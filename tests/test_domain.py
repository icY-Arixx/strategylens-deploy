from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.adapters.fuyao_financial import FuyaoFinancialDataProvider
from app.adapters.fuyao_client import FuyaoClient
from app.adapters.financial_base import DataProviderError
from app.adapters.mock_financial import MockFinancialDataProvider
from app.domain.conflicts import detect_conflicts
from app.domain.models import Condition, ConditionCheck, Metric, Observation, StockData, Strategy
from app.domain.strategy_engine import StrategyEngine


def condition(**changes):
    return Condition.model_validate(dict(concept="估值合理", metric="pe_ttm", operator="<", value=30,
                                         unit="x", origin="system_default", rationale="测试条件", **changes))


@pytest.mark.parametrize("field,value", [
    ("operator", "~"), ("metric", "invented_metric"), ("origin", "ai_decides"),
    ("unit", "%"), ("value", float("nan")), ("value", float("inf")),
    ("condition_id", ""), ("concept", ""), ("rationale", ""),
    ("value", True), ("value", "30"), ("enabled", "false")])
def test_condition_schema_rejects_invalid(strategy, field, value):
    payload = strategy.conditions[2].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        Condition.model_validate(payload)


@pytest.mark.parametrize("field,value", [("revision", 0), ("status", "completed"), ("universe", "ALL"), ("source_text", "")])
def test_strategy_schema_rejects_invalid(strategy, field, value):
    payload = strategy.model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        Strategy.model_validate(payload)


def test_unknown_extra_fields_and_duplicate_ids_are_rejected(strategy):
    with pytest.raises(ValidationError):
        Condition.model_validate({**strategy.conditions[0].model_dump(), "secret_override": True})
    with pytest.raises(ValidationError):
        Strategy.model_validate({**strategy.model_dump(), "conditions": [strategy.conditions[0]] * 2})


@pytest.mark.parametrize("actual,expected", [(29.9, "pass"), (30, "fail"), (30.1, "fail"), (0, "pass"), (None, "unknown")])
def test_engine_pass_fail_unknown_without_provider(actual, expected):
    # Direct normalized data, no MockFinancialDataProvider required by engine.
    c = condition()
    obs = Observation(metric="pe_ttm", value=actual, unit="x", data_source="Unit fixture",
                      retrieved_at=datetime.now(timezone.utc), reporting_period="fixture period")
    stock = StockData(symbol="UNIT", name="Unit Stock", observations={Metric.pe_ttm: obs})
    result = StrategyEngine().evaluate(Strategy(source_text="test", conditions=[c]), [stock])[0]
    check = result.checks[0]
    assert check.status == expected
    assert check.actual_value is actual or check.actual_value == actual
    assert check.threshold == 30
    assert check.data_source == "Unit fixture"
    assert check.retrieved_at == obs.retrieved_at
    assert check.reporting_period == "fixture period"
    if actual is None:
        assert check.actual_value is None  # 0 would PASS PE < 30: never coerce missing to zero.
        assert result.status == "unknown"
        assert "数据不足" in check.reason


def test_absent_observation_is_unknown_not_zero():
    c = condition()
    result = StrategyEngine().evaluate(Strategy(source_text="test", conditions=[c]),
                                      [StockData(symbol="X", name="missing", observations={})])[0]
    assert result.status == "unknown"
    assert result.checks[0].actual_value is None
    assert result.checks[0].retrieved_at is None
    assert result.checks[0].reporting_period is None


def test_mock_distribution_and_all_checks(strategy):
    results = StrategyEngine().evaluate(strategy, MockFinancialDataProvider().fetch_universe(strategy.universe))
    assert len(results) == 10
    assert [r.symbol for r in results if r.status == "selected"] == ["DEMO001", "DEMO002", "DEMO008"]
    assert [r.symbol for r in results if r.status == "excluded"] == ["DEMO003", "DEMO004", "DEMO006", "DEMO007", "DEMO009"]
    assert [r.symbol for r in results if r.status == "unknown"] == ["DEMO005", "DEMO010"]
    assert all(len(r.checks) == 4 for r in results)
    assert all(c.data_source.startswith("DEMO / MOCK") for r in results for c in r.checks)
    by_id = {r.symbol: r for r in results}
    assert [c.status for c in by_id["DEMO003"].checks].count("fail") == 1
    assert [c.status for c in by_id["DEMO004"].checks].count("fail") == 4
    assert {c.status for c in by_id["DEMO009"].checks} == {"pass", "fail", "unknown"}
    assert by_id["DEMO009"].status == "excluded"  # failure dominates missing
    assert all(c.status == "pass" for c in by_id["DEMO001"].checks)
    assert all(c.status != "fail" for c in by_id["DEMO005"].checks)


