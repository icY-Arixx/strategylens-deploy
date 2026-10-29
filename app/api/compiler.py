"""Compiler-only endpoints. No data provider or engine invocation."""
import base64
import hashlib
import hmac
import json
import time
from typing import Annotated
from fastapi import APIRouter, Request
from pydantic import Field
from app.domain.models import Contract, Condition, Strategy, now
from app.domain.conflicts import detect_conflicts
from app.api.strategy import CompileRequest, RevisionRequest
from app.services.llm_compiler import apply_patch
from app.services.llm_provider import CompilerError
from app.store.sqlite_store import RevisionConflict

router=APIRouter(prefix='/api/strategies',tags=['compiler'])
class PatchRequest(RevisionRequest):
    source_text: Annotated[str,Field(min_length=1,max_length=2000)]
class ApplyRequest(RevisionRequest):
    proposal_token: Annotated[str,Field(min_length=1,max_length=100000)]

def sign(request,payload):
    body=base64.urlsafe_b64encode(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()).decode()
    sig=hmac.new(request.app.state.compiler_secret,body.encode(),hashlib.sha256).hexdigest()
    return body+'.'+sig

def decode(request,token):
    try:
        body,sig=token.rsplit('.',1)
        expected=hmac.new(request.app.state.compiler_secret,body.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): raise ValueError()
        payload=json.loads(base64.urlsafe_b64decode(body))
        if time.time()>payload['expires']: raise ValueError()
        return payload
    except (ValueError,KeyError,TypeError): raise CompilerError('invalid_patch_proposal') from None

def compiler(request):
    c=request.app.state.sessions.compiler
    if getattr(c,'mode','demo')!='llm': raise CompilerError('unsupported_intent')
    return c

@router.post('/interpret')
def interpret(body:CompileRequest,request:Request):
    sessions=request.app.state.sessions
    semantic=compiler(request).initial(body.source_text)
    output={'semantic':semantic.model_dump(mode='json'),'session':None,'conflicts':[]}
    if semantic.clarifications or semantic.compliance_status=='blocked' or not semantic.conditions: return output
    strategy=Strategy(source_text=body.source_text,universe=sessions.provider.universe,conditions=[c.condition() for c in semantic.conditions])
    output['conflicts']=[c.model_dump(mode='json') for c in detect_conflicts(strategy.conditions)]
    sessions.store.create(strategy)
    output['session']=sessions.snapshot(strategy,None)
    return output

@router.post('/{strategy_id}/patch/preview')
def preview(strategy_id:str,body:PatchRequest,request:Request):
    sessions=request.app.state.sessions
    base,_=sessions.store.read(strategy_id)
    sessions.check_revision(base,body.expected_revision)
    patch=compiler(request).patch(body.source_text,base)
    output={'semantic':patch.model_dump(mode='json'),'preview_conditions':None,'conflicts':[],'proposal_token':None}
    if patch.clarifications or patch.compliance_status=='blocked' or not patch.operations: return output
    try: conditions=apply_patch(base,patch)
    except ValueError: raise CompilerError('invalid_structured_output') from None
    conflicts=detect_conflicts(conditions)
    output.update(preview_conditions=[c.model_dump(mode='json') for c in conditions],conflicts=[c.model_dump(mode='json') for c in conflicts])
    if not conflicts:
        output['proposal_token']=sign(request,{'strategy_id':strategy_id,'revision':base.revision,'conditions':output['preview_conditions'],'expires':time.time()+600})
    return output

@router.post('/{strategy_id}/patch/apply')
def accept(strategy_id:str,body:ApplyRequest,request:Request):
    compiler(request)
    data=decode(request,body.proposal_token)
    sessions=request.app.state.sessions
    base,execution=sessions.store.read(strategy_id)
    sessions.check_revision(base,body.expected_revision)
    if data['strategy_id']!=strategy_id or data['revision']!=base.revision: raise RevisionConflict('Patch基础版本已变化，请重新解析')
    conditions=[Condition.model_validate(c) for c in data['conditions']]
    if detect_conflicts(conditions): raise CompilerError('invalid_structured_output')
    if conditions==base.conditions: return sessions.snapshot(base,execution)
    updated=base.model_copy(update={'conditions':conditions,'revision':base.revision+1,'status':'stale' if execution else 'draft','updated_at':now()})
    sessions.store.save(base,updated)
    return sessions.snapshot(updated,execution)
