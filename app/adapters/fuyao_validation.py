"""Bounded REAL validation scope, using the existing Fuyao contracts and calculations."""
from app.adapters.fuyao_financial import FuyaoFinancialDataProvider, FINANCIAL_FIELDS, HISTORY, from_ms, SHANGHAI
from app.domain.models import Metric

SAMPLE_SCOPE = 'real_validation_sample_10'
SELECTION_METHOD = 'official_thscode_ascending_first_10_v1'


class FuyaoValidationSampleProvider(FuyaoFinancialDataProvider):
    name = FuyaoFinancialDataProvider.name + ' / REAL Validation Sample'
    sample_size = 10

    def __init__(self, client=None, *, clock=None):
        kwargs = {'report': ''}
        if clock is not None: kwargs['clock'] = clock
        super().__init__(client, **kwargs)

    @property
    def ready(self):
        return self.client.configured

    @property
    def snapshot_requirements(self):
        return {**super().snapshot_requirements, 'scope': SAMPLE_SCOPE, 'sample_selection': SELECTION_METHOD}

    def _get(self, endpoint, params=None):
        data, rid, retrieved = super()._get(endpoint, params)
        # Actual daily-bar echoes must agree with the requested symbol and adjustment.
        if endpoint == HISTORY and any(data.get(field) != params[field] for field in ('thscode','interval','adjust')):
            self._payload_error(endpoint, rid)
        return data, rid, retrieved

    def _financials(self, symbol):
        # Contract mismatch is unresolved. No financial alias, request, or Mock substitution.
        return {metric:self._observation(metric, None, retrieved=self.clock(), field=field,
            request_performed=False, issue=self._issue('missing_data', '/api/a-share/financials/indicators',
                symbol=symbol, metric=metric, message='财务字段契约尚未验证；本次真实验证样本未请求该指标，不做别名映射'))
            for metric,field in FINANCIAL_FIELDS.items()}

    def _volatility(self, symbol, dates):
        observation = super()._volatility(symbol, dates)
        evidence = observation.evidence
        rows = evidence.raw_value if isinstance(evidence.raw_value,list) else []
        used = sorted(row['date_ms'] for row in rows)
        evidence.calculation_inputs.update(used_trading_dates=used, close_count=len(used),
            return_count=60 if observation.value is not None else None,
            effective_start=from_ms(used[0]).astimezone(SHANGHAI).date().isoformat() if used else None,
            effective_end=from_ms(used[-1]).astimezone(SHANGHAI).date().isoformat() if used else None)
        return observation

    def fetch_snapshot(self, universe, progress=None):
        if universe != self.universe: raise ValueError('验证样本仅允许官方沪深300 000300.SH')
        members, evidence = self.get_constituents()
        if len(members) < self.sample_size: self._payload_error('/api/a-share-index/constituents/ths-stock-list', evidence.request_id)
        chosen = sorted(members, key=lambda member:member['thscode'])[:self.sample_size]
        symbols = [member['thscode'] for member in chosen]
        evidence.calculation_method = SELECTION_METHOD
        evidence.calculation_inputs.update(official_universe_size=len(members), selected_symbols=symbols,
            scope=SAMPLE_SCOPE, note='当前指取数时官方返回的成分；不代表完整沪深300筛选')
        snapshot = self.collect_members(chosen, evidence, progress=progress)
        snapshot.parameters.update(scope=SAMPLE_SCOPE, sample_selection=SELECTION_METHOD,
            sample_symbols=symbols, sample_size=self.sample_size, official_universe_size=len(members),
            financial_contract='unverified_not_requested', supported_live_metrics=['pe_ttm','volatility_60d'])
        return snapshot
