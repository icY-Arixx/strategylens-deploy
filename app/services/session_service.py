import threading

from app.adapters.financial_base import DataProviderError, FinancialDataProvider
from app.domain.conflicts import detect_conflicts
from app.domain.models import (Condition, DataIssue, Execution, ScreeningRun, SessionSnapshot, Strategy, WhatIfDiff, now)
from app.domain.strategy_engine import StrategyEngine
from app.services.strategy_compiler import StrategyCompiler
from app.store.sqlite_store import RevisionConflict, SQLiteStore


class InvalidStrategy(Exception):
    def __init__(self, message, conflicts=None):
        super().__init__(message)
        self.conflicts = conflicts or []


def calculate_diff(previous: Execution | None, results, revision: int, snapshot_id: str | None = None) -> WhatIfDiff | None:
    if previous is None:
        return None
    old = {r.symbol for r in previous.results if r.status == "selected"}
    new = {r.symbol for r in results if r.status == "selected"}
    return WhatIfDiff(previous_execution_id=previous.execution_id, previous_revision=previous.revision,
                      current_revision=revision, previous_count=len(old), current_count=len(new),
                      added=sorted(new - old), removed=sorted(old - new),
                      previous_snapshot_id=previous.snapshot_id, current_snapshot_id=snapshot_id,
                      condition_attributable=bool(snapshot_id and previous.snapshot_id == snapshot_id),
                      attribution_note="条件变化可归因：复用同一不可变数据快照" if snapshot_id and previous.snapshot_id == snapshot_id
                      else "本次比较同时存在数据快照变化。" if previous.snapshot_id and snapshot_id
                      else "历史执行没有快照标识，无法归因")


