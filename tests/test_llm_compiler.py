import json
import pytest
import httpx
from fastapi.testclient import TestClient
from app.main import create_app
from app.adapters.mock_financial import MockFinancialDataProvider
from app.services.strategy_compiler import DemoStrategyCompiler
from app.services.llm_compiler import LLMStrategyCompiler, apply_patch
from app.services.llm_provider import CompilerError, GLMProvider
from app.services.compiler_models import SemanticPatch


def draft(metric='pe_ttm',op='<',value=20,origin='user_explicit'):
    return {'universe':'000300.SH','conditions':[{'metric':metric,'operator':op,'value':value,'unit':'x','concept':'估值','origin':origin,'rationale':'用户明确要求PE低于20倍'}], 'clarifications':[],'unsupported_requests':[],'compliance_status':'allowed'}
def patch(cid='c3',operation='update',value=20):
    return {'operations':[{'operation':operation,'condition_id':cid,'field':'value' if operation=='update' else None,'value':value if operation=='update' else None,'condition':None}], 'clarifications':[],'unsupported_requests':[],'compliance_status':'allowed'}
class FakeModel:
    ready=True
    name='offline_fixture'
    model='fixture-not-a-model'
    def __init__(self,*responses): self.responses=list(responses); self.calls=0
    def generate(self,*_):
        response=self.responses[min(self.calls,len(self.responses)-1)];self.calls+=1
        if isinstance(response,Exception): raise response
        return response if isinstance(response,str) else json.dumps(response,ensure_ascii=False)


def test_initial_explicit_and_bounded_repair():
    m=FakeModel('{',draft());r=LLMStrategyCompiler(m).initial('PE低于20倍')
    assert r.conditions[0].value==20 and r.conditions[0].origin=='user_explicit' and m.calls==2

@pytest.mark.parametrize('kind',['json','metric','operator','unit','number','explicit','extra'])
def test_invalid_output_never_becomes_demo(kind):
    r=draft()
    if kind=='json': r='invalid'
    elif kind=='metric': r['conditions'][0]['metric']='peg'
    elif kind=='operator': r['conditions'][0]['operator']='!='
    elif kind=='unit': r['conditions'][0]['unit']='%'
    elif kind=='number': r['conditions'][0]['value']=True
    elif kind=='explicit': r['conditions'][0]['value']=30
    else: r['stocks']=['FAKE']
    m=FakeModel(r)
    with pytest.raises(CompilerError,match='invalid_structured_output'): LLMStrategyCompiler(m).initial('PE低于20倍')
    assert m.calls==2

@pytest.mark.parametrize('category',['llm_timeout','llm_auth_error','llm_upstream_error'])
def test_runtime_failure_no_fallback(category):
    m=FakeModel(CompilerError(category))
    with pytest.raises(CompilerError,match=category): LLMStrategyCompiler(m).initial('PE低于20')
    assert m.calls==1


def test_patch_exact_preservation():
    base=DemoStrategyCompiler().compile('demo');original=base.model_dump()
    target=base.conditions[2].condition_id
    r=LLMStrategyCompiler(FakeModel(patch(target))).patch('PE改成20，其他不变',base)
    changed=apply_patch(base,r)
    assert changed[2].value==20 and changed[2].condition_id==target
    assert [c for i,c in enumerate(changed) if i!=2]==[c for i,c in enumerate(base.conditions) if i!=2]
    assert base.model_dump()==original


def test_patch_wrong_target_rejected():
    base=DemoStrategyCompiler().compile('demo')
    m=FakeModel(patch(base.conditions[0].condition_id))
    with pytest.raises(CompilerError,match='invalid_structured_output'): LLMStrategyCompiler(m).patch('PE改成20，其他不变',base)

@pytest.mark.parametrize('text',['估值再严格一点','波动再低一点'])
def test_ambiguous_patch_never_calls_model_or_mutates(text):
    base=DemoStrategyCompiler().compile('demo');m=FakeModel(patch())
    r=LLMStrategyCompiler(m).patch(text,base)
    assert r.clarifications and not r.operations and m.calls==0

@pytest.mark.parametrize('text',['找明天一定涨停的股票','给我推荐下周能赚20%的股票','直接告诉我现在应该买哪只'])
def test_compliance(text):
    m=FakeModel(draft());r=LLMStrategyCompiler(m).initial(text)
    assert r.compliance_status=='blocked' and not r.conditions and m.calls==0


def test_remove_enable_disable_and_add():
    base=DemoStrategyCompiler().compile('demo'); cid=base.conditions[3].condition_id
    for operation in ['remove','enable','disable']:
        r=SemanticPatch.model_validate(patch(cid,operation))
        changed=apply_patch(base,r)
        assert changed[:3]==base.conditions[:3]
        if operation=='remove': assert len(changed)==3
        else: assert changed[3].enabled==(operation=='enable')
    add=patch();add['operations']=[{'operation':'add','condition_id':None,'field':None,'value':None,'condition':{**draft()['conditions'][0],'metric':'revenue_yoy','operator':'>','value':10,'unit':'%'}}]
    changed=apply_patch(base,SemanticPatch.model_validate(add))
    assert changed[:4]==base.conditions and len(changed)==5 and changed[4].condition_id not in {c.condition_id for c in base.conditions}


