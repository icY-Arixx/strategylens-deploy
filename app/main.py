import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.financial_base import DataProviderError, FinancialDataProvider
from app.adapters.fuyao_financial import FuyaoFinancialDataProvider
from app.adapters.fuyao_validation import FuyaoValidationSampleProvider, SAMPLE_SCOPE
from app.adapters.mock_financial import MockFinancialDataProvider
from app.api import screening, strategy, compiler as compiler_api
from app.services.llm_provider import CompilerError
from app.services.llm_compiler import LLMStrategyCompiler
from app.services.strategy_compiler import DemoStrategyCompiler
from app.services.session_service import InvalidStrategy, SessionService
from app.domain.models import DataSnapshot, Execution
from app.store.sqlite_store import RevisionConflict, SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


def create_app(db_path: str | Path | None = None, provider: FinancialDataProvider | None = None, compiler=None):
    @asynccontextmanager
    async def lifespan(app):
        configured = Path(db_path or os.getenv("STRATEGYLENS_DB", "data/strategylens.sqlite3"))
        configured = configured if configured.is_absolute() else ROOT / configured
        selected = provider
        if selected is None:
            mode = os.getenv("STRATEGYLENS_PROVIDER", "fuyao_validation")
            if mode not in ("mock", "fuyao", "fuyao_validation"):
                raise ValueError("STRATEGYLENS_PROVIDER仅允许mock、fuyao_validation或显式fuyao")
            selected = MockFinancialDataProvider() if mode == "mock" else FuyaoValidationSampleProvider() if mode == "fuyao_validation" else FuyaoFinancialDataProvider()
        mode = os.getenv("STRATEGYLENS_COMPILER","demo")
        if mode not in ("demo","llm"): raise ValueError("STRATEGYLENS_COMPILER仅允许demo/llm")
        chosen = compiler if compiler is not None else LLMStrategyCompiler() if mode == "llm" else DemoStrategyCompiler()
        app.state.compiler_secret = secrets.token_bytes(32)
        app.state.sessions = SessionService(SQLiteStore(configured), selected, chosen)
        try:
            yield
        finally:
            compiler_close = getattr(chosen,"close",None)
            if compiler_close: compiler_close()
            close = getattr(selected, "close", None)
            if close:
                close()

    application = FastAPI(title="StrategyLens｜自然语言智能选股与策略解释器", version="0.2.0", lifespan=lifespan)

    @application.exception_handler(DataProviderError)
    async def data_failure(request: Request, exc: DataProviderError):
        return JSONResponse(status_code=504 if exc.issue.category == "timeout" else 502,
                            content={"detail":exc.issue.message, "category":exc.issue.category,
                                     "issue":exc.issue.model_dump(mode="json"), "run_id":getattr(exc, "run_id", None)})

    @application.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError):
        return JSONResponse(status_code=404, content={"detail": "策略不存在"})

    @application.exception_handler(RevisionConflict)
    async def revision_conflict(request: Request, exc: RevisionConflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(InvalidStrategy)
    async def invalid_strategy(request: Request, exc: InvalidStrategy):
        return JSONResponse(status_code=422, content={"detail": str(exc),
                            "conflicts": [c.model_dump(mode="json") for c in exc.conflicts]})

    @application.exception_handler(ValueError)
    async def bad_value(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @application.exception_handler(CompilerError)
    async def compiler_failure(request: Request, exc: CompilerError):
        return JSONResponse(status_code=504 if exc.category=="llm_timeout" else 422 if exc.category in ("invalid_structured_output","unsupported_intent","invalid_patch_proposal") else 502,
            content={"category":exc.category,"detail":exc.category})

    application.include_router(compiler_api.router)
    application.include_router(strategy.router)
    application.include_router(screening.router)
    application.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    @application.get("/api/health")
    def health(request: Request):
        selected = request.app.state.sessions.provider
        return {"status":"ok", "data_mode":selected.data_mode, "compiler":"llm" if isinstance(request.app.state.sessions.compiler,LLMStrategyCompiler) else "fixed_demo_template"}

    @application.get("/api/config")
    def config(request: Request):
        selected = request.app.state.sessions.provider
        return {"product_name":"StrategyLens｜自然语言智能选股与策略解释器",
                "provider":selected.name, "data_mode":selected.data_mode, "universe":selected.universe,
                "ready":getattr(selected, "ready", True),
                "screening_scope":SAMPLE_SCOPE if isinstance(selected,FuyaoValidationSampleProvider) else None,
                "financial_report":selected.report if isinstance(selected, FuyaoFinancialDataProvider) and selected.ready else None,
                "compiler":"llm" if isinstance(request.app.state.sessions.compiler,LLMStrategyCompiler) else "fixed_demo_template",
                "runtime_llm":isinstance(request.app.state.sessions.compiler,LLMStrategyCompiler),
                "llm_ready":bool(getattr(getattr(request.app.state.sessions.compiler,"provider",None),"ready",False))}

    @application.get("/api/snapshots/{snapshot_id}", response_model=DataSnapshot)
    def read_snapshot(snapshot_id: str, request: Request):
        return request.app.state.sessions.store.read_snapshot(snapshot_id)

    @application.get("/api/executions/{execution_id}", response_model=Execution)
    def read_execution(execution_id: str, request: Request):
        return request.app.state.sessions.store.read_execution(execution_id)

    return application


app = create_app()
