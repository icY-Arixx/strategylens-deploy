from app.adapters.mock_financial import MockFinancialDataProvider
from app.main import create_app
from fastapi.testclient import TestClient


def test_added_condition_preserves_unmentioned_conditions_and_history(client):
    initial = client.post("/api/strategies/compile",json={"source_text":"test"}).json()
    sid = initial["strategy"]["strategy_id"]
    first = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1}).json()
    original = first["strategy"]["conditions"]
    extra = {**original[2],"condition_id":"manual-lower-bound","operator":">","value":10,
             "origin":"user_explicit","rationale":"用户手动添加"}
    edited = client.put(f"/api/strategies/{sid}/conditions",json={"expected_revision":1,"conditions":original+[extra]}).json()
    assert edited["strategy"]["conditions"][:4] == original
    assert edited["strategy"]["conditions"][4]["origin"] == "user_explicit"
    assert edited["strategy"]["status"] == "stale"
    second = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":2}).json()
    assert second["latest_execution"]["snapshot_id"] == first["latest_execution"]["snapshot_id"]
    history = client.get('/api/executions/'+first["latest_execution"]["execution_id"])
    assert history.status_code == 200 and history.json() == first["latest_execution"]
    assert history.json()["strategy_snapshot"]["conditions"] == original
    assert client.get("/api/executions/absent").status_code == 404


def test_result_metrics_remain_in_snapshot_after_condition_removed(client):
    initial = client.post("/api/strategies/compile",json={"source_text":"test"}).json()
    sid = initial["strategy"]["strategy_id"]
    first = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1}).json()
    kept = [c for c in first["strategy"]["conditions"] if c["metric"] != "pe_ttm"]
    assert client.put(f"/api/strategies/{sid}/conditions",json={"expected_revision":1,"conditions":kept}).status_code == 200
    second = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":2}).json()
    assert all(len(r["checks"]) == 3 for r in second["latest_execution"]["results"])
    snapshot = client.get('/api/snapshots/'+second["latest_execution"]["snapshot_id"]).json()
    assert all(set(s["observations"]) == {"revenue_yoy","net_profit_yoy","pe_ttm","volatility_60d"} for s in snapshot["stocks"])
    assert snapshot["stocks"][0]["observations"]["pe_ttm"]["value"] == 18


def test_display_history_and_assets_never_fetch_financial_provider(tmp_path):
    class CountingProvider(MockFinancialDataProvider):
        calls = 0
        def fetch_snapshot(self, universe, progress=None):
            self.calls += 1
            return super().fetch_snapshot(universe,progress)
    provider = CountingProvider()
    with TestClient(create_app(tmp_path/"workspace.sqlite3",provider)) as client:
        initial = client.post("/api/strategies/compile",json={"source_text":"test"}).json()
        sid = initial["strategy"]["strategy_id"]
        result = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1}).json()["latest_execution"]
        assert provider.calls == 1
        assert client.get('/api/executions/'+result["execution_id"]).status_code == 200
        assert client.get('/api/snapshots/'+result["snapshot_id"]).status_code == 200
        assert client.get("/static/workspace-core.mjs").status_code == 200
        assert provider.calls == 1
