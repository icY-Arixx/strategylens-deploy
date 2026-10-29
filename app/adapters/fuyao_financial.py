"""Official contracts checked at https://fuyao.aicubes.cn/llms-full.txt on 2026-10-28."""
import math
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from app.adapters.financial_base import DataProviderError
from app.adapters.fuyao_client import FuyaoClient, PROVIDER
from app.domain.models import DataIssue, DataSnapshot, Evidence, METRIC_INFO, Metric, Observation, StockData, now
from app.domain.volatility import InsufficientHistory, annualized_volatility

CONSTITUENTS = "/api/a-share-index/constituents/ths-stock-list"
FINANCIALS = "/api/a-share/financials/indicators"
VALUATIONS = "/api/a-share/valuations/snapshot"
HISTORY = "/api/a-share/prices/historical"
CALENDAR = "/api/a-share/calendar/trading-days"
SHANGHAI = timezone(timedelta(hours=8))
FINANCIAL_FIELDS = {Metric.revenue_yoy: "operating_income_yoy_growth_ratio",
                    Metric.net_profit_yoy: "net_profit_yoy_growth_ratio"}
VOLATILITY_METHOD = ("simple_return=close[t]/close[t-1]-1; sample_stdev(ddof=1) of exactly 60 daily returns"
                     " * sqrt(252) * 100; 61 calendar-aligned closes; official forward-adjusted 1d;"
                     " excludes Shanghai current calendar day; no filling, skipping or shortened window")


def numeric(raw):
    """Percentage points remain unchanged. Preserve raw separately, never null->0."""
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        raise ValueError("非数值")
    try:
        value = Decimal(str(raw).strip())
        result = float(value)
    except (InvalidOperation, ValueError, OverflowError):
        raise ValueError("非数值") from None
    if not value.is_finite() or not math.isfinite(result) or (value != 0 and result == 0):
        raise ValueError("非有限数值")
    return result


