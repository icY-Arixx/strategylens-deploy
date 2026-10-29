import operator

from app.domain.conflicts import detect_conflicts
from app.domain.models import ConditionCheck, StockData, StockResult, Strategy
from app.services.explanation_service import check_reason, stock_explanation

COMPARATORS = {">": operator.gt, ">=": operator.ge, "<": operator.lt,
               "<=": operator.le, "==": operator.eq}


class StrategyEngine:
    """Pure deterministic evaluation; no network, database, or provider dependency."""

    def evaluate(self, strategy: Strategy, stocks: list[StockData]) -> list[StockResult]:
        active = [c for c in strategy.conditions if c.enabled]
        if not active:
            raise ValueError("至少启用一个条件才能执行")
        if detect_conflicts(active):
            raise ValueError("条件冲突，不能执行")
        if len({s.symbol for s in stocks}) != len(stocks):
            raise ValueError("Provider 返回了重复股票代码")
        results = []
        for stock in stocks:
            checks = []
            for c in active:
                obs = stock.observations.get(c.metric)
                value = obs.value if obs is not None else None
                status = "unknown" if value is None else (
                    "pass" if COMPARATORS[c.operator](value, c.value) else "fail")
                checks.append(ConditionCheck(
                    condition_id=c.condition_id, metric=c.metric, status=status, actual_value=value,
                    threshold=c.value, operator=c.operator, unit=c.unit,
                    data_source=obs.data_source if obs else "Provider 未提供观测",
                    retrieved_at=obs.retrieved_at if obs else None,
                    reporting_period=obs.reporting_period if obs else None,
                    reason=check_reason(c, obs, status), evidence=obs.evidence if obs else None))
            statuses = {c.status for c in checks}
            status = "excluded" if "fail" in statuses else "unknown" if "unknown" in statuses else "selected"
            results.append(StockResult(symbol=stock.symbol, name=stock.name, status=status,
                                       checks=checks, explanation=stock_explanation(checks, status)))
        return results