def test_preview_apply_signed_revision_stale_and_same_snapshot(tmp_path):
    m=FakeModel(draft()); compiler=LLMStrategyCompiler(m)
    with TestClient(create_app(tmp_path/'llm.sqlite3',MockFinancialDataProvider(),compiler)) as client:
        first=client.post('/api/strategies/interpret',json={'source_text':'PE低于20'}).json()['session']
        sid=first['strategy']['strategy_id'];cid=first['strategy']['conditions'][0]['condition_id']
        ran=client.post(f'/api/strategies/{sid}/execute',json={'expected_revision':1}).json()
        m.responses=[patch(cid,value=15)];m.calls=0
        result=client.post(f'/api/strategies/{sid}/patch/preview',json={'source_text':'PE改成15，其他不变','expected_revision':1}).json()
        assert result['proposal_token'] and client.get(f'/api/strategies/{sid}').json()['strategy']['revision']==1
        token=result['proposal_token']
        assert client.post(f'/api/strategies/{sid}/patch/apply',json={'expected_revision':1,'proposal_token':token+'tampered'}).status_code==422
        applied=client.post(f'/api/strategies/{sid}/patch/apply',json={'expected_revision':1,'proposal_token':token}).json()
        assert applied['strategy']['status']=='stale' and applied['strategy']['revision']==2
        assert applied['strategy']['conditions'][0]['value']==15
        assert client.post(f'/api/strategies/{sid}/patch/apply',json={'expected_revision':1,'proposal_token':token}).status_code==409
        reran=client.post(f'/api/strategies/{sid}/execute',json={'expected_revision':2}).json()
        assert reran['latest_execution']['snapshot_id']==ran['latest_execution']['snapshot_id']


def test_conflict_and_unsupported_no_invented_metrics(tmp_path):
    r=draft(op='>',value=30);r['conditions'].append({**r['conditions'][0],'operator':'<','value':10})
    m=FakeModel(r)
    with TestClient(create_app(tmp_path/'a.sqlite3',MockFinancialDataProvider(),LLMStrategyCompiler(m))) as c:
        result=c.post('/api/strategies/interpret',json={'source_text':'PE大于30同时小于10'}).json()
        assert result['conflicts'] and result['session']['conflicts']
        sid=result['session']['strategy']['strategy_id']
        assert c.post(f'/api/strategies/{sid}/execute',json={'expected_revision':1}).status_code==422
        m.responses=[{**draft(),'conditions':[],'unsupported_requests':['PEG和机构持仓未支持']}];m.calls=0
        out=c.post('/api/strategies/interpret',json={'source_text':'PEG低于1且机构持仓增长'}).json()
        assert out['session'] is None and out['semantic']['unsupported_requests']

@pytest.mark.parametrize('status,category',[(401,'llm_auth_error'),(403,'llm_auth_error'),(429,'llm_upstream_error')])
def test_glm_safe_errors(monkeypatch,status,category):
    sentinel='fixture-credential-not-real';monkeypatch.setenv('ZHIPU_API_KEY',sentinel)
    p=GLMProvider(transport=httpx.MockTransport(lambda req:httpx.Response(status,json={'error':{'message':sentinel}})))
    try:
        with pytest.raises(CompilerError) as e:p.generate('test',{})
        assert str(e.value)==category and sentinel not in str(e.value)
    finally:p.close()


def test_glm_timeout_and_real_envelope(monkeypatch):
    monkeypatch.setenv('ZHIPU_API_KEY','fixture-credential-not-real')
    def timed(req): raise httpx.ReadTimeout('unsafe internal details',request=req)
    p=GLMProvider(transport=httpx.MockTransport(timed))
    with pytest.raises(CompilerError,match='llm_timeout'):p.generate('test',{})
    p.close()
    def ok(req):
        assert req.url.host=='open.bigmodel.cn'
        payload=json.loads(req.content)
        assert payload['model']=='glm-4.7-flash' and payload['response_format']=={'type':'json_object'} and 'tools' not in payload
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(draft())}}]})
    p=GLMProvider(transport=httpx.MockTransport(ok))
    assert json.loads(p.generate('test',{}))==draft();p.close()


def test_eval_grader_detects_mutation_outside_gold_target():
    from scripts.eval_llm import grade
    base=DemoStrategyCompiler().compile('eval context')
    for i,c in enumerate(base.conditions):c.condition_id=f'c{i+1}'
    wrong=SemanticPatch.model_validate(patch('c1',value=15))
    scores=grade({'task':'patch','expected':{'operation':'update','target':'c3','value':15}},wrong,base)
    assert scores['Patch Target Accuracy'] is False and scores['Patch Preservation Rate'] is False


def test_eval_grader_checks_explicit_mapping_not_only_global_values():
    from scripts.eval_llm import grade
    from app.services.compiler_models import SemanticDraft
    result=draft();result['conditions'].append({**result['conditions'][0],'metric':'revenue_yoy','unit':'%','value':5})
    scores=grade({'task':'initial','expected':{'conditions':[['pe_ttm','<',5,'user_explicit'],['revenue_yoy','<',20,'user_explicit']]}},SemanticDraft.model_validate(result),None)
    assert scores['Explicit Value Accuracy'] is False


