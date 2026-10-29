"""LLM proposes semantics; validation and patch application are deterministic."""
import json
import re
from pydantic import ValidationError
from app.domain.models import Condition, Strategy, METRIC_INFO
from app.services.compiler_models import SemanticDraft, SemanticPatch
from app.services.llm_provider import CompilerError, configured_llm_provider

PROMPT = '''You compile Chinese investment screening intent, never financial facts or stock names.
Use ONLY revenue_yoy %, net_profit_yoy %, pe_ttm x, volatility_60d %. Operators > >= < <= ==. All conditions AND.
Return ONLY requested strict JSON. No tools or financial data. universe is 000300.SH.
Initial vague defaults: 经营改善 revenue_yoy>0 and net_profit_yoy>0; 估值合理 pe_ttm<30; 走势稳定 volatility_60d<30.
These are llm_interpreted, rationale must state the phrase, proposed metric/threshold and temporary assumption.
Explicit thresholds/operators must be preserved EXACTLY with user_explicit origin; never override explicit with defaults.
Chinese operators: 低于/小于 => <; 不超过/至多/小于等于 => <=; 高于/大于 => >; 不低于/至少/大于等于 => >=; 等于 => ==.
Example initial PE不超过18.5倍 means pe_ttm <= 18.5, user_explicit, never <18.5.
Example 估值合理，但PE必须低于20倍 has ONLY pe_ttm<20 user_explicit, never the vague default 30.
Unsupported requests (PEG, institutions, cashflow, etc) go in unsupported_requests, never invent metrics. Keep supported clauses.
PEG is NOT PE. Example PE低于20，同时PEG低于1: only pe_ttm<20; unsupported_requests=['PEG<1：当前不支持']; never map PEG to pe_ttm or invent peg.
Predictions of certain future returns, profit guarantees or direct buy/sell advice => compliance_status blocked, empty conditions/operations.
Patch is operations only, using exact existing condition_id. Never rebuild strategy. Leave all other fields untouched.
Patch fields update only value/operator; enable/disable/remove target an ID; add supplies full condition and no ID (server assigns).
Explicit 再加/新增/添加 requests MUST use add, even if that metric already exists. Preserve the old condition AND add a new condition with condition_id:null. Never turn add into update or silently overwrite an existing threshold.
All operation fields required, unused fields null. No stock selection/execution.
For update: {operation:'update', condition_id:TARGET_ID, field:'value', value:20, condition:null}.
For remove/enable/disable: {operation:OP, condition_id:TARGET_ID, field:null, value:null, condition:null}.
For add: {operation:'add', condition_id:null, field:null, value:null, condition:NEW_DRAFT_CONDITION}.
The above is shape notation: return valid JSON, copy TARGET_ID exactly from the CURRENT BASE, never literally TARGET_ID.
暂时先不看估值 => disable existing pe_ttm. 不考虑波动率 => remove existing volatility_60d. 启用波动率 => enable.
其他不变 means output ONLY changed-target operations, never copy all BASE conditions. Do not copy historical rationale or system_default origin into new conditions.
Ambiguous PATCH such as 更严格/严格一点/波动再低一点 MUST have clarifications and empty operations, never guess 20/25.
If multiple same-metric targets cannot be uniquely identified ask clarification. Explicit PE改成20 preserves existing operator.
Empty/gibberish/unsupported universe => clarification or unsupported_requests, no fabricated defaults.
Use Chinese for concept, rationale, clarifications and unsupported_requests.
When explicit conditions contradict each other, preserve BOTH conditions in the draft for the deterministic conflict detector. Never silently drop one. Do not replace explicit contradictory constraints with an empty draft.
'''

PATCH_METRIC_NAMES={'pe_ttm':r'PE(?![A-Za-z])|市盈率|估值','revenue_yoy':r'营收|营业收入','net_profit_yoy':r'净利','volatility_60d':r'波动'}

def explicit_constraints(text):
    # A conservative verifier for canonical numeric phrases, not a replacement semantic compiler.
    names={'pe_ttm':r'PE(?:\(TTM\))?|市盈率','revenue_yoy':r'营(?:业收|收)入?同比|营收','net_profit_yoy':r'净利润同比|净利同比','volatility_60d':r'(?:60日)?(?:年化)?波动率'}
    ops={'低于':'<','小于':'<','不超过':'<=','大于':'>','高于':'>','至少':'>=','不低于':'>=','>':'>','<':'<','>=':'>=','<=':'<=','等于':'=='}
    out=[]
    for metric,name in names.items():
        for m in re.finditer(r'(?:'+name+r')\s*(?:(?:必须|应当|需要|需|要|应|须)\s*)?(低于|小于|不超过|不低于|至少|大于|高于|等于|>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)',text,re.I):
            out.append((metric,ops[m[1]],float(m[2])))
    return out

