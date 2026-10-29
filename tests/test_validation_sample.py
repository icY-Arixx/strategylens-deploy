"""Offline synthetic fixtures; never described as current official constituents."""
import httpx
import pytest
from test_fuyao import OfficialContractFixture, envelope, TEST_CREDENTIAL, CLOCK, DAYS, CLOSES
from app.adapters.fuyao_client import FuyaoClient
from app.adapters.fuyao_financial import HISTORY, FINANCIALS
from app.adapters.fuyao_validation import FuyaoValidationSampleProvider, SAMPLE_SCOPE
from app.adapters.financial_base import DataProviderError
from app.domain.models import Metric


def fixture_provider(count=13,adjust='forward',key=TEST_CREDENTIAL):
    fixture=OfficialContractFixture();fixture.symbols=[f'{600000+i:06d}.SH' for i in range(count,0,-1)]
    def respond(request):
        if request.url.path==HISTORY:
            fixture.calls.append(request)
            return envelope({'timestamp':DAYS[-1],'thscode':request.url.params['thscode'],'interval':'1d','adjust':adjust,
                'item':[{'date_ms':d,'close_price':p} for d,p in zip(DAYS,CLOSES)]})
        return fixture(request)
    client=FuyaoClient(key,transport=httpx.MockTransport(respond),min_interval=0)
    return FuyaoValidationSampleProvider(client,clock=lambda:CLOCK),fixture


def test_bounded_sample_is_official_sorted_and_never_calls_finance():
    provider,fixture=fixture_provider()
    try:
        snapshot=provider.fetch_snapshot('000300.SH')
        assert len(snapshot.stocks)==10 and len(snapshot.universe_evidence.raw_value)==13
        assert [s.symbol for s in snapshot.stocks]==sorted(fixture.symbols)[:10]
        assert snapshot.parameters['scope']==SAMPLE_SCOPE and snapshot.parameters['official_universe_size']==13
        assert len(fixture.calls)==13 and all(r.url.path!=FINANCIALS for r in fixture.calls)
        for stock in snapshot.stocks:
            vol=stock.observations[Metric.volatility_60d]
            assert vol.value is not None and vol.evidence.calculation_inputs['close_count']==61
            assert vol.evidence.calculation_inputs['return_count']==60 and vol.evidence.adjustment=='forward'
            fin=stock.observations[Metric.revenue_yoy]
            assert fin.value is None and not fin.evidence.request_performed and fin.evidence.request_id is None
    finally:provider.close()


def test_adjustment_echo_mismatch_is_unknown_not_a_calculated_fact():
    provider,_=fixture_provider(adjust='backward')
    try:
        snapshot=provider.fetch_snapshot('000300.SH')
        assert all(s.observations[Metric.volatility_60d].value is None for s in snapshot.stocks)
        assert all(s.observations[Metric.volatility_60d].evidence.error.category=='invalid_payload' for s in snapshot.stocks)
    finally:provider.close()


def test_insufficient_official_members_blocks_instead_of_filling_mock():
    provider,fixture=fixture_provider(count=9)
    try:
        with pytest.raises(DataProviderError):provider.fetch_snapshot('000300.SH')
        assert len(fixture.calls)==1
    finally:provider.close()


def test_sample_snapshot_scope_is_required_for_reuse():
    provider,_=fixture_provider()
    try:
        assert provider.snapshot_requirements['scope']==SAMPLE_SCOPE
        assert provider.snapshot_requirements['sample_selection']=='official_thscode_ascending_first_10_v1'
        assert provider.ready and provider.report==''
    finally:provider.close()


def test_missing_key_does_not_call_network_or_mock():
    provider,fixture=fixture_provider(key='')
    try:
        with pytest.raises(DataProviderError) as error:provider.fetch_snapshot('000300.SH')
        assert error.value.issue.category=='authentication_error' and not fixture.calls
    finally:provider.close()