def from_ms(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("时间戳格式错误")
    return datetime.fromtimestamp(value / 1000, timezone.utc)


class FuyaoFinancialDataProvider:
    name = PROVIDER
    data_mode = "REAL"
    universe = "000300.SH"

    def __init__(self, client: FuyaoClient | None = None, *, report: str | None = None, clock=now):
        if client is None:
            try:
                timeout, interval = float(os.getenv("FUYAO_TIMEOUT", "20")), float(os.getenv("FUYAO_MIN_INTERVAL", "1"))
            except ValueError:
                raise ValueError("FUYAO_TIMEOUT/MIN_INTERVAL配置无效，不回显原值") from None
            client = FuyaoClient(timeout=timeout, min_interval=interval)
        self.client = client
        self.report = report if report is not None else os.getenv("FUYAO_REPORT", "")
        self.clock = clock

    @property
    def ready(self):
        return self.client.configured and bool(re.fullmatch(r"\d{4}-[1-4]", self.report))

    @property
    def snapshot_requirements(self):
        required = {"adjust":"forward", "returns":60, "volatility_definition":"simple-sample-60-252-percent-v1"}
        if self.report:
            required["report"] = self.report
        return required

    def _issue(self, category, endpoint, *, symbol=None, metric=None, request_id=None, message=None):
        return DataIssue(category=category, provider=self.name, endpoint=endpoint, symbol=symbol,
                         metric=metric, request_id=request_id, message=message or {
                             "missing_data": "官方指标缺失或窗口不足，不能判断",
                             "invalid_payload": "响应字段/数值/标的/日期不符合官方契约"}[category])

    def _payload_error(self, endpoint, rid=None):
        raise DataProviderError(self._issue("invalid_payload", endpoint, request_id=rid)) from None

    def _get(self, endpoint, params=None):
        data, rid = self.client.get(endpoint, params)
        return data, rid, self.clock()

    def _items(self, data, endpoint, rid):
        if not isinstance(data, dict) or not isinstance(data.get("item"), list):
            self._payload_error(endpoint, rid)
        return data["item"]

    def _timestamp(self, data, endpoint, rid):
        if "timestamp" not in data:
            self._payload_error(endpoint, rid)
        if data["timestamp"] is None:
            return None
        try:
            return from_ms(data["timestamp"])
        except (ValueError, OverflowError, OSError):
            self._payload_error(endpoint, rid)

    @staticmethod
    def _fatal(issue):
        if issue.category == "authentication_error" or issue.business_code == 4001:
            raise DataProviderError(issue) from None

    def get_constituents(self):
        data, rid, retrieved = self._get(CONSTITUENTS, {"thscode": self.universe})
        items = self._items(data, CONSTITUENTS, rid)
        members = []
        for row in items:
            if (not isinstance(row, dict) or not isinstance(row.get("thscode"), str)
                    or not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", row["thscode"])
                    or not isinstance(row.get("name"), str) or not row["name"].strip()):
                self._payload_error(CONSTITUENTS, rid)
            members.append({"thscode": row["thscode"], "name": row["name"]})
        if not members or len({m["thscode"] for m in members}) != len(members):
            self._payload_error(CONSTITUENTS, rid)
        evidence = Evidence(provider=self.name, field="current_constituents:000300.SH", raw_value=members,
                            unit="members", retrieved_at=retrieved,
                            data_as_of=self._timestamp(data, CONSTITUENTS, rid), request_id=rid)
        return members, evidence

    def _calendar(self):
        data, rid, retrieved = self._get(CALENDAR)
        dates = []
        for row in self._items(data, CALENDAR, rid):
            try:
                dt = from_ms(row["date_ms"])
                text = dt.astimezone(SHANGHAI).strftime("%Y%m%d")
                if row["date"] != text:
                    raise ValueError("日期不匹配")
                if text < self.clock().astimezone(SHANGHAI).strftime("%Y%m%d"):
                    dates.append(row["date_ms"])
            except (TypeError, KeyError, ValueError, OverflowError, OSError):
                self._payload_error(CALENDAR, rid)
        if len(dates) != len(set(dates)):
            self._payload_error(CALENDAR, rid)
        dates = sorted(dates)[-61:]
        evidence = Evidence(provider=self.name, field="trading_days", raw_value=dates, unit="dates_ms",
                            retrieved_at=retrieved, data_as_of=self._timestamp(data, CALENDAR, rid), request_id=rid)
        return dates, evidence

    def _observation(self, metric, raw, *, retrieved, rid=None, as_of=None, report=None, issue=None,
                     field=None, calculation=None, adjustment=None, normalized=None, inputs=None, request_performed=True):
        value = normalized
        if calculation is None and issue is None:
            try:
                value = numeric(raw)
            except ValueError:
                issue = self._issue("invalid_payload", FINANCIALS if metric in FINANCIAL_FIELDS else VALUATIONS,
                                    metric=metric, request_id=rid)
        if value is None and issue is None:
            issue = self._issue("missing_data", HISTORY if metric == Metric.volatility_60d else
                                FINANCIALS if metric in FINANCIAL_FIELDS else VALUATIONS, metric=metric, request_id=rid)
        evidence = Evidence(provider=self.name, field=field or metric.value, raw_value=raw,
                            normalized_value=value, unit=METRIC_INFO[metric][1], retrieved_at=retrieved,
                            data_as_of=as_of, reporting_period=report, request_id=rid,
                            calculation_method=calculation, adjustment=adjustment, error=issue,
                            calculation_inputs=inputs or {}, request_performed=request_performed)
        return Observation(metric=metric, value=value, unit=METRIC_INFO[metric][1], data_source=self.name,
                           retrieved_at=retrieved, reporting_period=report, evidence=evidence,
                           missing_reason=issue.message if issue else None)

    def _financials(self, symbol):
        data, rid, retrieved = self._get(FINANCIALS, {"thscode": symbol, "report": self.report})
        if data.get("thscode") != symbol or data.get("report") != self.report or not isinstance(data.get("abilities"), list):
            self._payload_error(FINANCIALS, rid)
        fields = {}
        for ability in data["abilities"]:
            if not isinstance(ability, dict) or not isinstance(ability.get("indicators"), list):
                self._payload_error(FINANCIALS, rid)
            for item in ability["indicators"]:
                if not isinstance(item, dict) or not isinstance(item.get("index_id"), str) or "value" not in item:
                    self._payload_error(FINANCIALS, rid)
                if item["index_id"] in fields:
                    self._payload_error(FINANCIALS, rid)
                fields[item["index_id"]] = item["value"]
        # Documented financial indicators have no publication/as-of timestamp.
        return {metric: self._observation(metric, fields.get(field), retrieved=retrieved, rid=rid,
                                         report=self.report, field=field) for metric, field in FINANCIAL_FIELDS.items()}

    def _valuations(self, symbols):
        data, rid, retrieved = self._get(VALUATIONS, {"thscodes": ",".join(symbols)})
        items = self._items(data, VALUATIONS, rid)
        if type(data.get("total")) is not int or data["total"] != len(items):
            self._payload_error(VALUATIONS, rid)
        rows = {}
        for row in items:
            if (not isinstance(row, dict) or row.get("thscode") not in symbols or "pe_ttm" not in row
                    or row["thscode"] in rows):
                self._payload_error(VALUATIONS, rid)
            rows[row["thscode"]] = row
        as_of = self._timestamp(data, VALUATIONS, rid)
        return {s: self._observation(Metric.pe_ttm, rows.get(s, {}).get("pe_ttm"), retrieved=retrieved,
                                    rid=rid, as_of=as_of, field="pe_ttm") for s in symbols}

    def _volatility(self, symbol, dates):
        if len(dates) < 61:
            return self._observation(Metric.volatility_60d, None, retrieved=self.clock(), field="close_price",
                                     calculation=VOLATILITY_METHOD, adjustment="forward",
                                     request_performed=False, inputs={"expected_calendar_dates":dates},
                                     issue=self._issue("missing_data", CALENDAR, symbol=symbol,
                                                       message="官方交易日历不足61日，不能计算60个日收益率"))
        data, rid, retrieved = self._get(HISTORY, {"thscode":symbol, "interval":"1d", "start":dates[0],
                                                 "end":dates[-1] + 86400000 - 1, "adjust":"forward"})
        rows, raw = {}, []
        for row in self._items(data, HISTORY, rid):
            if not isinstance(row, dict) or "date_ms" not in row or "close_price" not in row:
                self._payload_error(HISTORY, rid)
            stamp = row["date_ms"]
            try:
                from_ms(stamp)
            except (ValueError, OverflowError, OSError):
                self._payload_error(HISTORY, rid)
            if stamp in rows or stamp not in dates:
                self._payload_error(HISTORY, rid)
            rows[stamp] = row["close_price"]
            raw.append({"date_ms":stamp, "close_price":row["close_price"]})
        period = f"{from_ms(dates[0]).astimezone(SHANGHAI):%Y-%m-%d}~{from_ms(dates[-1]).astimezone(SHANGHAI):%Y-%m-%d}; 61 closes / 60 returns"
        issue, result = None, None
        try:
            closes = [numeric(rows.get(d)) for d in dates]
            if any(p is None for p in closes):
                raise InsufficientHistory("窗口中有缺失交易日或收盘价，不能计算")
            result = annualized_volatility(closes)
        except InsufficientHistory:
            issue = self._issue("missing_data", HISTORY, symbol=symbol, request_id=rid,
                                message="历史有效数据不足完整61个收盘价/60个日收益率；未缩短窗口")
        except ValueError:
            issue = self._issue("invalid_payload", HISTORY, symbol=symbol, request_id=rid)
        return self._observation(Metric.volatility_60d, raw, retrieved=retrieved, rid=rid,
                                 as_of=self._timestamp(data, HISTORY, rid), report=period, field="close_price",
                                 calculation=VOLATILITY_METHOD, adjustment="forward", normalized=result, issue=issue,
                                 inputs={"expected_calendar_dates":dates, "window_returns":60, "ddof":1, "annualization":252})

    def fetch_universe(self, universe):
        return self.fetch_snapshot(universe).stocks

    def fetch_snapshot(self, universe, progress=None):
        if universe != self.universe:
            raise ValueError("扶摇Provider只允许官方沪深300指数000300.SH")
        if not self.client.configured:
            self.client.fail("authentication_error", CONSTITUENTS)
        if not re.fullmatch(r"\d{4}-[1-4]", self.report):
            raise DataProviderError(self._issue("invalid_payload", FINANCIALS,
                                               message="请显式配置FUYAO_REPORT（YYYY-1/2/3/4），不能猜测最新报告期"))
        members, universe_evidence = self.get_constituents()
        return self.collect_members(members, universe_evidence, progress=progress)

    def collect_members(self, members, universe_evidence, *, progress=None):
        """Main path passes ALL official members. Smoke samples must label their scope."""
        symbols = [m["thscode"] for m in members]
        if progress:
            progress(len(symbols), 0)
        global_issues = []
        dates, calendar_evidence, calendar_error = [], None, None
        try:
            dates, calendar_evidence = self._calendar()
        except DataProviderError as exc:
            self._fatal(exc.issue)
            calendar_error = exc.issue
            global_issues.append(exc.issue)
        valuations, valuation_permission = {}, None
        for start in range(0, len(symbols), 100):
            batch = symbols[start:start+100]
            skipped = valuation_permission is not None
            try:
                if valuation_permission:
                    raise DataProviderError(valuation_permission)
                valuations.update(self._valuations(batch))
            except DataProviderError as exc:
                self._fatal(exc.issue)
                if exc.issue.category == "permission_error":
                    valuation_permission = exc.issue
                for symbol in batch:
                    valuations[symbol] = self._observation(Metric.pe_ttm, None, retrieved=self.clock(),
                        rid=exc.issue.request_id if not skipped else None, request_performed=not skipped,
                        issue=exc.issue.model_copy(update={"symbol":symbol}))
        stocks, financial_permission, history_permission = [], None, None
        for index, member in enumerate(members):
            symbol = member["thscode"]
            observations = {Metric.pe_ttm: valuations[symbol]}
            skipped = financial_permission is not None
            try:
                if financial_permission:
                    raise DataProviderError(financial_permission)
                observations.update(self._financials(symbol))
            except DataProviderError as exc:
                self._fatal(exc.issue)
                if exc.issue.category == "permission_error":
                    financial_permission = exc.issue
                for metric, field in FINANCIAL_FIELDS.items():
                    observations[metric] = self._observation(metric, None, retrieved=self.clock(), field=field,
                        report=self.report, rid=exc.issue.request_id if not skipped else None, request_performed=not skipped,
                        issue=exc.issue.model_copy(update={"symbol":symbol, "metric":metric}))
            skipped = calendar_error is not None or history_permission is not None
            try:
                if calendar_error or history_permission:
                    raise DataProviderError(calendar_error or history_permission)
                observations[Metric.volatility_60d] = self._volatility(symbol, dates)
            except DataProviderError as exc:
                self._fatal(exc.issue)
                if exc.issue.category == "permission_error":
                    history_permission = exc.issue
                observations[Metric.volatility_60d] = self._observation(Metric.volatility_60d, None,
                    retrieved=self.clock(), field="close_price", calculation=VOLATILITY_METHOD,
                    adjustment="forward", rid=exc.issue.request_id if not skipped else None, request_performed=not skipped,
                    issue=exc.issue.model_copy(update={"symbol":symbol, "metric":Metric.volatility_60d}))
            stocks.append(StockData(symbol=symbol, name=member["name"], observations=observations))
            if progress:
                progress(len(symbols), index+1)
        issues = global_issues + [o.evidence.error.model_copy(update={"symbol":s.symbol, "metric":o.metric})
                                  for s in stocks for o in s.observations.values() if o.evidence.error]
        times = [o.evidence.data_as_of for s in stocks for o in s.observations.values() if o.evidence.data_as_of]
        return DataSnapshot(universe=self.universe, provider=self.name, data_mode=self.data_mode,
            captured_at=self.clock(), data_as_of=max(times) if times else None, stocks=stocks,
            universe_evidence=universe_evidence, calendar_evidence=calendar_evidence, issues=issues,
            parameters={"report":self.report, "adjust":"forward", "returns":60, "calendar_days":61,
                        "exclude_current_shanghai_day":True, "scope":"full_official_constituents", "universe_size":len(symbols),
                        "volatility_definition":"simple-sample-60-252-percent-v1"})

    def close(self):
        self.client.close()