def safety(text, patch=False):
    if re.search(r'一定.*(?:涨|赚|收益)|保证.*(?:赚|收益)|(?:明天|下周).*(?:涨停|赚\s*\d)|(?:直接|现在).*(?:应该买|买哪只|卖哪只)',text): return 'blocked'
    if patch and re.search(r'严格一点|严格些|更严格|再严格|再低一点|再低些|低一点',text) and not re.search(r'\d',text): return 'clarify'
    return None

class LLMStrategyCompiler:
    mode='llm'
    def __init__(self, provider=None): self.provider=provider or configured_llm_provider()
    def _run(self,text,model,base=None):
        if not text.strip(): raise CompilerError('unsupported_intent')
        prompt=PROMPT+'\nTASK='+('PATCH' if base else 'INITIAL')+'\nINPUT='+json.dumps(text,ensure_ascii=False)
        if base:
            prompt+='\nBASE='+json.dumps({'strategy_id':base.strategy_id,'revision':base.revision,'conditions':[c.model_dump(mode='json',include={'condition_id','metric','operator','value','unit','enabled'}) for c in base.conditions]},ensure_ascii=False)
            mentioned={metric for metric,pattern in PATCH_METRIC_NAMES.items() if re.search(pattern,text,re.I)}
            targets=[c for c in base.conditions if not mentioned or c.metric.value in mentioned]
            if mentioned: prompt+='\nONLY these existing target IDs match explicitly mentioned metrics: '+json.dumps([c.condition_id for c in targets])
            if len(targets)==1:
                cid=targets[0].condition_id
                examples={op:{'operations':[{'operation':op,'condition_id':cid,'field':'value' if op=='update' else None,'value':20 if op=='update' else None,'condition':None}],'clarifications':[],'unsupported_requests':[],'compliance_status':'allowed'} for op in ('update','remove','enable','disable')}
                examples['add']={'operations':[{'operation':'add','condition_id':None,'field':None,'value':None,'condition':{'metric':targets[0].metric.value,'operator':'>','value':10,'unit':targets[0].unit,'concept':'新增条件示例','origin':'user_explicit','rationale':'示例：新增条件，保留原条件；实际指标、操作符和阈值必须按INPUT填写。'}}],'clarifications':[],'unsupported_requests':[],'compliance_status':'allowed'}
                prompt+='\nLegal JSON response SHAPES for this single target (choose the operation and value requested by INPUT, never emit multiple alternatives): '+json.dumps(examples,ensure_ascii=False)
        # Strict APIs require all object keys, including nullable ones, to be required.
        schema=model.model_json_schema()
        def strict(node):
            if isinstance(node,dict):
                if node.get('type')=='object': node['required']=list(node.get('properties',{})); node['additionalProperties']=False
                for v in list(node.values()): strict(v)
            elif isinstance(node,list):
                for v in node: strict(v)
        strict(schema)
        self.last_attempts=[]
        for attempt in range(2):
            try:
                self.model_requested=True
                raw=self.provider.generate(prompt, schema)
                self.last_attempts.append({"raw_output":raw,"schema_valid":False,"provider_diagnostic":getattr(self.provider,'last_call',{})})
                result=model.model_validate_json(raw)
                self.last_attempts[-1]["schema_valid"]=True
                values=result.operations if base else result.conditions
                if result.compliance_status=='blocked' and values: raise ValueError()
                if result.clarifications and values and base: raise ValueError()
                if result.compliance_status=='allowed' and not values and not result.clarifications and not result.unsupported_requests: raise ValueError()
                self._verify(text,result,base)
                return result
            except (ValidationError,ValueError) as error:
                if attempt: raise CompilerError('invalid_structured_output') from None
                detail=json.dumps(error.errors(include_input=False,include_context=False,include_url=False)[:10],ensure_ascii=False) if isinstance(error,ValidationError) else str(error) or 'Explicit metric/operator/value/origin did not match INPUT.'
                prompt+='\nPrevious output failed program validation: '+detail[:2500]+'\nCorrect schema, explicit thresholds/origins and target-only operations. Do not return previous output. Required explicit conditions: '+json.dumps(explicit_constraints(text),ensure_ascii=False)
            except CompilerError as e:
                if e.category!='invalid_structured_output' or attempt: raise
                prompt+='\nOutput invalid; return only strict schema JSON.'
        raise CompilerError('invalid_structured_output')
    def _verify(self,text,result,base):
        if result.compliance_status=='blocked' or result.clarifications: return
        if re.search(r'PEG|机构持仓|现金流',text,re.I) and not result.unsupported_requests: raise ValueError('unsupported request silently dropped')
        if base:
            apply_patch(base,result)
            if re.search(r'再加|新增|添加|增加|加一个',text) and not re.search(r'改成|改为|调整|删除|移除|启用|禁用|暂时|不考虑',text):
                if any(op.operation!='add' for op in result.operations): raise ValueError('Explicit add must append a new condition; never update or overwrite existing conditions.')
            names=PATCH_METRIC_NAMES
            mentioned={metric for metric,pattern in names.items() if re.search(pattern,text,re.I)}
            for op in result.operations:
                if op.operation!='add':
                    target=next(c for c in base.conditions if c.condition_id==op.condition_id)
                    if mentioned and target.metric.value not in mentioned: raise ValueError('unmentioned target')
                    candidates=[c for c in base.conditions if c.metric==target.metric]
                    if len(candidates)>1 and not any(c.condition_id in text for c in candidates): raise ValueError('ambiguous duplicate targets')
            for metric,pattern in names.items():
                numeric=re.search(r'(?:'+pattern+r').*?(?:改成|改为|改到|调整为)\s*(-?\d+(?:\.\d+)?)',text,re.I)
                if numeric:
                    candidates=[c for c in base.conditions if c.metric.value==metric]
                    if len(candidates)!=1: raise ValueError()
                    matches=[o for o in result.operations if o.condition_id==candidates[0].condition_id and o.operation=='update' and o.field=='value' and o.value==float(numeric[1])]
                    if len(matches)!=1: raise ValueError('explicit patch value rewritten')
            explicit=re.search(r'(?:PE|市盈率).*?(?:改成|改为|改到|调整为|从\s*\d+\s*改成)\s*(\d+(?:\.\d+)?)',text,re.I)
            if explicit:
                targets=[c for c in base.conditions if c.metric.value=='pe_ttm']
                if len(targets)!=1 or len(result.operations)!=1: raise ValueError()
                op=result.operations[0]
                if op.operation!='update' or op.condition_id!=targets[0].condition_id or op.field!='value' or op.value!=float(explicit[1]): raise ValueError()
        else:
            explicit=explicit_constraints(text)
            defaults=[('经营改善',[('revenue_yoy','>',0),('net_profit_yoy','>',0)]),('估值合理',[('pe_ttm','<',30)]),('走势稳定',[('volatility_60d','<',30)])]
            for phrase,rules in defaults:
                if phrase in text:
                    for metric,operator,value in rules:
                        if any(m==metric for m,_,_ in explicit): continue
                        matches=[c for c in result.conditions if c.metric.value==metric and c.operator==operator and c.value==value and c.origin=='llm_interpreted' and phrase in c.rationale]
                        if not matches: raise ValueError('default explanation/provenance incorrect')
            for metric,operator,value in explicit:
                if not any(c.metric.value==metric and c.operator==operator and c.value==value and c.origin=='user_explicit' for c in result.conditions): raise ValueError()
    def initial(self,text):
        self.last_attempts=[]
        self.model_requested=False
        if not text.strip() or re.fullmatch(r'[a-zA-Z]+',text.strip()):
            return SemanticDraft(universe='000300.SH',conditions=[],clarifications=['请提供可检查的选股条件，例如PE低于20倍。'],unsupported_requests=[],compliance_status='allowed')
        guard=safety(text)
        if guard=='blocked': return SemanticDraft(universe='000300.SH',conditions=[],clarifications=[],unsupported_requests=['不进行确定性涨跌预测、收益承诺或直接买卖建议'],compliance_status='blocked')
        return self._run(text,SemanticDraft)
    def patch(self,text,base):
        self.last_attempts=[]
        self.model_requested=False
        guard=safety(text,True)
        if guard:
            return SemanticPatch(operations=[],clarifications=['当前条件：'+ '；'.join(f'{METRIC_INFO[c.metric][0]} {c.operator} {c.value}{c.unit}' for c in base.conditions) +'。请明确要修改的指标和新阈值（PE以倍、波动率以百分数）；不会自行决定新阈值。'] if guard=='clarify' else [],unsupported_requests=['不进行确定性预测、收益承诺或买卖建议'] if guard=='blocked' else [],compliance_status='blocked' if guard=='blocked' else 'allowed')
        return self._run(text,SemanticPatch,base)
    def close(self):
        close=getattr(self.provider,'close',None)
        if close: close()

def apply_patch(base,patch):
    if patch.clarifications or patch.compliance_status!='allowed': raise CompilerError('unsupported_intent')
    conditions=[c.model_copy(deep=True) for c in base.conditions]
    seen=set()
    for op in patch.operations:
        if op.operation=='add': conditions.append(op.condition.condition()); continue
        if op.condition_id in seen: raise ValueError('duplicate patch target')
        seen.add(op.condition_id)
        matches=[c for c in conditions if c.condition_id==op.condition_id]
        if len(matches)!=1: raise ValueError('unknown patch target')
        c=matches[0]
        if op.operation=='remove': conditions.remove(c); continue
        data=c.model_dump()
        if op.operation in ('enable','disable'): data['enabled']=op.operation=='enable'
        else: data[op.field]=op.value
        data.update(origin='user_explicit',rationale='用户自然语言明确修改；仅应用所审查Patch的目标字段')
        conditions[conditions.index(c)]=Condition.model_validate(data)
    Strategy.model_validate({**base.model_dump(),'conditions':conditions})
    return conditions
