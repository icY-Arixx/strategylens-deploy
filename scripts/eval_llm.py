"""Opt-in real model eval. Missing credentials => not_verified, never Demo scoring."""
import json
import time
from pathlib import Path
from app.services.llm_compiler import LLMStrategyCompiler, apply_patch
from app.services.strategy_compiler import DemoStrategyCompiler
from app.services.llm_provider import CompilerError
from app.domain.conflicts import detect_conflicts

METRICS=['Schema Valid Rate','Explicit Metric Accuracy','Explicit Operator Accuracy','Explicit Value Accuracy','Patch Target Accuracy','Patch Preservation Rate','Clarification Accuracy','Unsupported Metric Handling','Conflict Handling','Compliance Boundary Accuracy']

def grade(case,result,base):
    e=case['expected'];scores={}
    conditions=getattr(result,'conditions',[])
    if 'conditions' in e:
        expected=e['conditions'];actual=[(c.metric.value,c.operator,c.value,c.origin) for c in conditions]
        for name,index in [('Explicit Metric Accuracy',0),('Explicit Operator Accuracy',1),('Explicit Value Accuracy',2)]:
            if all(c[3]=='user_explicit' for c in expected):
                scores[name]=len(actual)==len(expected) and sorted(x[index] for x in actual)==sorted(x[index] for x in expected) and all(any(a[0]==x[0] and a[index]==x[index] for a in actual) for x in expected)
        scores['case_conditions_exact']=sorted(actual)==sorted(tuple(x) for x in expected)
    if case['task']=='patch' and 'operation' in e:
        ops=result.operations
        scores['Patch Target Accuracy']=len(ops)==1 and ops[0].operation==e['operation'] and (ops[0].condition_id==e.get('target') if e['operation']!='add' else ops[0].condition.metric.value==e['metric']) and (ops[0].value==e['value'] if e['operation']=='update' else ops[0].condition.value==e['value'] if e['operation']=='add' else True)
        updated=apply_patch(base,result)
        untouched=[c for c in base.conditions if c.condition_id!=e.get('target')]
        scores['Patch Preservation Rate']=all(any(c==n for n in updated) for c in untouched) and {c.condition_id for c in updated}-{c.condition_id for c in base.conditions}==({c.condition_id for c in updated if c.condition_id not in {b.condition_id for b in base.conditions}} if e['operation']=='add' else set())
    if e.get('clarify'):
        scores['Clarification Accuracy']=bool(result.clarifications) and not getattr(result,'operations',[]) and not conditions
    if 'unsupported' in e:
        scores['Unsupported Metric Handling']=bool(result.unsupported_requests) and all(term.lower() in ' '.join(result.unsupported_requests).lower() for term in e['unsupported'])
    if e.get('conflict'):scores['Conflict Handling']=bool(detect_conflicts([c.condition() for c in conditions]))
    if e.get('blocked'):scores['Compliance Boundary Accuracy']=result.compliance_status=='blocked' and not conditions and not getattr(result,'operations',[])
    return scores

def main(output=None):
    root=Path(__file__).resolve().parents[1]
    cases=json.loads((root/'tests/eval/strategy_cases.json').read_text(encoding='utf-8'))
    compiler=LLMStrategyCompiler();provider=compiler.provider
    report={'test_type':'REAL_LLM_EVAL','provider':provider.name,'model':provider.model,'planned_cases':len(cases),'evaluated_cases':0,'status':'not_verified','metrics':{m:{'passed':0,'total':0,'rate':None} for m in METRICS},'cases':[]}
    try:
        if not provider.ready:
            report['reason']=provider.key_env+' not configured; no real model requests or Demo substitution'
        else:
            report['status']='completed'
            for case in cases:
                base=DemoStrategyCompiler().compile('fixed evaluation context, not model output')
                for i,c in enumerate(base.conditions):c.condition_id=f'c{i+1}'
                started=time.perf_counter();record={'id':case['id'],'input':case['text'],'task':case['task']}
                expected=case['expected']
                applicable=[]
                if expected.get('conditions') and all(c[3]=='user_explicit' for c in expected['conditions']):applicable+=METRICS[1:4]
                if expected.get('operation'):applicable+=METRICS[4:6]
                if expected.get('clarify'):applicable.append(METRICS[6])
                if expected.get('unsupported'):applicable.append(METRICS[7])
                if expected.get('conflict'):applicable.append(METRICS[8])
                if expected.get('blocked'):applicable.append(METRICS[9])
                scores={m:False for m in applicable}
                try:
                    result=compiler.patch(case['text'],base) if case['task']=='patch' else compiler.initial(case['text'])
                    scores.update(grade(case,result,base));record['result']=result.model_dump(mode='json')
                except (CompilerError,ValueError) as exc:
                    record['error']=exc.category if isinstance(exc,CompilerError) else 'validation_error'
                    record['provider_diagnostic']=getattr(provider,'last_call',{})
                    if record['error'] in ('llm_auth_error','llm_timeout','llm_upstream_error'):scores={}
                    if not case['text'].strip() and expected.get('clarify'):scores[METRICS[6]]=False
                attempts=getattr(compiler,'last_attempts',[])
                if attempts:scores[METRICS[0]]=attempts[0]['schema_valid']
                record.update(scores=scores,attempts=attempts,elapsed_seconds=round(time.perf_counter()-started,3),path='model' if getattr(compiler,'model_requested',False) else 'program_preflight')
                if record['path']=='model':record['provider_diagnostic']=getattr(provider,'last_call',{})
                report['cases'].append(record);report['evaluated_cases']+=1
                print(case['id']+' '+record['path']+' '+record.get('error','evaluated')+' '+str(record['elapsed_seconds'])+'s',flush=True)
                for metric,value in scores.items():
                    if metric in report['metrics']:
                        count=report['metrics'][metric];count['total']+=1;count['passed']+=int(value);count['rate']=count['passed']/count['total']
                # Serial, bounded, no financial calls. Abort credential errors rather than hammering service.
                if record.get('error')=='llm_auth_error':report['status']='failed';break
        report['successful_semantic_cases']=sum('result' in c for c in report['cases'])
        out=Path(output) if output else root/'artifacts/llm-eval.json';out.parent.mkdir(parents=True,exist_ok=True)
        text=json.dumps(report,ensure_ascii=False,indent=2)
        secret=provider.key.get_secret_value()
        if secret and secret in text:raise RuntimeError('Credential output blocked')
        out.write_text(text,encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False,indent=2))
    finally:compiler.close()

if __name__=='__main__':main()
