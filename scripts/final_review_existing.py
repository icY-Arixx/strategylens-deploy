"""No network/model calls: review inverted draft and reuse existing REAL evidence.

The correction is an authorized scripted review, never claimed as raw model success
or an actual human click. Original reports remain available.
"""
import json
import time
from pathlib import Path
from app.adapters.fuyao_validation import FuyaoValidationSampleProvider
from app.domain.models import Condition, now
from app.services.compiler_models import SemanticPatch
from app.services.llm_compiler import apply_patch
from app.services.session_service import SessionService
from app.store.sqlite_store import SQLiteStore


def main():
    root=Path(__file__).resolve().parents[1];path=root/'artifacts/final-real-validation.json'
    content=path.read_text(encoding='utf-8');report=json.loads(content)
    if report.get('review_correction'): raise RuntimeError('Review already completed; do not create extra revisions')
    path.with_name('final-real-validation.uncorrected.json').write_text(content,encoding='utf-8')
    provider=FuyaoValidationSampleProvider()
    def forbidden(*args,**kwargs):raise AssertionError('Review must reuse saved snapshot; network forbidden')
    provider.fetch_snapshot=forbidden
    provider.client.get=forbidden
    services=SessionService(SQLiteStore(root/'data/final-real.sqlite3'),provider)
    started=time.perf_counter()
    try:
        sid=report['strategy_id'];current=services.get(sid)
        original=report['initial_compile']['response']['session']['strategy']['conditions']
        corrected=[Condition.model_validate({**c,'operator':'<'}) for c in original]
        reviewed=services.update(sid,current.strategy.revision,corrected)
        first=services.execute(sid,reviewed.strategy.revision)
        patch=SemanticPatch.model_validate(report['patch']['response']['semantic'])
        conditions=apply_patch(first.strategy,patch)
        before=[c for c in first.strategy.conditions if c.metric.value!='pe_ttm']
        assert before==[c for c in conditions if c.metric.value!='pe_ttm']
        applied=services.update(sid,first.strategy.revision,conditions)
        assert applied.results_stale and applied.strategy.status=='stale'
        final=services.execute(sid,applied.strategy.revision)
        assert final.latest_execution.snapshot_id==first.latest_execution.snapshot_id==report['snapshot']['snapshot_id']
        assert final.latest_execution.diff.condition_attributable
        report.update(status='completed_after_review_correction',raw_initial_compile_correct=False,
            first_execution=first.latest_execution.model_dump(mode='json'),final_execution=final.latest_execution.model_dump(mode='json'),
            patch_applied={'strategy':applied.strategy.model_dump(mode='json'),'results_stale':True},
            review_correction={'performed_at':now().isoformat(),'human_click_claimed':False,
                'reason':'Raw model inverted both directions to >=30; authorized review corrected them to <30. Prompt/model/parameters unchanged.',
                'raw_conditions':original,'corrected_conditions':[c.model_dump(mode='json') for c in first.strategy.conditions],
                'llm_calls':0,'financial_calls':0,'patch_reused_from_prior_real_response':True},
            review_validation_elapsed_seconds=round(time.perf_counter()-started,3))
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'status':report['status'],'raw_initial_compile_correct':False,
            'counts_before':{k:getattr(first.latest_run,k) for k in ('selected_count','excluded_count','unknown_count')},
            'counts_after':{k:getattr(final.latest_run,k) for k in ('selected_count','excluded_count','unknown_count')},
            'snapshot_id':final.latest_execution.snapshot_id,'revision':final.strategy.revision,
            'new_llm_calls':0,'new_financial_calls':0},ensure_ascii=False,indent=2))
    finally:provider.close()


if __name__=='__main__':main()
