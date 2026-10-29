const METRICS = {
  revenue_yoy: { unit: "%", label: "营业收入同比" },
  net_profit_yoy: { unit: "%", label: "净利润同比" },
  pe_ttm: { unit: "x", label: "PE(TTM)" },
  volatility_60d: { unit: "%", label: "60日年化波动率" },
};
const OPS = new Set([">", ">=", "<", "<=", "=="]);
const PATCH_OPS = new Set(["update", "add", "remove", "enable", "disable"]);

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function blocked(text) {
  return /保证.*(?:收益|赚钱)|一定.*(?:涨|赚)|(?:直接|现在).*(?:买哪只|卖哪只|应该买|应该卖)|(?:明天|下周).*(?:涨停|必涨)/.test(text);
}

function ambiguousPatch(text) {
  return /严格一点|严格些|更严格|再严格|再低一点|再低些|低一点/.test(text) && !/\d/.test(text);
}

function cleanCondition(c) {
  if (!c || !METRICS[c.metric] || !OPS.has(c.operator) || !Number.isFinite(Number(c.value))) return null;
  return {
    concept: String(c.concept || METRICS[c.metric].label).slice(0, 80),
    metric: c.metric,
    operator: c.operator,
    value: Number(c.value),
    unit: METRICS[c.metric].unit,
    enabled: c.enabled !== false,
    origin: c.origin === "user_explicit" ? "user_explicit" : "llm_interpreted",
    rationale: String(c.rationale || "AI根据用户自然语言生成的待审查条件").slice(0, 500),
  };
}

function cleanInitial(raw) {
  const conditions = Array.isArray(raw?.conditions) ? raw.conditions.map(cleanCondition).filter(Boolean) : [];
  return {
    conditions,
    clarifications: Array.isArray(raw?.clarifications) ? raw.clarifications.map(String).slice(0, 5) : [],
    unsupported_requests: Array.isArray(raw?.unsupported_requests) ? raw.unsupported_requests.map(String).slice(0, 5) : [],
    compliance_status: raw?.compliance_status === "blocked" ? "blocked" : "allowed",
  };
}

function cleanPatch(raw, base) {
  const ids = new Set((base?.conditions || []).map(c => c.condition_id));
  const operations = [];
  for (const op of Array.isArray(raw?.operations) ? raw.operations : []) {
    if (!PATCH_OPS.has(op?.operation)) continue;
    if (op.operation === "add") {
      const condition = cleanCondition(op.condition);
      if (condition) operations.push({ operation: "add", condition_id: null, field: null, value: null, condition });
      continue;
    }
    if (!ids.has(op.condition_id)) continue;
    if (op.operation === "update") {
      if (!new Set(["value", "operator"]).has(op.field)) continue;
      const value = op.field === "value" ? Number(op.value) : String(op.value);
      if (op.field === "value" && !Number.isFinite(value)) continue;
      if (op.field === "operator" && !OPS.has(value)) continue;
      operations.push({ operation: "update", condition_id: op.condition_id, field: op.field, value, condition: null });
    } else {
      operations.push({ operation: op.operation, condition_id: op.condition_id, field: null, value: null, condition: null });
    }
  }
  return {
    operations,
    clarifications: Array.isArray(raw?.clarifications) ? raw.clarifications.map(String).slice(0, 5) : [],
    unsupported_requests: Array.isArray(raw?.unsupported_requests) ? raw.unsupported_requests.map(String).slice(0, 5) : [],
    compliance_status: raw?.compliance_status === "blocked" ? "blocked" : "allowed",
  };
}

