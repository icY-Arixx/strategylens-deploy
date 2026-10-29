import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.adapters.mock_financial import MockFinancialDataProvider
from app.store.sqlite_store import RevisionConflict, SQLiteStore


def compile_strategy(client):
    response = client.post("/api/strategies/compile", json={"source_text": "经营改善、估值合理、走势稳定"})
    assert response.status_code == 201, response.text
    return response.json()


def execute(client, session):
    s = session["strategy"]
    return client.post(f'/api/strategies/{s["strategy_id"]}/execute', json={"expected_revision": s["revision"]})


def edit(client, session, conditions):
    s = session["strategy"]
    return client.put(f'/api/strategies/{s["strategy_id"]}/conditions', json={
        "expected_revision":s["revision"], "conditions":conditions})


def test_end_to_end_stale_immutable_snapshot_diff_and_restore(client):
    initial = compile_strategy(client)
    assert initial["strategy"]["status"] == "draft"
    assert {c["origin"] for c in initial["strategy"]["conditions"]} == {"system_default"}
    first_response = execute(client, initial)
    assert first_response.status_code == 200
    first = first_response.json()
    assert first["strategy"]["status"] == "executed"
    assert first["results_stale"] is False
    assert first["latest_execution"]["diff"] is None
    conditions = first["strategy"]["conditions"]
    conditions[2]["value"] = 20
    edited = edit(client, first, conditions).json()
    assert edited["strategy"]["revision"] == 2
    assert edited["strategy"]["status"] == "stale"
    assert edited["results_stale"] is True
    assert edited["strategy"]["conditions"][2]["origin"] == "user_explicit"
    assert edited["latest_execution"]["strategy_snapshot"]["conditions"][2]["value"] == 30
    assert edited["latest_execution"] == first["latest_execution"]
    sid = edited["strategy"]["strategy_id"]
    restored = client.get(f"/api/strategies/{sid}").json()
    assert restored == edited
    # Validation must NOT re-certify historical results as current.
    validated = client.post(f"/api/strategies/{sid}/validate", json={"expected_revision":2}).json()
    assert validated["strategy"]["status"] == "stale"
    assert validated["results_stale"] is True
    second = execute(client, edited).json()
    assert second["strategy"]["status"] == "executed"
    assert second["results_stale"] is False
    diff = second["latest_execution"]["diff"]
    assert diff["previous_count"] == 3
    assert diff["current_count"] == 1
    assert diff["previous_revision"] == 1 and diff["current_revision"] == 2
    assert diff["added"] == []
    assert diff["removed"] == ["DEMO002", "DEMO008"]
    assert diff["previous_execution_id"] == first["latest_execution"]["execution_id"]
    # Relaxation verifies additions as well as removals.
    conditions = second["strategy"]["conditions"]
    conditions[2]["value"] = 40
    third_draft = edit(client, second, conditions).json()
    third = execute(client, third_draft).json()["latest_execution"]["diff"]
    assert third["previous_count"] == 1 and third["current_count"] == 4
    assert third["added"] == ["DEMO002", "DEMO003", "DEMO008"]
    assert third["removed"] == []


def test_validate_transition_and_noop_does_not_increment(client):
    session = compile_strategy(client)
    sid = session["strategy"]["strategy_id"]
    response = client.post(f"/api/strategies/{sid}/validate", json={"expected_revision":1})
    assert response.status_code == 200
    validated = response.json()
    assert validated["strategy"]["status"] == "validated"
    assert validated["latest_execution"] is None
    unchanged = edit(client, validated, validated["strategy"]["conditions"]).json()
    assert unchanged == validated


def test_conflict_blocks_execution_without_provider_call(tmp_path):
    class NeverCalledProvider(MockFinancialDataProvider):
        name = "test sentinel"
        def fetch_universe(self, universe):
            raise AssertionError("Conflicts must be detected BEFORE data access")
    with TestClient(create_app(tmp_path / "conflict.sqlite3", NeverCalledProvider())) as client:
        session = compile_strategy(client)
        conditions = session["strategy"]["conditions"]
        conditions[2]["operator"], conditions[2]["value"] = ">", 30
        extra = {**conditions[2], "condition_id":"second-pe", "operator":"<", "value":10}
        edited = edit(client, session, conditions + [extra])
        assert edited.status_code == 200
        body = edited.json()
        assert len(body["conflicts"]) == 1
        assert len(body["strategy"]["conditions"]) == 5  # never silently overwrites
        response = execute(client, body)
        assert response.status_code == 422
        assert response.json()["conflicts"][0]["metric"] == "pe_ttm"
        assert client.get(f'/api/strategies/{body["strategy"]["strategy_id"]}').json()["latest_execution"] is None