def test_disabled_conditions_do_not_produce_checks(strategy):
    strategy.conditions[2].enabled = False
    results = StrategyEngine().evaluate(strategy, MockFinancialDataProvider().fetch_universe(strategy.universe))
    missing_pe = next(r for r in results if r.symbol == "DEMO005")
    assert missing_pe.status == "selected"
    assert len(missing_pe.checks) == 3
    assert all(c.metric != Metric.pe_ttm for c in missing_pe.checks)


def test_no_active_conditions_blocked(strategy):
    for c in strategy.conditions:
        c.enabled = False
    with pytest.raises(ValueError, match="至少启用"):
        StrategyEngine().evaluate(strategy, [])


@pytest.mark.parametrize("ops,values,conflicting", [
    ((">", "<"), (30, 10), True), ((">", "<"), (10, 10), True),
    ((">=", "<="), (10, 10), False), ((">=", "<"), (10, 10), True),
    (("==", ">"), (10, 10), True), (("==", "=="), (10, 11), True),
    ((">", "<"), (10, 30), False), (("==", "<="), (10, 10), False)])
def test_conflict_interval_boundaries(ops, values, conflicting):
    first, second = condition(), condition()
    first.operator, first.value = ops[0], values[0]
    second.operator, second.value = ops[1], values[1]
    conflicts = detect_conflicts([first, second])
    assert bool(conflicts) is conflicting
    if conflicting:
        assert set(conflicts[0].condition_ids) == {first.condition_id, second.condition_id}
    second.enabled = False
    assert detect_conflicts([first, second]) == []


@pytest.mark.parametrize("operator,actual,threshold,expected", [
    (">", 0, 0, "fail"), (">=", 0, 0, "pass"), ("<=", 30, 30, "pass"),
    ("==", 30, 30, "pass"), ("==", 29, 30, "fail")])
def test_all_comparison_operators(operator, actual, threshold, expected):
    c = condition()
    c.operator, c.value = operator, threshold
    obs = Observation(metric="pe_ttm", value=actual, unit="x", data_source="fixture",
                      retrieved_at=datetime.now(timezone.utc), reporting_period="fixture")
    result = StrategyEngine().evaluate(Strategy(source_text="test", conditions=[c]),
                                      [StockData(symbol="X", name="X", observations={Metric.pe_ttm: obs})])[0]
    assert result.checks[0].status == expected


def test_observation_rejects_nonfinite_and_unit_mismatch():
    payload = dict(metric="pe_ttm", value=10, unit="x", data_source="fixture",
                   retrieved_at=datetime.now(timezone.utc), reporting_period="fixture")
    for changed in ({"value": float("inf")}, {"unit": "%"}):
        with pytest.raises(ValidationError):
            Observation.model_validate({**payload, **changed})


def test_fuyao_without_key_explicitly_fails():
    provider = FuyaoFinancialDataProvider(FuyaoClient(api_key=""), report="2026-2")
    try:
        with pytest.raises(DataProviderError) as error:
            provider.fetch_universe("000300.SH")
        assert error.value.issue.category == "authentication_error"
    finally:
        provider.close()


@pytest.mark.parametrize("status,actual", [("pass", None), ("fail", None), ("unknown", 0)])
def test_condition_check_rejects_inconsistent_status(status, actual):
    with pytest.raises(ValidationError, match="unknown 必须"):
        ConditionCheck(condition_id="check", metric="pe_ttm", status=status, actual_value=actual,
                       threshold=30, operator="<", unit="x", data_source="fixture",
                       retrieved_at=None, reporting_period=None, reason="fixture")


def test_engine_rejects_duplicate_symbols(strategy):
    stocks = MockFinancialDataProvider().fetch_universe(strategy.universe)
    with pytest.raises(ValueError, match="重复股票"):
        StrategyEngine().evaluate(strategy, [stocks[0], stocks[0]])
