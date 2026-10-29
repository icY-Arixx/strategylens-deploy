"""Explicit single-symbol LIVE probe. No universe fetch, no fallback, no retries."""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.adapters.fuyao_client import FuyaoClient
from app.adapters.fuyao_financial import FuyaoFinancialDataProvider, HISTORY, VALUATIONS, FINANCIALS, numeric, from_ms
from app.adapters.financial_base import DataProviderError

class ContractMismatch(ValueError):
    pass


SH = timezone(timedelta(hours=8))
SYMBOL = '300033.SZ'
REPORT = '2026-2'


def main():
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('httpcore').setLevel(logging.CRITICAL)
    root = Path(__file__).resolve().parents[1]
    out = root/'artifacts'/'single-stock-live-20261029.json'
    started = time.perf_counter()
    report = {'test_type':'LIVE', 'scope':'single_explicit_symbol', 'symbol':SYMBOL,
              'financial_report':REPORT, 'report_selection':'explicit historical interim period, not asserted latest',
              'started_at':datetime.now(SH).isoformat(), 'key_present':bool(os.getenv('HITHINK_FINANCE_API_KEY','').strip()),
              'full_universe_requested':False, 'requests':[], 'status':'not_verified'}
    client = FuyaoClient(timeout=20, min_interval=1)
    provider = FuyaoFinancialDataProvider(client,report=REPORT)
    active = None
    def clean(value):
        value = client.redact(value)
        if isinstance(value, dict):
            return {k:('[REDACTED]' if any(word in k.lower().replace('-','').replace('_','') for word in ('apikey','authorization','cookie','accesstoken')) else clean(v)) for k,v in value.items()}
        if isinstance(value,list): return [clean(v) for v in value]
        return value
    def capture(response):
        response.read()
        active['http_status'] = response.status_code
        active['received_at'] = datetime.now(SH).isoformat()
        try:
            payload = clean(response.json())
        except ValueError:
            active['response_format'] = 'non_json'
            active['response_bytes'] = len(response.content)
            return
        active['raw_response'] = payload
        if isinstance(payload,dict):
            active['business_code'] = payload.get('code')
            active['upstream_message'] = payload.get('message')
            active['request_id'] = payload.get('request_id')
            active['envelope_fields'] = sorted(payload)
            data = payload.get('data')
            active['data_fields'] = sorted(data) if isinstance(data,dict) else None
    # Observe only sanitized response bodies/status; never headers or request objects.
    client._http.event_hooks['response'].append(capture)
    def step(name, endpoint, params, operation):
        nonlocal active
        active = {'capability':name,'endpoint':endpoint,'params':params,'started_at':datetime.now(SH).isoformat()}
        report['requests'].append(active)
        begin = time.perf_counter()
        try:
            result = operation()
            active.update(status='completed', result=clean(result))
            return True
        except ContractMismatch:
            active.update(status='contract_mismatch',issue={'category':'invalid_payload','message':'Official documented financial index_ids absent; no alias mapping applied; normalized metrics remain Unknown'})
        except DataProviderError as exc:
            active.update(status='failed',issue=exc.issue.model_dump(mode='json'))
        except (ValueError,KeyError,TypeError,OverflowError):
            active.update(status='failed',issue={'category':'invalid_payload','message':'Returned data failed single-stock contract validation'})
        finally:
            active['elapsed_seconds'] = round(time.perf_counter()-begin,3)
            active['completed_at'] = datetime.now(SH).isoformat()
        return False
    start = int(datetime(2026,10,20,tzinfo=SH).timestamp()*1000)
    end = int(datetime(2026,10,29,tzinfo=SH).timestamp()*1000)-1
    params = {'thscode':SYMBOL,'interval':'1d','start':start,'end':end,'adjust':'forward'}
    def prices():
        data,rid = client.get(HISTORY,params)
        if data.get('thscode') != SYMBOL or data.get('interval') != '1d' or data.get('adjust') != 'forward':
            raise ValueError('price echo mismatch')
        rows = provider._items(data,HISTORY,rid)
        if not rows: raise ValueError('empty history')
        for row in rows:
            stamp = row['date_ms']
            from_ms(stamp)
            if not start <= stamp <= end or numeric(row['close_price']) is None: raise ValueError('invalid price')
        return {'row_count':len(rows),'row_fields':sorted(set().union(*(row.keys() for row in rows))),
                'data_as_of':provider._timestamp(data,HISTORY,rid),
                'latest_bar_at':from_ms(max(row['date_ms'] for row in rows)),
                'latest_bar':max(rows,key=lambda row:row['date_ms']), 'adjustment':'forward',
                'interpretation':'historical daily bars, not realtime tick; short window, no volatility calculation'}
    def financials():
        result = {metric.value:obs.model_dump(mode='json') for metric,obs in provider._financials(SYMBOL).items()}
        # Compare exact contract IDs. Similar-looking upstream IDs are not safe aliases.
        data = active['raw_response']['data']
        fields = {item['index_id']:item['value'] for block in data['abilities'] for item in block['indicators']}
        expected = ['operating_income_yoy_growth_ratio','net_profit_yoy_growth_ratio']
        active['expected_field_presence'] = {field:field in fields for field in expected}
        active['observed_growth_indicators'] = [item for block in data['abilities'] if block.get('ability')=='growth' for item in block['indicators']]
        active['normalized_result'] = clean(result)
        if not all(field in fields for field in expected):
            raise ContractMismatch()
        return result
    try:
        if not report['key_present']:
            report['reason'] = 'key absent; no requests'
        elif not step('daily_price_history',HISTORY,params,prices):
            report.update(status='failed',stop_reason='price request failed; PE and financials not requested')
        else:
            pe_ok = step('pe_ttm',VALUATIONS,{'thscodes':SYMBOL},lambda:provider._valuations([SYMBOL])[SYMBOL].model_dump(mode='json'))
            fin_ok = False
            # Authentication failure/rate limit stops immediately. Other per-capability failures remain explicit.
            issue = active.get('issue',{})
            if not pe_ok and (issue.get('category')=='authentication_error' or issue.get('business_code')==4001):
                report['stop_reason'] = 'PE authentication/rate-limit failure; financials not requested'
            else:
                fin_ok = step('financial_growth',FINANCIALS,{'thscode':SYMBOL,'report':REPORT},
                    financials)
            report['status'] = 'completed' if pe_ok and fin_ok else 'partial_failure'
    finally:
        report['elapsed_seconds'] = round(time.perf_counter()-started,3)
        report['completed_at'] = datetime.now(SH).isoformat()
        # No credential is included; sanitize once more immediately before serialization.
        content = json.dumps(clean(report),ensure_ascii=False,indent=2,default=lambda value:value.isoformat())
        secret = os.getenv('HITHINK_FINANCE_API_KEY','')
        if secret and secret in content: raise RuntimeError('Credential safety guard blocked report')
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(content,encoding='utf-8')
        provider.close()
    summary = {k:report[k] for k in ('test_type','scope','symbol','status','elapsed_seconds','full_universe_requested')}
    summary['requests'] = [{k:r.get(k) for k in ('capability','http_status','business_code','request_id','status','elapsed_seconds','issue')} for r in report['requests']]
    print(json.dumps(clean(summary),ensure_ascii=False,indent=2))
    return 0 if report['status']=='completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
