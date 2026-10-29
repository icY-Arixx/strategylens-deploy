"""OFFLINE CONTRACT FIXTURES ONLY. Symbols/values/calendar are synthetic, not live evidence."""
import json
import math
import statistics
import traceback
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.adapters.financial_base import DataProviderError
from app.adapters.fuyao_client import FuyaoClient
from app.adapters.fuyao_financial import (CALENDAR, CONSTITUENTS, FINANCIALS, HISTORY, VALUATIONS,
                                         FuyaoFinancialDataProvider, numeric)
from app.domain.models import Metric
from app.domain.strategy_engine import StrategyEngine
from app.domain.volatility import InsufficientHistory, annualized_volatility
from app.main import create_app
from app.services.strategy_compiler import StrategyCompiler

TEST_CREDENTIAL = "fixture-sentinel-not-a-real-credential"
CLOCK = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
SYMBOLS = ["600001.SH", "000002.SZ"]
# Synthetic weekdays, deliberately NOT asserted to be the real exchange calendar.
candidate = CLOCK.replace(hour=0) - timedelta(days=110)
DAYS = []
while candidate.date() < CLOCK.date():
    if candidate.weekday() < 5:
        local_midnight = candidate.replace(hour=16) - timedelta(days=1)
        DAYS.append(int(local_midnight.timestamp() * 1000))
    candidate += timedelta(days=1)
DAYS = DAYS[-61:]
RETURNS = [.01 if i % 2 else -.01 for i in range(60)]
CLOSES = [100.0]
for daily_return in RETURNS:
    CLOSES.append(CLOSES[-1] * (1 + daily_return))


def envelope(data, *, code=0, request_id="fixture-request", message="fixture"):
    return httpx.Response(200, json={"code":code, "message":message, "request_id":request_id, "data":data})


class OfficialContractFixture:
    def __init__(self, overrides=None, count=2):
        self.overrides = overrides or {}
        self.symbols = SYMBOLS[:count]
        self.calls = []

    def __call__(self, request):
        self.calls.append(request)
        assert request.url.host == "fuyao.aicubes.cn"
        assert request.headers["X-api-key"] == TEST_CREDENTIAL
        path = request.url.path
        if path in self.overrides:
            return self.overrides[path](request)
        if path == CONSTITUENTS:
            assert request.url.params["thscode"] == "000300.SH"
            return envelope({"timestamp":DAYS[-1], "item":[{"thscode":s, "ticker":s[:6], "name":f"fixture {s}"} for s in self.symbols]})
        if path == CALENDAR:
            return envelope({"timestamp":DAYS[-1], "item":[{"date_ms":d, "date":datetime.fromtimestamp(d/1000,timezone(timedelta(hours=8))).strftime("%Y%m%d")} for d in DAYS]})
        if path == VALUATIONS:
            requested = request.url.params["thscodes"].split(",")
            assert len(requested) <= 100
            return envelope({"timestamp":DAYS[-1], "total":len(requested), "item":[{"thscode":s, "pe_ttm":18.5} for s in requested]}, request_id="fixture-pe")
        if path == FINANCIALS:
            return envelope({"thscode":request.url.params["thscode"], "report":request.url.params["report"],
                "abilities":[{"ability":"growth", "indicators":[
                    {"index_id":"operating_income_yoy_growth_ratio", "value":"12.3400"},
                    {"index_id":"net_profit_yoy_growth_ratio", "value":"8.0000"}]}]}, request_id="fixture-financial")
        if path == HISTORY:
            assert request.url.params["interval"] == "1d"
            assert request.url.params["adjust"] == "forward"
            return envelope({"timestamp":DAYS[-1], "item":[{"date_ms":d, "close_price":v} for d,v in zip(DAYS,CLOSES)]}, request_id="fixture-history")
        raise AssertionError("Undocumented endpoint")


@pytest.fixture
def make_provider():
    providers = []
    def factory(overrides=None, count=2):
        transport = OfficialContractFixture(overrides, count)
        client = FuyaoClient(TEST_CREDENTIAL, transport=httpx.MockTransport(transport), min_interval=0)
        provider = FuyaoFinancialDataProvider(client, report="2026-2", clock=lambda:CLOCK)
        providers.append(provider)
        return provider, transport
    yield factory
    for provider in providers:
        provider.close()


