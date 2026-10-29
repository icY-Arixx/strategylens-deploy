from app.domain.models import Condition, Strategy


class DemoStrategyCompiler:
    """DEMO: every non-empty input maps to the same template. No semantic parsing."""

    def compile(self, text: str) -> Strategy:
        text = text.strip()
        if not text:
            raise ValueError("请输入选股意图")
        specs = [("经营改善", "revenue_yoy", ">", 0, "%"),
                 ("经营改善", "net_profit_yoy", ">", 0, "%"),
                 ("估值合理", "pe_ttm", "<", 30, "x"),
                 ("走势稳定", "volatility_60d", "<", 30, "%")]
        return Strategy(source_text=text, conditions=[Condition(
            concept=concept, metric=metric, operator=op, value=value, unit=unit,
            origin="system_default", rationale="固定四条件模板；未调用 LLM，未理解任意输入语义")
            for concept, metric, op, value, unit in specs])


# Compatibility for offline callers; runtime selection is explicit in app lifespan.
StrategyCompiler = DemoStrategyCompiler
