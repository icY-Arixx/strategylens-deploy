"""Offline HTTP fixtures only. No real credentials or live model calls."""
import json
import httpx
import pytest
from app.services.llm_provider import SiliconFlowProvider, GLMProvider, CompilerError, configured_llm_provider


def test_siliconflow_request_contract_and_safe_trace(monkeypatch):
    monkeypatch.setenv('SILICONFLOW_API_KEY','fixture-siliconflow-credential')
    monkeypatch.setenv('ZHIPU_API_KEY','fixture-other-credential')
    monkeypatch.delenv('STRATEGYLENS_LLM_MODEL',raising=False)
    def respond(request):
        assert str(request.url)=='https://api.siliconflow.cn/v1/chat/completions'
        assert request.headers['Authorization']=='Bearer fixture-siliconflow-credential'
        body=json.loads(request.content)
        assert body['model']=='Qwen/Qwen3-8B'
        assert body['response_format']=={'type':'json_object'}
        assert body['enable_thinking'] is False and body['temperature']==0
        assert 'thinking' not in body and 'tools' not in body
        return httpx.Response(200,headers={'x-siliconcloud-trace-id':'trace-fixture-123'},json={'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]})
    provider=SiliconFlowProvider(transport=httpx.MockTransport(respond))
    try:
        assert provider.generate('only semantics',{})=='{}'
        assert provider.last_call['request_id']=='trace-fixture-123'
        assert provider.last_call['http_status']==200
        assert 'fixture-siliconflow-credential' not in json.dumps(provider.last_call)
    finally:provider.close()


@pytest.mark.parametrize('body', [[], {'choices':[]}, {'error':'unsafe response'}, {'code':20012,'message':'unsafe response'}, {'choices':[{'finish_reason':'stop','message':{'content':None}}]}])
def test_malformed_or_business_error_never_returns_semantics(monkeypatch,body):
    monkeypatch.setenv('SILICONFLOW_API_KEY','fixture-credential')
    provider=SiliconFlowProvider(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=body)))
    try:
        with pytest.raises(CompilerError) as error:provider.generate('test',{})
        assert error.value.category in ('invalid_structured_output','llm_upstream_error')
        assert 'unsafe response' not in str(error.value)
    finally:provider.close()


@pytest.mark.parametrize('status,category',[(401,'llm_auth_error'),(403,'llm_auth_error'),(429,'llm_upstream_error')])
def test_siliconflow_errors_redact_key(monkeypatch,status,category):
    credential='fixture-credential-not-real'
    monkeypatch.setenv('SILICONFLOW_API_KEY',credential)
    provider=SiliconFlowProvider(transport=httpx.MockTransport(lambda _:httpx.Response(status,json={'message':credential},headers={'x-siliconcloud-trace-id':credential})))
    try:
        with pytest.raises(CompilerError,match=category) as error:provider.generate('test',{})
        assert credential not in str(error.value) and credential not in json.dumps(provider.last_call)
    finally:provider.close()


def test_siliconflow_missing_key_never_uses_zhipu_key(monkeypatch):
    monkeypatch.delenv('SILICONFLOW_API_KEY',raising=False)
    monkeypatch.setenv('ZHIPU_API_KEY','fixture-other-credential')
    calls=[]
    provider=SiliconFlowProvider(transport=httpx.MockTransport(lambda request:calls.append(request)))
    try:
        assert provider.ready is False
        with pytest.raises(CompilerError,match='llm_auth_error'):provider.generate('test',{})
        assert calls==[]
    finally:provider.close()


def test_provider_configuration_is_explicit_no_fallback(monkeypatch):
    for mode,kind in [('siliconflow',SiliconFlowProvider),('zhipu',GLMProvider)]:
        monkeypatch.setenv('STRATEGYLENS_LLM_PROVIDER',mode)
        provider=configured_llm_provider()
        assert isinstance(provider,kind)
        provider.close()
    monkeypatch.setenv('STRATEGYLENS_LLM_PROVIDER','unknown')
    with pytest.raises(CompilerError,match='unsupported_llm_provider'):configured_llm_provider()


def test_siliconflow_timeout_does_not_leak_transport_details(monkeypatch):
    monkeypatch.setenv('SILICONFLOW_API_KEY','fixture-credential')
    def respond(request):raise httpx.ReadTimeout('unsafe upstream detail',request=request)
    provider=SiliconFlowProvider(transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(CompilerError,match='llm_timeout') as error:provider.generate('test',{})
        assert str(error.value)=='llm_timeout'
    finally:provider.close()