def test_official_fixture_flow_preserves_raw_units_ids_and_formula(make_provider):
    provider, transport = make_provider()
    snapshot = provider.fetch_snapshot("000300.SH")
    assert snapshot.data_mode == "REAL"  # Adapter branch; fixture does NOT claim live verification.
    assert snapshot.provider == provider.name
    assert len(snapshot.stocks) == 2 and len(transport.calls) == 7
    assert snapshot.universe_evidence.request_id == "fixture-request"
    obs = snapshot.stocks[0].observations
    revenue = obs[Metric.revenue_yoy]
    assert revenue.value == 12.34
    assert revenue.evidence.raw_value == "12.3400"
    assert revenue.evidence.normalized_value == 12.34 and revenue.unit == "%"
    assert revenue.evidence.field == "operating_income_yoy_growth_ratio"
    assert revenue.evidence.request_id == "fixture-financial"
    assert revenue.evidence.data_as_of is None  # Do not fake a publication timestamp.
    assert revenue.reporting_period == "2026-2"
    assert obs[Metric.pe_ttm].evidence.field == "pe_ttm"
    vol = obs[Metric.volatility_60d]
    assert vol.value == pytest.approx(statistics.stdev(RETURNS) * math.sqrt(252) * 100)
    assert len(vol.evidence.raw_value) == 61
    assert vol.evidence.adjustment == "forward"
    assert "ddof=1" in vol.evidence.calculation_method
    assert vol.evidence.request_id == "fixture-history"
    strategy = StrategyCompiler().compile("fixed conditions")
    strategy.universe = "000300.SH"
    assert all(r.status == "selected" for r in StrategyEngine().evaluate(strategy, snapshot.stocks))


@pytest.mark.parametrize("raw,expected", [(None,None), ("0",0), ("-16.0031",-16.0031), ("89.12000000",89.12), ("0.12",.12)])
def test_percent_conversion_never_scales_or_fills(raw, expected):
    assert numeric(raw) == expected


@pytest.mark.parametrize("raw", [True, "NaN", "inf", "", "12%", {}, [], "1e10000", "1e-10000"])
def test_invalid_numbers_not_silently_coerced(raw):
    with pytest.raises(ValueError):
        numeric(raw)


def test_financial_null_yields_unknown(make_provider):
    def missing(request):
        return envelope({"thscode":request.url.params["thscode"], "report":"2026-2", "abilities":[
            {"ability":"growth", "indicators":[{"index_id":"operating_income_yoy_growth_ratio", "value":None},
                {"index_id":"net_profit_yoy_growth_ratio", "value":"8"}]}]})
    provider, _ = make_provider({FINANCIALS:missing})
    snapshot = provider.fetch_snapshot("000300.SH")
    result = StrategyEngine().evaluate(StrategyCompiler().compile("test"), snapshot.stocks)[0]
    assert result.status == "unknown"
    check = next(c for c in result.checks if c.metric == Metric.revenue_yoy)
    assert check.status == "unknown" and check.actual_value is None
    assert check.evidence.raw_value is None
    assert check.evidence.error.category == "missing_data"


@pytest.mark.parametrize("code,category", [(2001,"authentication_error"), (2003,"permission_error"),
    (5002,"timeout"), (5003,"upstream_error"), (4001,"upstream_error"), (3002,"missing_data")])
def test_business_code_nonzero_http200_is_failure(make_provider, code, category):
    provider, _ = make_provider({CONSTITUENTS:lambda request:envelope(None, code=code)})
    with pytest.raises(DataProviderError) as error:
        provider.fetch_snapshot("000300.SH")
    assert error.value.issue.category == category
    assert error.value.issue.business_code == code
    assert error.value.issue.request_id == "fixture-request"


@pytest.mark.parametrize("payload", [{"code":"0", "message":"x", "data":{}},
    {"code":0,"message":"x","data":{"item":{}}}, {"code":0,"message":"x","data":None},
    {"code":0,"message":"x","data":{"timestamp":DAYS[-1],"item":[]}}])
def test_malformed_or_empty_universe_fails(make_provider, payload):
    provider, _ = make_provider({CONSTITUENTS:lambda request:httpx.Response(200,json=payload)})
    with pytest.raises(DataProviderError) as error:
        provider.fetch_snapshot("000300.SH")
    assert error.value.issue.category == "invalid_payload"


def test_timeout_has_sanitized_exception_and_no_fallback(make_provider, caplog):
    def timeout(request):
        raise httpx.ReadTimeout("upstream echoed " + TEST_CREDENTIAL, request=request)
    provider, transport = make_provider({CONSTITUENTS:timeout})
    with pytest.raises(DataProviderError) as error:
        provider.fetch_snapshot("000300.SH")
    assert error.value.issue.category == "timeout"
    assert len(transport.calls) == 1
    rendered = "".join(traceback.format_exception(error.type, error.value, error.tb))
    assert TEST_CREDENTIAL not in rendered
    assert TEST_CREDENTIAL not in caplog.text