class SessionService:
    def __init__(self, store: SQLiteStore, provider: FinancialDataProvider, compiler=None):
        self.store, self.provider = store, provider
        self.compiler = compiler or StrategyCompiler()
        self.engine = StrategyEngine()
        self._execution_lock = threading.Lock()

    def snapshot(self, strategy, execution, latest_run=None):
        if latest_run is None:
            latest_run = self.store.read_state(strategy.strategy_id)[2]
        return SessionSnapshot(strategy=strategy, latest_execution=execution,
                               results_stale=execution is not None and (
                                   strategy.status != "executed" or execution.revision != strategy.revision
                                   or execution.snapshot_id is None or bool(latest_run and latest_run.status == "failed")),
                               conflicts=detect_conflicts(strategy.conditions), latest_run=latest_run)

    def create(self, text: str):
        if getattr(self.compiler,"mode","demo") == "llm":
            from app.services.llm_provider import CompilerError
            raise CompilerError("unsupported_intent")
        strategy = self.compiler.compile(text)
        strategy.universe = self.provider.universe
        self.store.create(strategy)
        return self.snapshot(strategy, None)

    def get(self, strategy_id: str):
        return self.snapshot(*self.store.read_state(strategy_id))

    @staticmethod
    def check_revision(strategy, expected_revision):
        if strategy.revision != expected_revision:
            raise RevisionConflict("策略版本已变化，请刷新后重试")

    def update(self, strategy_id: str, expected_revision: int, conditions: list[Condition]):
        original, execution = self.store.read(strategy_id)
        self.check_revision(original, expected_revision)
        # Schema validation must also cover list-level invariants before persistence.
        Strategy.model_validate({**original.model_dump(), "conditions": conditions})
        if conditions == original.conditions:
            return self.snapshot(original, execution)
        previous = {c.condition_id: c for c in original.conditions}
        normalized = []
        for c in conditions:
            if c.condition_id not in previous or c != previous[c.condition_id]:
                c = c.model_copy(update={"origin": "user_explicit", "rationale": "用户在结构化条件编辑中修改；以当前条件为准"})
            normalized.append(c)
        updated = original.model_copy(update={"conditions": normalized, "revision": original.revision + 1,
                                              "status": "stale" if execution else "draft", "updated_at": now()})
        self.store.save(original, updated)
        return self.snapshot(updated, execution)

    @staticmethod
    def assert_executable(strategy: Strategy):
        conflicts = detect_conflicts(strategy.conditions)
        if conflicts:
            raise InvalidStrategy("条件范围冲突，请修改后执行", conflicts)
        if not any(c.enabled for c in strategy.conditions):
            raise InvalidStrategy("至少启用一个条件才能执行")

    def validate(self, strategy_id: str, expected_revision: int):
        original, execution = self.store.read(strategy_id)
        self.check_revision(original, expected_revision)
        self.assert_executable(original)
        if original.status in ("stale", "executed", "validated"):
            return self.snapshot(original, execution)
        updated = original.model_copy(update={"status": "validated", "updated_at": now()})
        self.store.save(original, updated)
        return self.snapshot(updated, execution)

    def execute(self, strategy_id: str, expected_revision: int, *, refresh_data=False, snapshot_id=None):
        if not self._execution_lock.acquire(blocking=False):
            raise RevisionConflict("已有筛选正在取数；本机单进程串行执行，请稍后重试")
        try:
            return self._execute(strategy_id, expected_revision, refresh_data=refresh_data, snapshot_id=snapshot_id)
        finally:
            self._execution_lock.release()

    def _execute(self, strategy_id, expected_revision, *, refresh_data, snapshot_id):
        original, previous = self.store.read(strategy_id)
        self.check_revision(original, expected_revision)
        self.assert_executable(original)
        run = ScreeningRun(strategy_id=strategy_id, strategy_revision=original.revision,
                           universe=original.universe, provider=self.provider.name)
        self.store.save_run(run)
        try:
            if original.universe != self.provider.universe:
                raise DataProviderError(DataIssue(category="invalid_payload", provider=self.provider.name,
                    message="当前策略的股票池与运行模式不同，请重新生成策略；不会互相回退"))
            if refresh_data and snapshot_id:
                raise InvalidStrategy("refresh_data与snapshot_id不能同时指定")
            reusable = snapshot_id or (previous.snapshot_id if previous and not refresh_data else None)
            if reusable:
                snapshot = self.store.read_snapshot(reusable)
                if (snapshot.universe != original.universe or snapshot.provider != self.provider.name
                        or snapshot.data_mode != self.provider.data_mode):
                    raise InvalidStrategy("快照股票池、Provider或模式与当前策略不匹配")
                required = getattr(self.provider, "snapshot_requirements", {})
                if any(snapshot.parameters.get(key) != value for key, value in required.items()):
                    raise InvalidStrategy("快照报告期/计算口径与当前配置不同，请勾选重新获取数据快照")
                run.snapshot_reused = True
            else:
                def progress(total, processed):
                    run.universe_size, run.processed_count = total, processed
                    self.store.save_run(run)
                snapshot = self.provider.fetch_snapshot(original.universe, progress=progress)
                if (snapshot.universe != original.universe or snapshot.provider != self.provider.name
                        or snapshot.data_mode != self.provider.data_mode):
                    raise InvalidStrategy("Provider返回的快照模式/股票池/来源不匹配")
                snapshot = self.store.save_snapshot(snapshot)
            run.snapshot_id, run.data_as_of = snapshot.snapshot_id, snapshot.data_as_of
            run.universe_size = run.processed_count = len(snapshot.stocks)
            run.issues = snapshot.issues
            results = self.engine.evaluate(original, snapshot.stocks)
            run.selected_count = sum(r.status == "selected" for r in results)
            run.excluded_count = sum(r.status == "excluded" for r in results)
            run.unknown_count = sum(r.status == "unknown" for r in results)
            run.completed_at = now()
            run.status = "partial_failure" if any(i.category != "missing_data" for i in run.issues) else "completed"
            updated = original.model_copy(update={"status":"executed", "updated_at":now()})
            execution = Execution(execution_id=run.run_id, strategy_id=strategy_id, revision=original.revision,
                provider=self.provider.name, data_mode=snapshot.data_mode, strategy_snapshot=updated.model_copy(deep=True),
                results=results, snapshot_id=snapshot.snapshot_id, run=run,
                diff=calculate_diff(previous, results, original.revision, snapshot.snapshot_id))
            self.store.save(original, updated, execution)
            return self.snapshot(updated, execution, run)
        except Exception as exc:
            run.status, run.completed_at = "failed", now()
            run.selected_count = run.excluded_count = run.unknown_count = 0
            if isinstance(exc, DataProviderError):
                run.issues = [exc.issue]
                exc.run_id = run.run_id
            else:
                run.issues = [DataIssue(category="invalid_payload", provider=self.provider.name,
                                       message="筛选未完成；请检查请求、快照或策略版本")]
            self.store.save_run(run)
            if isinstance(exc, (DataProviderError, RevisionConflict, InvalidStrategy, KeyError)):
                raise
            raise DataProviderError(run.issues[0]) from None
