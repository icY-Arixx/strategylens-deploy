"""Shared contracts. Percent values use percentage points: 30 means 30%, not .30."""
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, JsonValue, model_validator


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class Metric(str, Enum):
    revenue_yoy = "revenue_yoy"
    net_profit_yoy = "net_profit_yoy"
    pe_ttm = "pe_ttm"
    volatility_60d = "volatility_60d"


METRIC_INFO = {
    Metric.revenue_yoy: ("营收同比", "%"),
    Metric.net_profit_yoy: ("净利润同比", "%"),
    Metric.pe_ttm: ("PE(TTM)", "x"),
    Metric.volatility_60d: ("60日年化波动率", "%"),
}
Operator = Literal[">", ">=", "<", "<=", "=="]
ConditionOrigin = Literal["user_explicit", "llm_interpreted", "system_default"]
Nonempty = Annotated[str, Field(min_length=1, max_length=200)]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class Condition(Contract):
    condition_id: Nonempty = Field(default_factory=new_id)
    concept: Nonempty
    metric: Metric
    operator: Operator
    value: Number
    unit: Literal["%", "x"]
    enabled: bool = Field(default=True, strict=True)
    origin: ConditionOrigin = Field(validation_alias=AliasChoices("origin", "source"))
    rationale: Annotated[str, Field(min_length=1, max_length=1000)]

    @model_validator(mode="after")
    def check_unit(self):
        if self.unit != METRIC_INFO[self.metric][1]:
            raise ValueError("指标与单位不匹配；百分数使用百分点，例如 30 表示 30%")
        return self


class Strategy(Contract):
    strategy_id: Nonempty = Field(default_factory=new_id)
    revision: int = Field(default=1, ge=1)
    source_text: Annotated[str, Field(min_length=1, max_length=2000)]
    universe: Literal["CSI300_DEMO", "000300.SH"] = "CSI300_DEMO"
    conditions: list[Condition] = Field(max_length=30)
    status: Literal["draft", "validated", "executed", "stale"] = "draft"
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    @model_validator(mode="after")
    def unique_conditions(self):
        ids = [c.condition_id for c in self.conditions]
        if len(ids) != len(set(ids)):
            raise ValueError("condition_id 不得重复")
        return self


ErrorCategory = Literal["authentication_error", "permission_error", "upstream_error", "timeout",
                        "missing_data", "invalid_payload", "partial_failure"]


class DataIssue(Contract):
    category: ErrorCategory
    provider: str
    message: str
    symbol: str | None = None
    metric: Metric | None = None
    endpoint: str | None = None
    request_id: str | None = None
    business_code: int | None = None


class Evidence(Contract):
    provider: str
    field: str
    raw_value: JsonValue = None
    normalized_value: Number | None = None
    unit: str
    retrieved_at: datetime
    data_as_of: datetime | None = None
    reporting_period: str | None = None
    request_id: str | None = None
    calculation_method: str | None = None
    calculation_inputs: dict[str, JsonValue] = Field(default_factory=dict)
    request_performed: bool = True
    adjustment: Literal["forward", "backward", "none"] | None = None
    error: DataIssue | None = None


class Observation(Contract):
    metric: Metric
    value: Number | None
    unit: Literal["%", "x"]
    data_source: Nonempty = Field(validation_alias=AliasChoices("data_source", "source"))
    retrieved_at: datetime
    reporting_period: Nonempty | None
    missing_reason: str | None = None
    evidence: Evidence | None = None

    @model_validator(mode="after")
    def check_unit(self):
        if self.unit != METRIC_INFO[self.metric][1]:
            raise ValueError("观测值单位与指标不匹配")
        if self.evidence and (self.evidence.normalized_value != self.value or self.evidence.unit != self.unit):
            raise ValueError("观测值与Evidence不一致")
        return self


class StockData(Contract):
    symbol: Nonempty
    name: Nonempty
    observations: dict[Metric, Observation]

    @model_validator(mode="after")
    def matching_metrics(self):
        if any(key != obs.metric for key, obs in self.observations.items()):
            raise ValueError("观测键与 metric 不匹配")
        return self


class ConditionCheck(Contract):
    condition_id: Nonempty
    metric: Metric
    status: Literal["pass", "fail", "unknown"]
    actual_value: Number | None
    threshold: Number
    operator: Operator
    unit: Literal["%", "x"]
    data_source: Nonempty = Field(validation_alias=AliasChoices("data_source", "source"))
    retrieved_at: datetime | None
    reporting_period: str | None
    reason: Nonempty
    evidence: Evidence | None = None

    @model_validator(mode="after")
    def consistent_observation(self):
        if (self.status == "unknown") != (self.actual_value is None):
            raise ValueError("unknown 必须对应缺失实际值；pass/fail 必须提供实际数值")
        if self.unit != METRIC_INFO[self.metric][1]:
            raise ValueError("检查结果单位与指标不匹配")
        if self.evidence and self.evidence.normalized_value != self.actual_value:
            raise ValueError("检查结果与Evidence不一致")
        return self