def test_partial_failure_api_is_explicit_and_key_not_persisted(make_provider, tmp_path, caplog):
    def financial_error(request):
        return envelope(None, code=5003, message="secret="+TEST_CREDENTIAL, request_id=TEST_CREDENTIAL)
    provider, _ = make_provider({FINANCIALS:financial_error})
    path = tmp_path / "partial.sqlite3"
    with TestClient(create_app(path, provider)) as client:
        session = client.post("/api/strategies/compile", json={"source_text":"test"}).json()
        sid = session["strategy"]["strategy_id"]
        response = client.post(f"/api/strategies/{sid}/execute", json={"expected_revision":1})
        assert response.status_code == 200
        result = response.json()
        assert result["latest_run"]["status"] == "partial_failure"
        assert result["latest_run"]["unknown_count"] == 2
        assert result["latest_run"]["selected_count"] == 0
        assert {i["category"] for i in result["latest_run"]["issues"]} == {"upstream_error"}
        snapshot = client.get('/api/snapshots/'+result["latest_execution"]["snapshot_id"])
        assert snapshot.status_code == 200
        assert TEST_CREDENTIAL not in response.text + snapshot.text + caplog.text
    assert TEST_CREDENTIAL.encode() not in path.read_bytes()


def test_authentication_failure_api_records_failed_run_not_empty_success(make_provider, tmp_path):
    provider, transport = make_provider({CONSTITUENTS:lambda request:envelope(None,code=2001,message=TEST_CREDENTIAL)})
    with TestClient(create_app(tmp_path/"auth.sqlite3", provider)) as client:
        session = client.post("/api/strategies/compile",json={"source_text":"test"}).json()
        sid = session["strategy"]["strategy_id"]
        response = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1})
        assert response.status_code == 502
        assert response.json()["category"] == "authentication_error"
        assert TEST_CREDENTIAL not in response.text
        loaded = client.get(f"/api/strategies/{sid}").json()
        assert loaded["latest_execution"] is None
        assert loaded["latest_run"]["status"] == "failed"
        assert loaded["strategy"]["status"] == "draft"
        assert len(transport.calls) == 1


@pytest.mark.parametrize("bars", [0, 59, 60])
def test_insufficient_history_unknown_without_shortening(make_provider, bars):
    def short_history(request):
        return envelope({"timestamp":DAYS[-1], "item":[{"date_ms":d,"close_price":v} for d,v in list(zip(DAYS,CLOSES))[:bars]]})
    provider, _ = make_provider({HISTORY:short_history},count=1)
    obs = provider.fetch_snapshot("000300.SH").stocks[0].observations[Metric.volatility_60d]
    assert obs.value is None
    assert obs.evidence.error.category == "missing_data"
    assert len(obs.evidence.raw_value) == bars  # Preserve actual upstream rows, no synthetic null bars.
    assert len(obs.evidence.calculation_inputs["expected_calendar_dates"]) == 61
    assert all(r["close_price"] is not None for r in obs.evidence.raw_value)


def test_volatility_formula_constant_and_invalid_prices():
    assert annualized_volatility([100.0]*61) == 0
    assert annualized_volatility(CLOSES) == pytest.approx(statistics.stdev(RETURNS)*math.sqrt(252)*100)
    with pytest.raises(InsufficientHistory):
        annualized_volatility([100.0]*60)
    with pytest.raises(ValueError):
        annualized_volatility([100.0]*60+[0])


def test_permission_circuit_does_not_repeat_for_every_stock(make_provider):
    provider, transport = make_provider({FINANCIALS:lambda request:envelope(None,code=2003)})
    snapshot = provider.fetch_snapshot("000300.SH")
    assert len([r for r in transport.calls if r.url.path == FINANCIALS]) == 1
    assert len(snapshot.stocks) == 2
    assert all(s.observations[Metric.revenue_yoy].value is None for s in snapshot.stocks)
    assert snapshot.stocks[0].observations[Metric.revenue_yoy].evidence.request_performed is True
    assert snapshot.stocks[1].observations[Metric.revenue_yoy].evidence.request_performed is False
    assert snapshot.stocks[1].observations[Metric.revenue_yoy].evidence.request_id is None


def test_rate_limit_aborts_instead_of_retry_storm(make_provider):
    provider, transport = make_provider({VALUATIONS:lambda request:httpx.Response(429,text="busy")})
    with pytest.raises(DataProviderError) as error:
        provider.fetch_snapshot("000300.SH")
    assert error.value.issue.business_code == 4001
    assert len([r for r in transport.calls if r.url.path == VALUATIONS]) == 1
    assert not any(r.url.path in (FINANCIALS,HISTORY) for r in transport.calls)


