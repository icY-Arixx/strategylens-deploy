"""Authorized final REAL sample workflow, using production HTTP routes and frozen LLM.

No full scan, no Mock provider, no financial alias mapping. Reports exclude credentials.
"""
import json
import logging
import math
import statistics
import time
from pathlib import Path

from fastapi.testclient import TestClient
from app.adapters.fuyao_validation import FuyaoValidationSampleProvider
from app.domain.models import now
from app.main import create_app
from app.services.llm_compiler import LLMStrategyCompiler
from app.services.llm_provider import SiliconFlowProvider

ROOT = Path(__file__).resolve().parents[1]
QUERY = '帮我找估值不要太高、最近走势比较稳定的股票。'
PATCH = 'PE改成20，其他不变。'


def main():
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('httpcore').setLevel(logging.CRITICAL)
    provider = FuyaoValidationSampleProvider()
    compiler = LLMStrategyCompiler(SiliconFlowProvider())
    report = {'test_type':'FINAL_REAL_WORKFLOW','status':'not_verified','started_at':now().isoformat(),
              'scope':'REAL Validation Sample / 10 current official constituents',
              'confirmation_mode':'user-authorized validation script, not an invented human click',
              'model':compiler.provider.model,'provider':provider.name,'financial_requests':[],
              'full_universe_scanned':False}
    started = time.perf_counter()

    def trace(response):
        response.read()
        record = {'endpoint':response.request.url.path,'params':dict(response.request.url.params),
                  'http_status':response.status_code,'retrieved_at':now().isoformat(),
                  'elapsed_seconds':round(time.perf_counter()-response.request.extensions['final_started'],3)}
        try:
            record['raw_response'] = provider.client.redact(response.json())
            record['request_id'] = record['raw_response'].get('request_id')
            record['business_code'] = record['raw_response'].get('code')
        except (ValueError,AttributeError): record['response_format'] = 'invalid_json_envelope'
        report['financial_requests'].append(record)

    provider.client._http.event_hooks['request'].append(lambda request:request.extensions.update(final_started=time.perf_counter()))
    provider.client._http.event_hooks['response'].append(trace)

    def require(response):
        if response.status_code != 200:
            report['http_failure'] = {'status':response.status_code,'response':response.json()}
            raise RuntimeError('workflow_request_failed')
        return response.json()

    try:
        if not provider.ready or not compiler.provider.ready:
            report['reason'] = 'Required financial or model credential missing; no fallback'
            return 2
        if compiler.provider.model != 'Qwen/Qwen3-8B': raise RuntimeError('frozen_model_mismatch')
        with TestClient(create_app(ROOT/'data/final-real.sqlite3',provider,compiler)) as client:
            compiled = require(client.post('/api/strategies/interpret',json={'source_text':QUERY}))
            report['initial_compile'] = {'response':compiled,'attempts':compiler.last_attempts}
            session = compiled['session']
            if not session: raise RuntimeError('draft_requires_clarification_or_is_blocked')
            strategy = session['strategy'];sid = strategy['strategy_id']
            assert session['latest_execution'] is None
            assert {c['metric'] for c in strategy['conditions']} == {'pe_ttm','volatility_60d'}
            assert len(strategy['conditions']) == 2 and all(c['origin']=='llm_interpreted' for c in strategy['conditions'])
            # Stop rather than execute an inverted interpretation of "not too high / stable".
            assert all(c['operator']=='<' for c in strategy['conditions']), 'draft_direction_requires_review'
            report['draft_reviewed_at'] = now().isoformat()
            first = require(client.post(f'/api/strategies/{sid}/execute',json={'expected_revision':strategy['revision']}))
            execution = first['latest_execution']
            report['first_execution'] = execution
            snapshot = require(client.get('/api/snapshots/'+execution['snapshot_id']))
            report['snapshot'] = snapshot
            assert len(snapshot['stocks']) == 10 and snapshot['data_mode']=='REAL'
            official = {row['thscode'] for row in snapshot['universe_evidence']['raw_value']}
            assert {s['symbol'] for s in snapshot['stocks']} <= official
            assert snapshot['parameters']['sample_symbols'] == sorted(official)[:10]
            for stock in snapshot['stocks']:
                observation = stock['observations']['volatility_60d'];ev = observation['evidence']
                if observation['value'] is not None:
                    closes = [float(row['close_price']) for row in sorted(ev['raw_value'],key=lambda row:row['date_ms'])]
                    assert len(closes)==61 and ev['adjustment']=='forward'
                    independently = statistics.stdev([closes[i]/closes[i-1]-1 for i in range(1,61)])*math.sqrt(252)*100
                    assert math.isclose(observation['value'],independently,rel_tol=1e-10,abs_tol=1e-10)
            preview = require(client.post(f'/api/strategies/{sid}/patch/preview',json={'source_text':PATCH,'expected_revision':strategy['revision']}))
            report['patch'] = {'response':preview,'attempts':compiler.last_attempts}
            assert preview['proposal_token'] and len(preview['semantic']['operations'])==1
            before = first['strategy']['conditions'];after = preview['preview_conditions']
            pe = next(c for c in before if c['metric']=='pe_ttm')
            assert pe['value'] != 20
            assert next(c for c in after if c['condition_id']==pe['condition_id'])['value']==20
            assert [c for c in before if c['metric']!='pe_ttm']==[c for c in after if c['metric']!='pe_ttm']
            unchanged = require(client.get('/api/strategies/'+sid))
            assert unchanged['strategy']==first['strategy']
            applied = require(client.post(f'/api/strategies/{sid}/patch/apply',json={'expected_revision':strategy['revision'],'proposal_token':preview['proposal_token']}))
            assert applied['strategy']['revision']==strategy['revision']+1 and applied['strategy']['status']=='stale'
            assert applied['results_stale'] is True
            report['patch_applied'] = {'strategy':applied['strategy'],'results_stale':applied['results_stale']}
            financial_calls = len(report['financial_requests'])
            final = require(client.post(f'/api/strategies/{sid}/execute',json={'expected_revision':applied['strategy']['revision']}))
            second = final['latest_execution']
            assert second['snapshot_id']==execution['snapshot_id'] and second['diff']['condition_attributable']
            assert second['run']['snapshot_reused'] and len(report['financial_requests'])==financial_calls
            report.update(status='completed',chain_status='completed',strategy_id=sid,final_execution=second,
                sample_symbols=snapshot['parameters']['sample_symbols'],snapshot_reused=True,
                extra_financial_calls_for_whatif=0,
                live_volatility_count=sum(s['observations']['volatility_60d']['value'] is not None for s in snapshot['stocks']),
                live_pe_count=sum(s['observations']['pe_ttm']['value'] is not None for s in snapshot['stocks']))
            if report['live_volatility_count'] < 10 or report['live_pe_count'] < 10: report['status']='partial_failure'
    except Exception as error:
        report.update(status='failed',failure_type=type(error).__name__,
            failure_category=getattr(error,'category','workflow_assertion_or_upstream_failure'))
    finally:
        report.update(completed_at=now().isoformat(),elapsed_seconds=round(time.perf_counter()-started,3))
        text = json.dumps(report,ensure_ascii=False,indent=2)
        for secret in (provider.client._secret.get_secret_value(),compiler.provider.key.get_secret_value()):
            if secret and secret in text: raise RuntimeError('Credential report guard blocked output') from None
        (ROOT/'artifacts').mkdir(exist_ok=True)
        (ROOT/'artifacts/final-real-validation.json').write_text(text,encoding='utf-8')
        compiler.close();provider.close()
    summary = {k:report.get(k) for k in ('status','strategy_id','sample_symbols','live_pe_count','live_volatility_count','snapshot_reused','extra_financial_calls_for_whatif','elapsed_seconds','failure_type','failure_category')}
    summary['financial_request_count'] = len(report['financial_requests'])
    if report.get('final_execution'):
        summary['counts'] = {k:report['final_execution']['run'][k] for k in ('selected_count','excluded_count','unknown_count')}
        summary['diff'] = report['final_execution']['diff']
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if report['status']=='completed' else 1


if __name__ == '__main__':raise SystemExit(main())
