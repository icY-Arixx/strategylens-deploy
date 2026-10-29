import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.adapters.mock_financial import MockFinancialDataProvider
from app.domain.models import Execution
from app.main import create_app
from app.store.sqlite_store import SQLiteStore


def create(client):
    return client.post("/api/strategies/compile",json={"source_text":"test"}).json()


def execute(client, session, **options):
    strategy = session["strategy"]
    response = client.post(f'/api/strategies/{strategy["strategy_id"]}/execute',json={"expected_revision":strategy["revision"],**options})
    assert response.status_code == 200, response.text
    return response.json()


def test_snapshot_binding_reuse_refresh_and_offline_restore(tmp_path):
    class CountingMock(MockFinancialDataProvider):
        calls = 0
        def fetch_snapshot(self, universe, progress=None):
            self.calls += 1
            return super().fetch_snapshot(universe, progress)
    provider = CountingMock()
    path = tmp_path/"snapshot.sqlite3"
    with TestClient(create_app(path,provider)) as client:
        first = execute(client,create(client))
        run = first["latest_run"]
        assert run["run_id"] == first["latest_execution"]["execution_id"]
        assert run["strategy_revision"] == 1
        assert run["snapshot_id"] == first["latest_execution"]["snapshot_id"]
        assert run["selected_count"] == 3 and run["excluded_count"] == 5 and run["unknown_count"] == 2
        assert run["started_at"] and run["completed_at"]
        conditions = first["strategy"]["conditions"]
        conditions[2]["value"] = 20
        sid = first["strategy"]["strategy_id"]
        draft = client.put(f"/api/strategies/{sid}/conditions",json={"expected_revision":1,"conditions":conditions}).json()
        second = execute(client,draft)
        assert provider.calls == 1
        assert second["latest_run"]["strategy_revision"] == 2 and second["latest_run"]["snapshot_reused"] is True
        assert second["latest_execution"]["diff"]["condition_attributable"] is True
        assert second["latest_execution"]["diff"]["current_snapshot_id"] == run["snapshot_id"]
        third = execute(client,second,refresh_data=True)
        assert provider.calls == 2
        assert third["latest_execution"]["snapshot_id"] != run["snapshot_id"]
        assert third["latest_execution"]["diff"]["condition_attributable"] is False
        assert third["latest_execution"]["diff"]["attribution_note"] == "本次比较同时存在数据快照变化。"
        assert third["latest_execution"]["diff"]["added"] == third["latest_execution"]["diff"]["removed"] == []
        old = client.get('/api/snapshots/'+run["snapshot_id"]).json()
        assert old["snapshot_id"] == run["snapshot_id"] and len(old["content_hash"]) == 64
        assert "origin" in third["strategy"]["conditions"][0] and "source" not in third["strategy"]["conditions"][0]
        check = third["latest_execution"]["results"][0]["checks"][0]
        assert "data_source" in check and "source" not in check
        bad = dict(third["latest_execution"])
        bad["run"] = {**bad["run"],"strategy_revision":999}
        with pytest.raises(ValidationError,match="绑定不一致"):
            Execution.model_validate(bad)
    with TestClient(create_app(path,provider)) as client:
        restored = client.get(f"/api/strategies/{sid}").json()
        assert restored == third and provider.calls == 2  # GET must not fetch external data.


def test_snapshot_id_cannot_be_overwritten_or_silently_tampered(tmp_path):
    store = SQLiteStore(tmp_path/"immutable.sqlite3")
    snapshot = store.save_snapshot(MockFinancialDataProvider().fetch_snapshot("CSI300_DEMO"))
    with pytest.raises(sqlite3.IntegrityError):
        store.save_snapshot(snapshot.model_copy(update={"stocks":[]}))
    assert len(store.read_snapshot(snapshot.snapshot_id).stocks) == 10
    with store.connection() as conn:
        payload = snapshot.model_dump()
        payload["parameters"]["tampered"] = True
        changed = snapshot.model_validate(payload).model_dump_json()
        conn.execute("UPDATE data_snapshots SET payload=? WHERE snapshot_id=?",(changed,snapshot.snapshot_id))
    with pytest.raises(ValueError,match="完整性"):
        store.read_snapshot(snapshot.snapshot_id)


def test_old_database_backed_up_values_preserved_without_fabricated_snapshot(tmp_path, strategy):
    old_condition_ids = [c.condition_id for c in strategy.conditions]
    payload = strategy.model_dump(mode="json")
    payload["status"] = "executed"
    for c in payload["conditions"]:
        c["source"] = c.pop("origin")
    legacy = {"execution_id":"phase1-run", "strategy_id":strategy.strategy_id, "revision":1,
              "executed_at":payload["updated_at"], "data_mode":"DEMO / MOCK", "provider":"old-demo",
              "strategy_snapshot":payload,"results":[],"diff":None}
    path = tmp_path/"legacy.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript("CREATE TABLE strategies(strategy_id TEXT PRIMARY KEY,revision INTEGER,payload TEXT);"
                           "CREATE TABLE executions(sequence INTEGER PRIMARY KEY AUTOINCREMENT,execution_id TEXT UNIQUE,strategy_id TEXT,payload TEXT);")
        conn.execute("INSERT INTO strategies VALUES(?,?,?)",(strategy.strategy_id,1,json.dumps(payload)))
        conn.execute("INSERT INTO executions(execution_id,strategy_id,payload) VALUES(?,?,?)",("phase1-run",strategy.strategy_id,json.dumps(legacy)))
    store = SQLiteStore(path)
    current, execution = store.read(strategy.strategy_id)
    assert current.status == "stale" and current.revision == 1
    assert [c.condition_id for c in current.conditions] == old_condition_ids
    assert current.conditions[2].value == 30
    assert execution.snapshot_id is None and execution.run is None
    backups = list((tmp_path/"backups").glob("*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert "source" in json.loads(conn.execute("SELECT payload FROM strategies").fetchone()[0])["conditions"][0]
    SQLiteStore(path)
    assert len(list((tmp_path/"backups").glob("*.sqlite3"))) == 1


def test_real_is_default_and_missing_key_never_selects_demo(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATEGYLENS_PROVIDER",raising=False)
    monkeypatch.delenv("HITHINK_FINANCE_API_KEY",raising=False)
    with TestClient(create_app(tmp_path/"real.sqlite3")) as client:
        assert client.get("/api/config").json()["data_mode"] == "REAL"
        session = create(client)
        assert session["strategy"]["universe"] == "000300.SH"
        response = client.post(f'/api/strategies/{session["strategy"]["strategy_id"]}/execute',json={"expected_revision":1})
        assert response.status_code == 502 and response.json()["category"] == "authentication_error"
        loaded = client.get(f'/api/strategies/{session["strategy"]["strategy_id"]}').json()
        assert loaded["latest_execution"] is None and loaded["latest_run"]["status"] == "failed"


def test_snapshot_provider_mismatch_rejected_without_fetch(client):
    first = execute(client,create(client))
    service = client.app.state.sessions
    snapshot = service.store.read_snapshot(first["latest_execution"]["snapshot_id"])
    other = service.store.save_snapshot(snapshot.model_copy(update={"snapshot_id":"other-mode", "provider":"other-provider"}))
    response = client.post(f'/api/strategies/{first["strategy"]["strategy_id"]}/execute',json={"expected_revision":1,"snapshot_id":other.snapshot_id})
    assert response.status_code == 422 and "不匹配" in response.json()["detail"]
