from datetime import datetime, timezone

from app.domain.models import DataSnapshot, Evidence, METRIC_INFO, Metric, Observation, StockData


class MockFinancialDataProvider:
    name = "MockFinancialDataProvider / DEMO"
    data_mode = "DEMO / MOCK"
    universe = "CSI300_DEMO"

    def fetch_universe(self, universe: str) -> list[StockData]:
        if universe != "CSI300_DEMO":
            raise ValueError("Mock Provider 只支持 CSI300_DEMO")
        # Fictional identities AND values. Never presented as actual CSI300 membership.
        rows = [
            ("DEMO001", "示例·青禾制造", 12, 18, 18, 22),
            ("DEMO002", "示例·澄川消费", 8, 10, 25, 24),
            ("DEMO003", "示例·远山科技", 20, 30, 35, 25),
            ("DEMO004", "示例·星港材料", -5, -10, 40, 38),
            ("DEMO005", "示例·沐光医药", 10, 12, None, 20),
            ("DEMO006", "示例·明岸能源", 15, 20, 15, 35),
            ("DEMO007", "示例·云杉服务", 0, 5, 12, 15),
            ("DEMO008", "示例·知行装备", 9, 11, 20, 29),
            ("DEMO009", "示例·新原通信", 4, -2, None, 18),
            ("DEMO010", "示例·融溪物流", 6, 7, 10, None),
        ]
        result = []
        retrieved_at = datetime.now(timezone.utc)
        for symbol, name, *values in rows:
            observations = {}
            for metric, value in zip(Metric, values):
                observations[metric] = Observation(
                    metric=metric, value=value, unit=METRIC_INFO[metric][1],
                    data_source="DEMO / MOCK · 人工构造样本，非真实金融数据",
                    retrieved_at=retrieved_at,
                    reporting_period="DEMO 财报期 2026Q2" if metric in (Metric.revenue_yoy, Metric.net_profit_yoy)
                    else "DEMO 估值截面" if metric == Metric.pe_ttm else "DEMO 连续60交易日窗口",
                    missing_reason="Mock 故意设置缺失值" if value is None else None,
                    evidence=Evidence(provider=self.name, field=metric.value, raw_value=value,
                                      normalized_value=value, unit=METRIC_INFO[metric][1],
                                      retrieved_at=retrieved_at, reporting_period="DEMO / MOCK", request_performed=False))
            result.append(StockData(symbol=symbol, name=name, observations=observations))
        return result

    def fetch_snapshot(self, universe: str, progress=None) -> DataSnapshot:
        stocks = self.fetch_universe(universe)
        if progress:
            progress(len(stocks), len(stocks))
        return DataSnapshot(universe=universe, provider=self.name, data_mode=self.data_mode, stocks=stocks,
                            parameters={"fixture_version": "phase1-10-fictional-stocks"})
