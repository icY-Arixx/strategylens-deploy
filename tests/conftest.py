import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.adapters.mock_financial import MockFinancialDataProvider
from app.services.strategy_compiler import StrategyCompiler


@pytest.fixture
def strategy():
    return StrategyCompiler().compile("帮我找沪深300里经营改善、估值合理、走势比较稳定的股票。")


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3", MockFinancialDataProvider())) as instance:
        yield instance