const SYSTEM = `You are StrategyLens semantic compiler, not a financial advisor or market-data source.
Return JSON only. Never provide stock facts, predictions, profit guarantees, or direct buy/sell advice.
Supported metrics ONLY: revenue_yoy %, net_profit_yoy %, pe_ttm x, volatility_60d %. Operators: > >= < <= ==. All conditions are AND.
Vague defaults: 经营改善 => revenue_yoy>0 AND net_profit_yoy>0; 估值合理 => pe_ttm<30; 走势稳定/不要太波动 => volatility_60d<30.
Explicit thresholds and operators must be preserved exactly. Chinese mappings: 低于/小于=> <; 不超过/至多=> <=; 高于/大于=> >; 不低于/至少=> >=; 等于=> ==.
Unsupported metrics such as PEG, cash flow or institutional holdings go to unsupported_requests and must never be mapped to a supported metric.
For INITIAL return {conditions:[{concept,metric,operator,value,unit,enabled,origin,rationale}],clarifications:[],unsupported_requests:[],compliance_status:"allowed"}.
origin is user_explicit for explicit threshold/operator, otherwise llm_interpreted. rationale must explain the temporary interpretation.
For PATCH return {operations:[...],clarifications:[],unsupported_requests:[],compliance_status:"allowed"}. Each operation is one of:
{operation:"update",condition_id:"existing-id",field:"value"|"operator",value:number|string,condition:null}
{operation:"add",condition_id:null,field:null,value:null,condition:{concept,metric,operator,value,unit,enabled,origin,rationale}}
{operation:"remove"|"enable"|"disable",condition_id:"existing-id",field:null,value:null,condition:null}.
PATCH must modify only explicitly targeted existing IDs; “其他不变” means do not emit operations for other conditions. “PE改成20” preserves its existing operator and updates only value. Ambiguous changes such as “严格一点” without a number require clarification and empty operations.`;

export async function onRequestPost(context) {
  const key = context.env.SILICONFLOW_API_KEY;
  if (!key) return json({ detail: "AI服务凭证尚未配置", category: "llm_auth_error" }, 503);

  let body;
  try { body = await context.request.json(); }
  catch { return json({ detail: "请求格式错误" }, 400); }

  const mode = body?.mode === "patch" ? "patch" : "initial";
  const text = String(body?.text || "").trim();
  if (!text) return json({ detail: "请输入选股意图" }, 422);

  if (blocked(text)) {
    const out = mode === "patch"
      ? { operations: [], clarifications: [], unsupported_requests: ["不进行确定性涨跌预测、收益承诺或直接买卖建议"], compliance_status: "blocked" }
      : { conditions: [], clarifications: [], unsupported_requests: ["不进行确定性涨跌预测、收益承诺或直接买卖建议"], compliance_status: "blocked" };
    return json(out);
  }
  if (mode === "patch" && ambiguousPatch(text)) {
    return json({ operations: [], clarifications: ["请明确要修改的指标和新阈值；不会自行决定新阈值。"], unsupported_requests: [], compliance_status: "allowed" });
  }

  const base = body?.base || null;
  const user = mode === "patch"
    ? `TASK=PATCH\nINPUT=${JSON.stringify(text)}\nBASE=${JSON.stringify(base)}`
    : `TASK=INITIAL\nINPUT=${JSON.stringify(text)}\nUNIVERSE=000300.SH`;

  let upstream;
  try {
    upstream = await fetch("https://api.siliconflow.cn/v1/chat/completions", {
      method: "POST",
      headers: { "content-type": "application/json", "authorization": `Bearer ${key}` },
      body: JSON.stringify({
        model: context.env.STRATEGYLENS_LLM_MODEL || "Qwen/Qwen3-8B",
        stream: false,
        enable_thinking: false,
        temperature: 0,
        max_tokens: 2048,
        response_format: { type: "json_object" },
        messages: [{ role: "system", content: SYSTEM }, { role: "user", content: user }],
      }),
    });
  } catch {
    return json({ detail: "AI服务暂时不可用", category: "llm_upstream_error" }, 502);
  }

  if (upstream.status === 401 || upstream.status === 403) return json({ detail: "AI服务鉴权失败", category: "llm_auth_error" }, 502);
  if (!upstream.ok) return json({ detail: "AI服务调用失败", category: "llm_upstream_error" }, 502);

  let payload;
  try {
    const data = await upstream.json();
    const content = data?.choices?.[0]?.message?.content;
    payload = JSON.parse(content);
  } catch {
    return json({ detail: "AI返回结构无效，请换一种表达", category: "invalid_structured_output" }, 422);
  }

  const cleaned = mode === "patch" ? cleanPatch(payload, base) : cleanInitial(payload);
  const items = mode === "patch" ? cleaned.operations : cleaned.conditions;
  if (cleaned.compliance_status === "allowed" && !items.length && !cleaned.clarifications.length && !cleaned.unsupported_requests.length) {
    return json({ detail: "当前表达未能生成可审查条件，请更明确地描述指标或阈值", category: "invalid_structured_output" }, 422);
  }
  return json(cleaned);
}

export function onRequest() {
  return json({ detail: "Method Not Allowed" }, 405);
}