def test_vague_initial_has_interpreted_origin_and_explanation():
    r=draft(value=30,origin='llm_interpreted');r['conditions'][0]['rationale']='将估值合理暂解释为PE(TTM)<30倍'
    assert LLMStrategyCompiler(FakeModel(r)).initial('估值合理').conditions[0].origin=='llm_interpreted'
    r['conditions'][0]['origin']='user_explicit'
    with pytest.raises(CompilerError,match='invalid_structured_output'):LLMStrategyCompiler(FakeModel(r)).initial('估值合理')


def test_explicit_must_phrase_overrides_vague_default():
    result=LLMStrategyCompiler(FakeModel(draft())).initial('估值合理，但PE必须低于20倍')
    assert len(result.conditions)==1 and result.conditions[0].value==20
    assert result.conditions[0].origin=='user_explicit'
    wrong=draft(value=30,origin='llm_interpreted')
    with pytest.raises(CompilerError,match='invalid_structured_output'):
        LLMStrategyCompiler(FakeModel(wrong)).initial('估值合理，但PE必须低于20倍')


def test_not_exceed_operator_is_preserved():
    wrong=draft(value=18.5)
    with pytest.raises(CompilerError,match='invalid_structured_output'):
        LLMStrategyCompiler(FakeModel(wrong)).initial('PE不超过18.5倍')
    correct=draft(op='<=',value=18.5)
    assert LLMStrategyCompiler(FakeModel(correct)).initial('PE不超过18.5倍').conditions[0].operator=='<='


def test_patch_update_cannot_smuggle_full_condition():
    base=DemoStrategyCompiler().compile('context')
    response=patch(base.conditions[2].condition_id)
    response['operations'][0]['condition']=draft()['conditions'][0]
    with pytest.raises(CompilerError,match='invalid_structured_output'):
        LLMStrategyCompiler(FakeModel(response)).patch('PE改成20，其他不变',base)


def test_explicit_add_same_metric_never_overwrites_existing_condition():
    base=DemoStrategyCompiler().compile('context');before=base.model_dump()
    wrong=patch(base.conditions[0].condition_id,value=10)
    with pytest.raises(CompilerError,match='invalid_structured_output'):
        LLMStrategyCompiler(FakeModel(wrong)).patch('再加一个营收同比大于10%的条件',base)
    correct=patch();correct['operations']=[{'operation':'add','condition_id':None,'field':None,'value':None,'condition':{**draft()['conditions'][0],'metric':'revenue_yoy','operator':'>','value':10,'unit':'%'}}]
    semantic=LLMStrategyCompiler(FakeModel(correct)).patch('再加一个营收同比大于10%的条件',base)
    result=apply_patch(base,semantic)
    assert result[:4]==base.conditions and len(result)==5 and result[4].value==10
    assert result[4].condition_id not in {c.condition_id for c in base.conditions}
    assert base.model_dump()==before


def test_clarification_never_changes_persisted_strategy(tmp_path):
    m=FakeModel(draft());compiler=LLMStrategyCompiler(m)
    with TestClient(create_app(tmp_path/'clarify.sqlite3',MockFinancialDataProvider(),compiler)) as c:
        first=c.post('/api/strategies/interpret',json={'source_text':'PE低于20'}).json()['session']
        sid=first['strategy']['strategy_id']
        r=c.post(f'/api/strategies/{sid}/patch/preview',json={'source_text':'估值严格一点','expected_revision':1}).json()
        assert r['semantic']['clarifications'] and r['proposal_token'] is None and r['preview_conditions'] is None
        assert c.get(f'/api/strategies/{sid}').json()==first


def test_missing_llm_credentials_does_not_reach_demo_or_provider(monkeypatch,tmp_path):
    monkeypatch.delenv('ZHIPU_API_KEY',raising=False)
    monkeypatch.delenv('SILICONFLOW_API_KEY',raising=False)
    with TestClient(create_app(tmp_path/'no-key.sqlite3',MockFinancialDataProvider(),LLMStrategyCompiler())) as c:
        result=c.post('/api/strategies/interpret',json={'source_text':'PE低于20'})
        assert result.status_code==502 and result.json()['category']=='llm_auth_error'
        assert c.post('/api/strategies/compile',json={'source_text':'PE低于20'}).json()['category']=='unsupported_intent'


def test_eval_dataset_missing_key_has_no_fabricated_rates(monkeypatch,capsys,tmp_path):
    from scripts.eval_llm import main
    monkeypatch.delenv('ZHIPU_API_KEY',raising=False)
    monkeypatch.delenv('SILICONFLOW_API_KEY',raising=False)
    main(tmp_path/"notverified.json")
    report=json.loads(capsys.readouterr().out)
    assert report['status']=='not_verified' and report['planned_cases']==26 and report['evaluated_cases']==0
    assert all(v['rate'] is None and v['total']==0 for v in report['metrics'].values())