def test_disable_delete_stale_and_zero_conditions_block(client):
    session = execute(client, compile_strategy(client)).json()
    conditions = session["strategy"]["conditions"]
    conditions[0]["enabled"] = False
    disabled = edit(client, session, conditions).json()
    assert disabled["strategy"]["status"] == "stale"
    deleted = edit(client, disabled, conditions[1:]).json()
    assert deleted["strategy"]["status"] == "stale"
    assert len(deleted["strategy"]["conditions"]) == 3
    empty = edit(client, deleted, []).json()
    assert empty["strategy"]["status"] == "stale"
    response = execute(client, empty)
    assert response.status_code == 422
    assert "至少启用" in response.json()["detail"]


def test_diff_includes_selected_becoming_unknown(client):
    session = compile_strategy(client)
    conditions = session["strategy"]["conditions"]
    conditions[2]["enabled"] = False
    without_pe = execute(client, edit(client, session, conditions).json()).json()
    conditions = without_pe["strategy"]["conditions"]
    conditions[2]["enabled"] = True
    with_pe = execute(client, edit(client, without_pe, conditions).json()).json()
    diff = with_pe["latest_execution"]["diff"]
    assert diff["previous_count"] == 5 and diff["current_count"] == 3
    assert diff["removed"] == ["DEMO003", "DEMO005"]
    assert diff["added"] == []
    status = {r["symbol"]:r["status"] for r in with_pe["latest_execution"]["results"]}
    assert status["DEMO003"] == "excluded" and status["DEMO005"] == "unknown"


def test_old_revision_rejected_and_data_unchanged(client):
    session = compile_strategy(client)
    conditions = session["strategy"]["conditions"]
    conditions[2]["value"] = 20
    current = edit(client, session, conditions).json()
    assert execute(client, session).status_code == 409
    assert edit(client, session, conditions).status_code == 409
    assert client.get(f'/api/strategies/{current["strategy"]["strategy_id"]}').json() == current


def test_store_compare_and_swap_detects_status_race(tmp_path, strategy):
    store = SQLiteStore(tmp_path / "race.sqlite3")
    store.create(strategy)
    validated = strategy.model_copy(update={"status":"validated"})
    store.save(strategy, validated)
    with pytest.raises(RevisionConflict):
        store.save(strategy, strategy.model_copy(update={"revision":2}))
    assert store.read(strategy.strategy_id)[0] == validated


def test_persistence_survives_app_restart(tmp_path):
    path = tmp_path / "persistent.sqlite3"
    with TestClient(create_app(path, MockFinancialDataProvider())) as first:
        executed = execute(first, compile_strategy(first)).json()
    with TestClient(create_app(path, MockFinancialDataProvider())) as second:
        loaded = second.get(f'/api/strategies/{executed["strategy"]["strategy_id"]}')
        assert loaded.status_code == 200
        assert loaded.json() == executed


def test_injected_alternate_provider_integrates_without_engine_change(tmp_path):
    from app.domain.models import StockData
    class AlternativeProvider(MockFinancialDataProvider):
        name = "Alternate test provider"
        def fetch_universe(self, universe):
            assert universe == "CSI300_DEMO"
            return [StockData(symbol="ALT", name="Alternate", observations={})]
    with TestClient(create_app(tmp_path / "alternate.sqlite3", AlternativeProvider())) as client:
        result = execute(client, compile_strategy(client)).json()["latest_execution"]
        assert result["provider"] == "Alternate test provider"
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "unknown"
        assert all(c["actual_value"] is None for c in result["results"][0]["checks"])


def test_http_errors_and_static_assets(client):
    assert client.get("/").status_code == 200
    assert "data-status" in client.get("/").text
    assert client.get("/api/config").json()["data_mode"] == "DEMO / MOCK"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/api/health").json()["compiler"] == "fixed_demo_template"
    assert client.get("/api/strategies/missing").status_code == 404
    assert client.post("/api/strategies/compile", json={"source_text":"  "}).status_code == 422
    session = compile_strategy(client)
    duplicate = [session["strategy"]["conditions"][0]] * 2
    assert edit(client, session, duplicate).status_code == 422
    conditions = session["strategy"]["conditions"]
    conditions[0]["value"] = None
    assert edit(client, session, conditions).status_code == 422
