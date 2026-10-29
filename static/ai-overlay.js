(() => {
  const baseFetch = window.fetch.bind(window);
  const STORE_KEY = "strategylens.pages.demo.v1";
  const PROPOSAL_KEY = "strategylens.pages.ai.proposals.v1";
  const metricUnit = {revenue_yoy:"%",net_profit_yoy:"%",pe_ttm:"x",volatility_60d:"%"};

  const response = (body,status=200) => new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json; charset=utf-8"}});
  const clone = (x) => structuredClone(x);
  const uid = () => crypto.randomUUID();
  function readState(){ try{return JSON.parse(localStorage.getItem(STORE_KEY))||{strategies:{},snapshots:{},executions:{}};}catch{return {strategies:{},snapshots:{},executions:{}};} }
  function writeState(s){ localStorage.setItem(STORE_KEY,JSON.stringify(s)); }
  function readProposals(){ try{return JSON.parse(localStorage.getItem(PROPOSAL_KEY))||{};}catch{return {};} }
  function writeProposals(p){ localStorage.setItem(PROPOSAL_KEY,JSON.stringify(p)); }
  async function readJson(res){
    let data={}; try{data=await res.json();}catch{}
    if(!res.ok){ const e=new Error(data.detail||"请求未完成"); e.status=res.status; e.category=data.category; throw e; }
    return data;
  }
  async function callAi(payload){ return readJson(await baseFetch("/ai",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})); }
  async function callDemo(path,method="GET",body){ return readJson(await baseFetch(path,{method,headers:{"Content-Type":"application/json"},...(body?{body:JSON.stringify(body)}:{})})); }

  function conflicts(conditions){
    const groups={}; for(const c of conditions.filter(c=>c.enabled)) (groups[c.metric] ||= []).push(c);
    const out=[];
    for(const [metric,group] of Object.entries(groups)){
      let lower=-Infinity, upper=Infinity, lc=false, uc=false;
      for(const c of group){
        if([">",">=","=="].includes(c.operator)){ const closed=c.operator!==">"; if(c.value>lower){lower=c.value;lc=closed;} else if(c.value===lower) lc=lc&&closed; }
        if(["<","<=","=="].includes(c.operator)){ const closed=c.operator!=="<"; if(c.value<upper){upper=c.value;uc=closed;} else if(c.value===upper) uc=uc&&closed; }
      }
      if(lower>upper || (lower===upper && !(lc&&uc))) out.push({metric,condition_ids:group.map(c=>c.condition_id),reason:"启用条件没有公共可行范围"});
    }
    return out;
  }

  function normalizeCondition(c){
    return {condition_id:c.condition_id||uid(),concept:c.concept||c.metric,metric:c.metric,operator:c.operator,value:Number(c.value),unit:metricUnit[c.metric],enabled:c.enabled!==false,origin:c.origin==="user_explicit"?"user_explicit":"llm_interpreted",rationale:c.rationale||"AI根据自然语言生成的待审查条件"};
  }

  function applyOps(base,semantic){
    const next=clone(base);
    for(const op of semantic.operations||[]){
      if(op.operation==="add"){ next.push(normalizeCondition(op.condition)); continue; }
      const i=next.findIndex(c=>c.condition_id===op.condition_id); if(i<0) throw new Error("AI修改目标已失效，请重新解析");
      if(op.operation==="remove"){ next.splice(i,1); continue; }
      if(op.operation==="enable" || op.operation==="disable"){ next[i].enabled=op.operation==="enable"; next[i].origin="user_explicit"; next[i].rationale="用户自然语言明确修改；仅应用所审查Patch"; continue; }
      if(op.operation==="update"){
        if(op.field==="value") next[i].value=Number(op.value);
        else if(op.field==="operator") next[i].operator=op.value;
        next[i].origin="user_explicit"; next[i].rationale="用户自然语言明确修改；仅应用所审查Patch";
      }
    }
    return next;
  }

  async function interpret(body){
    const text=String(body?.source_text||"").trim();
    const semantic=await callAi({mode:"initial",text});
    const output={semantic,session:null,conflicts:[]};
    if(semantic.compliance_status==="blocked" || semantic.clarifications?.length || !semantic.conditions?.length) return response(output);

    const seed=await callDemo("/api/strategies/compile","POST",{source_text:text});
    const sid=seed.strategy.strategy_id;
    const state=readState(), rec=state.strategies[sid];
    if(!rec) return response({detail:"浏览器会话初始化失败"},500);
    rec.strategy.conditions=semantic.conditions.map(normalizeCondition);
    rec.strategy.revision=1; rec.strategy.status="draft"; rec.strategy.source_text=text; rec.strategy.updated_at=new Date().toISOString();
    writeState(state);
    output.session=await callDemo(`/api/strategies/${encodeURIComponent(sid)}`);
    output.conflicts=output.session.conflicts||[];
    return response(output);
  }

  async function preview(strategyId,body){
    const session=await callDemo(`/api/strategies/${encodeURIComponent(strategyId)}`);
    if(body?.expected_revision!==session.strategy.revision) return response({detail:"策略版本已变化，请刷新后重试"},409);
    const semantic=await callAi({mode:"patch",text:String(body?.source_text||""),base:{strategy_id:strategyId,revision:session.strategy.revision,conditions:session.strategy.conditions.map(c=>({condition_id:c.condition_id,metric:c.metric,operator:c.operator,value:c.value,unit:c.unit,enabled:c.enabled}))}});
    const result={semantic,preview_conditions:null,conflicts:[],proposal_token:null};
    if(semantic.compliance_status==="blocked" || semantic.clarifications?.length || !semantic.operations?.length) return response(result);
    let next; try{next=applyOps(session.strategy.conditions,semantic);}catch(e){return response({detail:e.message,category:"invalid_patch_proposal"},422);}
    const cs=conflicts(next); result.preview_conditions=next; result.conflicts=cs;
    if(!cs.length){ const token=uid(); const p=readProposals(); p[token]={strategy_id:strategyId,revision:session.strategy.revision,conditions:next,created_at:Date.now()}; writeProposals(p); result.proposal_token=token; }
    return response(result);
  }

  async function apply(strategyId,body){
    const p=readProposals(), proposal=p[body?.proposal_token];
    if(!proposal || proposal.strategy_id!==strategyId || proposal.revision!==body?.expected_revision || Date.now()-proposal.created_at>10*60*1000) return response({detail:"修改提案已失效，请重新解析",category:"invalid_patch_proposal"},422);
    let session;
    try{ session=await callDemo(`/api/strategies/${encodeURIComponent(strategyId)}/conditions`,"PUT",{expected_revision:body.expected_revision,conditions:proposal.conditions}); }
    catch(e){ return response({detail:e.message},e.status||422); }
    delete p[body.proposal_token]; writeProposals(p); return response(session);
  }

  window.fetch=async (input,init={})=>{
    const url=typeof input==="string"?new URL(input,location.origin):new URL(input.url,location.origin);
    const method=(init.method||"GET").toUpperCase(); let body=null; try{if(init.body) body=JSON.parse(init.body);}catch{}
    if(url.origin===location.origin && url.pathname==="/api/config" && method==="GET"){
      const config=await callDemo("/api/config"); return response({...config,compiler:"llm",runtime_llm:true,llm_ready:true});
    }
    if(url.origin===location.origin && url.pathname==="/api/health" && method==="GET"){
      const health=await callDemo("/api/health"); return response({...health,compiler:"llm"});
    }
    if(url.origin===location.origin && url.pathname==="/api/strategies/interpret" && method==="POST"){
      try{return await interpret(body);}catch(e){return response({detail:e.message,category:e.category||"llm_upstream_error"},e.status||502);}
    }
    let m=url.pathname.match(/^\/api\/strategies\/([^/]+)\/patch\/preview$/);
    if(url.origin===location.origin && m && method==="POST"){
      try{return await preview(decodeURIComponent(m[1]),body);}catch(e){return response({detail:e.message,category:e.category||"llm_upstream_error"},e.status||502);}
    }
    m=url.pathname.match(/^\/api\/strategies\/([^/]+)\/patch\/apply$/);
    if(url.origin===location.origin && m && method==="POST") return apply(decodeURIComponent(m[1]),body);
    return baseFetch(input,init);
  };
})();