class StockResult(Contract):
    symbol: Nonempty
    name: Nonempty
    status: Literal["selected", "excluded", "unknown"]
    checks: list[ConditionCheck]
    explanation: str


class WhatIfDiff(Contract):
    previous_execution_id: str
    previous_revision: int
    current_revision: int
    previous_count: int
    current_count: int
    added: list[str]
    removed: list[str]
    previous_snapshot_id: str | None = None
    current_snapshot_id: str | None = None
    condition_attributable: bool = False
    attribution_note: str = "历史执行没有快照标识，无法归因"

    @model_validator(mode="after")
    def attribution_matches_ids(self):
        same = bool(self.current_snapshot_id and self.previous_snapshot_id == self.current_snapshot_id)
        if self.condition_attributable != same:
            raise ValueError("Diff归因与snapshot_id不一致")
        return self


class DataSnapshot(Contract):
    snapshot_id: str = Field(default_factory=new_id)
    universe: str
    provider: str
    data_mode: Literal["DEMO / MOCK", "REAL"]
    captured_at: datetime = Field(default_factory=now)
    data_as_of: datetime | None = None
    as_of_semantics: str = "各证据有独立时间；汇总值仅为最晚已知上游时间，不表示全量数据同步"
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    stocks: list[StockData]
    universe_evidence: Evidence | None = None
    calendar_evidence: Evidence | None = None
    issues: list[DataIssue] = Field(default_factory=list)
    content_hash: str = ""

    @model_validator(mode="after")
    def unique_stocks(self):
        if len({s.symbol for s in self.stocks}) != len(self.stocks):
            raise ValueError("快照股票代码重复")
        return self


class ScreeningRun(Contract):
    run_id: str = Field(default_factory=new_id)
    strategy_id: str
    strategy_revision: int = Field(ge=1)
    snapshot_id: str | None = None
    universe: str
    provider: str
    started_at: datetime = Field(default_factory=now)
    completed_at: datetime | None = None
    data_as_of: datetime | None = None
    status: Literal["running", "completed", "partial_failure", "failed"] = "running"
    selected_count: int = Field(default=0, ge=0)
    excluded_count: int = Field(default=0, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    universe_size: int = Field(default=0, ge=0)
    processed_count: int = Field(default=0, ge=0)
    snapshot_reused: bool = False
    issues: list[DataIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def completed_runs_have_snapshot(self):
        if self.completed_at and self.completed_at < self.started_at:
            raise ValueError("执行结束时间早于开始时间")
        if self.status in ("completed", "partial_failure"):
            if not self.snapshot_id or not self.completed_at:
                raise ValueError("已完成执行必须绑定快照与完成时间")
            if self.selected_count + self.excluded_count + self.unknown_count != self.universe_size:
                raise ValueError("执行结果计数与股票池数量不一致")
        return self


class Execution(Contract):
    execution_id: str = Field(default_factory=new_id)
    strategy_id: str
    revision: int
    executed_at: datetime = Field(default_factory=now)
    data_mode: Literal["DEMO / MOCK", "REAL"] = "DEMO / MOCK"
    provider: str
    strategy_snapshot: Strategy
    results: list[StockResult]
    diff: WhatIfDiff | None = None
    snapshot_id: str | None = None  # None only for preserved Phase 1 history.
    run: ScreeningRun | None = None

    @model_validator(mode="after")
    def consistent_run(self):
        if (self.snapshot_id is None) != (self.run is None):
            raise ValueError("快照与ScreeningRun必须同时存在；仅第一阶段历史允许同时缺失")
        if self.run and (self.run.run_id != self.execution_id or self.run.strategy_id != self.strategy_id
                         or self.run.strategy_revision != self.revision or self.run.snapshot_id != self.snapshot_id
                         or self.strategy_snapshot.strategy_id != self.strategy_id
                         or self.strategy_snapshot.revision != self.revision):
            raise ValueError("执行记录的策略版本/快照绑定不一致")
        if self.run and (self.run.status not in ("completed", "partial_failure") or self.run.provider != self.provider
                         or self.run.universe != self.strategy_snapshot.universe):
            raise ValueError("执行记录状态/Provider/股票池绑定不一致")
        return self


class Conflict(Contract):
    metric: Metric
    condition_ids: list[str]
    reason: str


class SessionSnapshot(Contract):
    strategy: Strategy
    latest_execution: Execution | None
    results_stale: bool
    conflicts: list[Conflict]
    latest_run: ScreeningRun | None = None
