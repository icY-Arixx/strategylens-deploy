(() => {
  const originalFetch = window.fetch.bind(window);
  const STORE_KEY = "strategylens.pages.demo.v1";
  const provider = "MockFinancialDataProvider / DEMO";
  const dataMode = "DEMO / MOCK";
  const universe = "CSI300_DEMO";
  const metricMeta = {
    revenue_yoy: ["营业收入同比", "%"],
    net_profit_yoy: ["净利润同比", "%"],
    pe_ttm: ["PE(TTM)", "x"],
    volatility_60d: ["60日年化波动率", "%"],
  };
  const rows = [
    ["DEMO001","示例·青禾制造",12,18,18,22],
    ["DEMO002","示例·澄川消费",8,10,25,24],
    ["DEMO003","示例·远山科技",20,30,35,25],
    ["DEMO004","示例·星港材料",-5,-10,40,38],
    ["DEMO005","示例·沐光医药",10,12,null,20],
    ["DEMO006","示例·明岸能源",15,20,15,35],
    ["DEMO007","示例·云杉服务",0,5,12,15],
    ["DEMO008","示例·知行装备",9,11,20,29],
    ["DEMO009","示例·新原通信",4,-2,null,18],
    ["DEMO010","示例·融溪物流",6,7,10,null],
  ];

  const now = () => new Date().toISOString();
  const id = () => crypto.randomUUID();
  const clone = (x) => structuredClone(x);
  const emptyState = () => ({ strategies:{}, snapshots:{}, executions:{} });
  function load() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || emptyState(); }
    catch { return emptyState(); }
  }
  function save(state) { localStorage.setItem(STORE_KEY, JSON.stringify(state)); }
  function response(body, status=200) {
    return new Response(JSON.stringify(body), {status, headers:{"Content-Type":"application/json; charset=utf-8"}});
  }
  function error(detail, status=422, category) { return response({detail, ...(category?{category}:{})}, status); }
  function condition(metric, operator, value, concept, origin="system_default", rationale="固定四条件模板；未调用 LLM，未理解任意输入语义") {
    return {condition_id:id(), concept, metric, operator, value, unit:metricMeta[metric][1], enabled:true, origin, rationale};
  }
  function template(text) {
    const t = now();
    return {
      strategy_id:id(), revision:1, source_text:text, universe,
      conditions:[
        condition("revenue_yoy",">",0,"经营改善"),
        condition("net_profit_yoy",">",0,"经营改善"),
        condition("pe_ttm","<",30,"估值合理"),
        condition("volatility_60d","<",30,"走势稳定"),
      ],
      status:"draft", created_at:t, updated_at:t,
    };
  }
  function detectConflicts(conditions) {
    const groups = {};
    for (const c of conditions.filter(c=>c.enabled)) (groups[c.metric] ||= []).push(c);
    const out = [];
    for (const [metric, group] of Object.entries(groups)) {
      let lower = -Infinity, upper = Infinity, lowerClosed=false, upperClosed=false;
      for (const c of group) {
        if ([">",">=","=="].includes(c.operator)) {
          const closed = c.operator !== ">";
          if (c.value > lower) { lower=c.value; lowerClosed=closed; }
          else if (c.value === lower) lowerClosed = lowerClosed && closed;
        }
        if (["<","<=","=="].includes(c.operator)) {
          const closed = c.operator !== "<";
          if (c.value < upper) { upper=c.value; upperClosed=closed; }
          else if (c.value === upper) upperClosed = upperClosed && closed;
        }
      }
      if (lower > upper || (lower === upper && !(lowerClosed && upperClosed))) {
        out.push({metric, condition_ids:group.map(c=>c.condition_id), reason:`${metricMeta[metric]?.[0] || metric} 的启用条件没有公共可行范围`});
      }
    }
    return out;
  }
  function snapshotSession(record) {
    const latest = record.latest_execution || null;
    const stale = !!latest && (record.strategy.status !== "executed" || latest.revision !== record.strategy.revision);
    return {strategy:clone(record.strategy), latest_execution:clone(latest), results_stale:stale,
      conflicts:detectConflicts(record.strategy.conditions), latest_run:clone(record.latest_run || latest?.run || null)};
  }
  function makeStocks() {
    const captured = now();
    return rows.map(([symbol,name,revenue,profit,pe,vol]) => {
      const vals = {revenue_yoy:revenue, net_profit_yoy:profit, pe_ttm:pe, volatility_60d:vol};
      const observations = {};
      for (const [metric,value] of Object.entries(vals)) {
        const unit = metricMeta[metric][1];
        const period = ["revenue_yoy","net_profit_yoy"].includes(metric) ? "DEMO 财报期 2026Q2" : metric === "pe_ttm" ? "DEMO 估值截面" : "DEMO 连续60交易日窗口";
        observations[metric] = {metric,value,unit,data_source:"DEMO / MOCK · 人工构造样本，非真实金融数据",retrieved_at:captured,reporting_period:period,
          missing_reason:value===null?"Mock 故意设置缺失值":null,
          evidence:{provider,field:metric,raw_value:value,normalized_value:value,unit,retrieved_at:captured,data_as_of:null,reporting_period:"DEMO / MOCK",request_id:null,calculation_method:null,calculation_inputs:{},request_performed:false,adjustment:null,error:null}};
      }
      return {symbol,name,observations};
    });
  }
  function compare(actual, op, threshold) {
    if (actual === null || actual === undefined) return null;
    return op === ">" ? actual > threshold : op === ">=" ? actual >= threshold : op === "<" ? actual < threshold : op === "<=" ? actual <= threshold : actual === threshold;
  }
  function evaluate(strategy, stocks) {
    const enabled = strategy.conditions.filter(c=>c.enabled);
    return stocks.map(stock => {
      const checks = enabled.map(c => {
        const obs = stock.observations[c.metric];
        const actual = obs?.value ?? null;
        const ok = compare(actual,c.operator,c.value);
        const status = ok === null ? "unknown" : ok ? "pass" : "fail";
        const reason = status === "unknown" ? (obs?.missing_reason || "数据缺失") : `${metricMeta[c.metric][0]} ${actual}${c.unit === "x" ? "倍" : c.unit} ${status === "pass" ? "满足" : "不满足"}条件 ${c.operator} ${c.value}${c.unit === "x" ? "倍" : c.unit}`;
        return {condition_id:c.condition_id,metric:c.metric,status,actual_value:actual,threshold:c.value,operator:c.operator,unit:c.unit,
          data_source:obs?.data_source || "DEMO / MOCK",retrieved_at:obs?.retrieved_at || null,reporting_period:obs?.reporting_period || null,reason,evidence:obs?.evidence || null};
      });
      const status = checks.some(c=>c.status==="fail") ? "excluded" : checks.some(c=>c.status==="unknown") ? "unknown" : "selected";
      const explanation = status === "selected" ? "全部启用条件均通过。" : status === "excluded" ? "至少一项启用条件不满足。" : "没有明确不通过项，但至少一项数据缺失，因此不判定为入选。";
      return {symbol:stock.symbol,name:stock.name,status,checks,explanation};
    });
  }
  function makeDiff(previous, currentResults, revision, snapshotId) {
    if (!previous) return null;
    const oldSet = new Set(previous.results.filter(r=>r.status==="selected").map(r=>r.symbol));
    const newSet = new Set(currentResults.filter(r=>r.status==="selected").map(r=>r.symbol));
    const added = [...newSet].filter(x=>!oldSet.has(x)).sort();
    const removed = [...oldSet].filter(x=>!newSet.has(x)).sort();
    const same = !!snapshotId && previous.snapshot_id === snapshotId;
    return {previous_execution_id:previous.execution_id,previous_revision:previous.revision,current_revision:revision,previous_count:oldSet.size,current_count:newSet.size,added,removed,
      previous_snapshot_id:previous.snapshot_id,current_snapshot_id:snapshotId,condition_attributable:same,
      attribution_note:same?"条件变化可归因：复用同一不可变数据快照":"本次比较同时存在数据快照变化。"};
  }
  async function handle(path, method, body) {
    const state = load();
    if (path === "/api/health" && method === "GET") return response({status:"ok",data_mode:dataMode,compiler:"fixed_demo_template"});
    if (path === "/api/config" && method === "GET") return response({product_name:"StrategyLens｜自然语言智能选股与策略解释器",provider,data_mode:dataMode,universe,ready:true,screening_scope:null,financial_report:null,compiler:"fixed_demo_template",runtime_llm:false,llm_ready:false});
    if (path === "/api/strategies/compile" && method === "POST") {
      const text = String(body?.source_text || "").trim();
      if (!text) return error("请输入选股意图");
      const strategy = template(text);
      state.strategies[strategy.strategy_id] = {strategy,latest_execution:null,latest_run:null}; save(state);
      return response(snapshotSession(state.strategies[strategy.strategy_id]),201);
    }
    let m = path.match(/^\/api\/strategies\/([^/]+)$/);
    if (m && method === "GET") {
      const rec = state.strategies[decodeURIComponent(m[1])];
      return rec ? response(snapshotSession(rec)) : error("策略不存在",404);
    }
    m = path.match(/^\/api\/strategies\/([^/]+)\/conditions$/);
    if (m && method === "PUT") {
      const sid = decodeURIComponent(m[1]), rec = state.strategies[sid]; if (!rec) return error("策略不存在",404);
      if (body?.expected_revision !== rec.strategy.revision) return error("策略版本已变化，请刷新后重试",409);
      const next = clone(body.conditions || []);
      const conflicts = detectConflicts(next);
      const changed = JSON.stringify(next) !== JSON.stringify(rec.strategy.conditions);
      if (changed) {
        rec.strategy.conditions = next.map(c=>({...c,origin:c.origin || "user_explicit",rationale:c.rationale || "用户在结构化条件编辑中修改；以当前条件为准"}));
        rec.strategy.revision += 1; rec.strategy.status = rec.latest_execution ? "stale" : "draft"; rec.strategy.updated_at = now();
      }
      rec.latest_run = rec.latest_run || null; save(state);
      const session = snapshotSession(rec); session.conflicts = conflicts; return response(session);
    }
    m = path.match(/^\/api\/strategies\/([^/]+)\/validate$/);
    if (m && method === "POST") {
      const sid=decodeURIComponent(m[1]), rec=state.strategies[sid]; if(!rec) return error("策略不存在",404);
      if (body?.expected_revision !== rec.strategy.revision) return error("策略版本已变化，请刷新后重试",409);
      const conflicts=detectConflicts(rec.strategy.conditions); if(conflicts.length) return error("条件范围冲突，请修改后执行",422);
      rec.strategy.status="validated"; rec.strategy.updated_at=now(); save(state); return response(snapshotSession(rec));
    }
    m = path.match(/^\/api\/strategies\/([^/]+)\/execute$/);
    if (m && method === "POST") {
      const sid=decodeURIComponent(m[1]), rec=state.strategies[sid]; if(!rec) return error("策略不存在",404);
      if (body?.expected_revision !== rec.strategy.revision) return error("策略版本已变化，请刷新后重试",409);
      const conflicts=detectConflicts(rec.strategy.conditions); if(conflicts.length) return error("条件范围冲突，请修改后执行",422);
      if (!rec.strategy.conditions.some(c=>c.enabled)) return error("至少启用一个条件才能执行",422);
      const previous=rec.latest_execution;
      let snapshot;
      if (!body?.refresh_data && previous?.snapshot_id && state.snapshots[previous.snapshot_id]) snapshot=state.snapshots[previous.snapshot_id];
      else {
        const captured=now(); snapshot={snapshot_id:id(),universe,provider,data_mode:dataMode,captured_at:captured,data_as_of:null,as_of_semantics:"DEMO证据使用构造时点；不代表真实市场同步时点",parameters:{fixture_version:"phase1-10-fictional-stocks"},stocks:makeStocks(),universe_evidence:null,calendar_evidence:null,issues:[],content_hash:"browser-demo"};
        state.snapshots[snapshot.snapshot_id]=snapshot;
      }
      const results=evaluate(rec.strategy,snapshot.stocks), runId=id(), completed=now();
      const counts={selected:results.filter(r=>r.status==="selected").length,excluded:results.filter(r=>r.status==="excluded").length,unknown:results.filter(r=>r.status==="unknown").length};
      const run={run_id:runId,strategy_id:sid,strategy_revision:rec.strategy.revision,snapshot_id:snapshot.snapshot_id,universe,provider,started_at:completed,completed_at:completed,data_as_of:null,status:"completed",selected_count:counts.selected,excluded_count:counts.excluded,unknown_count:counts.unknown,universe_size:results.length,processed_count:results.length,snapshot_reused:!!previous && previous.snapshot_id===snapshot.snapshot_id,issues:[]};
      rec.strategy.status="executed"; rec.strategy.updated_at=completed;
      const execution={execution_id:runId,strategy_id:sid,revision:rec.strategy.revision,executed_at:completed,data_mode:dataMode,provider,strategy_snapshot:clone(rec.strategy),results,diff:makeDiff(previous,results,rec.strategy.revision,snapshot.snapshot_id),snapshot_id:snapshot.snapshot_id,run};
      rec.latest_execution=execution; rec.latest_run=run; state.executions[runId]=execution; save(state); return response(snapshotSession(rec));
    }
    m = path.match(/^\/api\/snapshots\/([^/]+)$/);
    if (m && method === "GET") { const item=state.snapshots[decodeURIComponent(m[1])]; return item?response(item):error("策略不存在",404); }
    m = path.match(/^\/api\/executions\/([^/]+)$/);
    if (m && method === "GET") { const item=state.executions[decodeURIComponent(m[1])]; return item?response(item):error("策略不存在",404); }
    if (path.includes("/patch/") || path === "/api/strategies/interpret") return error("公开网页为固定模板 DEMO；运行时 LLM 与真实扶摇链路请见正式源码和验证记录。",422,"unsupported_intent");
    return error("接口不存在",404);
  }
  window.fetch = async (input, init={}) => {
    const url = typeof input === "string" ? new URL(input, location.origin) : new URL(input.url, location.origin);
    if (url.origin === location.origin && url.pathname.startsWith("/api/")) {
      let body = null;
      try { if (init.body) body = JSON.parse(init.body); } catch {}
      return handle(url.pathname, (init.method || "GET").toUpperCase(), body);
    }
    return originalFetch(input, init);
  };
})();