def test_client_paces_requests_without_sleeping_in_fixture():
    current, delays = [10.0], []
    def sleeper(delay):
        delays.append(delay)
        current[0] += delay
    client = FuyaoClient(TEST_CREDENTIAL,transport=httpx.MockTransport(lambda req:envelope({"item":[]})),
                         min_interval=1,sleeper=sleeper,monotonic=lambda:current[0])
    try:
        for _ in range(3):
            client.get(CALENDAR)
        assert delays == [1,1]
    finally:
        client.close()


def test_report_must_be_explicit_no_latest_guess(make_provider):
    provider, transport = make_provider()
    provider.report = ""
    with pytest.raises(DataProviderError) as error:
        provider.fetch_snapshot("000300.SH")
    assert error.value.issue.category == "invalid_payload"
    assert transport.calls == []


def test_full_300_fixture_uses_all_members_and_100_symbol_batches(make_provider):
    provider, transport = make_provider()
    transport.symbols = [f"{600000+i:06d}.SH" for i in range(300)]  # Synthetic, not a real constituent list.
    progress = []
    snapshot = provider.fetch_snapshot("000300.SH",progress=lambda total,done:progress.append((total,done)))
    assert len(snapshot.stocks) == 300
    assert len(transport.calls) == 605
    batches = [r.url.params["thscodes"].split(",") for r in transport.calls if r.url.path == VALUATIONS]
    assert [len(batch) for batch in batches] == [100,100,100]
    assert [s for batch in batches for s in batch] == transport.symbols
    assert len([r for r in transport.calls if r.url.path == FINANCIALS]) == 300
    assert len([r for r in transport.calls if r.url.path == HISTORY]) == 300
    assert progress[0] == (300,0) and progress[-1] == (300,300)


def test_single_stock_failure_does_not_hide_healthy_stock(make_provider):
    def mixed(request):
        symbol = request.url.params["thscode"]
        if symbol == SYMBOLS[0]:
            return envelope(None,code=5003)
        return envelope({"thscode":symbol,"report":"2026-2","abilities":[{"ability":"growth","indicators":[
            {"index_id":"operating_income_yoy_growth_ratio","value":"12"},
            {"index_id":"net_profit_yoy_growth_ratio","value":"8"}]}]})
    provider, _ = make_provider({FINANCIALS:mixed})
    snapshot = provider.fetch_snapshot("000300.SH")
    results = StrategyEngine().evaluate(StrategyCompiler().compile("test"),snapshot.stocks)
    assert [r.status for r in results] == ["unknown","selected"]
    assert {i.symbol for i in snapshot.issues} == {SYMBOLS[0]}


def test_no_external_redirect_or_undocumented_url_can_receive_key(make_provider):
    provider, transport = make_provider()
    with pytest.raises(DataProviderError) as error:
        provider.client.get("https://example.com/collect")
    assert error.value.issue.category == "invalid_payload"
    assert transport.calls == []


def test_real_snapshot_can_be_reused_without_new_credentials(make_provider, tmp_path):
    path = tmp_path/"offline-reuse.sqlite3"
    provider, transport = make_provider(count=1)
    with TestClient(create_app(path,provider)) as client:
        session = client.post("/api/strategies/compile",json={"source_text":"test"}).json()
        sid = session["strategy"]["strategy_id"]
        first = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1}).json()
    no_key = FuyaoFinancialDataProvider(FuyaoClient(api_key=""),report="2026-2")
    with TestClient(create_app(path,no_key)) as client:
        reused = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1})
        assert reused.status_code == 200 and reused.json()["latest_run"]["snapshot_reused"] is True
        assert reused.json()["latest_execution"]["snapshot_id"] == first["latest_execution"]["snapshot_id"]
        refreshed = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1,"refresh_data":True})
        assert refreshed.status_code == 502 and refreshed.json()["category"] == "authentication_error"


def test_changed_report_requires_explicit_snapshot_refresh(make_provider, tmp_path):
    provider, _ = make_provider(count=1)
    with TestClient(create_app(tmp_path/"report.sqlite3",provider)) as client:
        session = client.post("/api/strategies/compile",json={"source_text":"test"}).json()
        sid = session["strategy"]["strategy_id"]
        assert client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1}).status_code == 200
        provider.report = "2026-3"
        response = client.post(f"/api/strategies/{sid}/execute",json={"expected_revision":1})
        assert response.status_code == 422
        assert "报告期" in response.json()["detail"]
