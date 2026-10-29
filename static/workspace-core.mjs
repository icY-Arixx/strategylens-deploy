// Display projections only. All financial pass/fail/unknown decisions come from the server.
export const METRICS = [
  {key:"revenue_yoy", label:"营业收入同比", concept:"经营改善", unit:"%", operator:">", value:0},
  {key:"net_profit_yoy", label:"净利润同比", concept:"经营改善", unit:"%", operator:">", value:0},
  {key:"pe_ttm", label:"PE(TTM)", concept:"估值", unit:"x", operator:"<", value:30},
  {key:"volatility_60d", label:"60日年化波动率", concept:"风险", unit:"%", operator:"<", value:30}
];
export const metricInfo = (metric) => METRICS.find((m) => m.key === metric);
export function groupConditions(conditions) {
  const groups = [
    {key:"quality",label:"经营质量",metrics:["revenue_yoy","net_profit_yoy"]},
    {key:"valuation-risk",label:"估值与风险",metrics:["pe_ttm","volatility_60d"]}
  ];
  const known = new Set(groups.flatMap((group) => group.metrics));
  return [...groups.map((group) => ({...group,conditions:conditions.filter((c) => group.metrics.includes(c.metric))})),
    {key:"other",label:"其他条件",conditions:conditions.filter((c) => !known.has(c.metric))}]
    .filter((group) => group.conditions.length > 0);
}
export function compilerPresentation(config) {
  if (config?.compiler === "llm" && config?.runtime_llm) return {readOnly:false,enabled:true,label:"描述选股逻辑",action:"解析策略",notice:"AI仅生成待审查条件，不自动执行；请检查阈值与AI解释。"};
  const supported = config?.compiler === "fixed_demo_template";
  return {readOnly:true,enabled:supported,label:"示例策略",action:supported ? "载入示例策略" : "编译器不可用",
    notice:supported ? "当前为固定模板，不解析任意自然语言。载入后可直接编辑条件。" : "当前编译器未就绪，暂不能载入策略。"};
}
export function dataScope(config, execution, stale=false) {
  const actualMode = execution?.data_mode;
  const count = execution?.results.length;
  const validationSample = actualMode === 'REAL' && execution?.provider?.endsWith(' / REAL Validation Sample');
  return {
    mode:config?.data_mode === "REAL" ? "扶摇真实数据 · REAL" : "演示数据 · DEMO",
    scope:validationSample ? `${stale ? '历史' : '真实'}验证样本：${count}只沪深300当前成分股（取数时成分，非完整沪深300筛选）` : execution ? `${stale ? "历史" : "实际"}样本：${count}${actualMode === "REAL" ? "只官方成分" : "只虚构样本，非真实沪深300成分或市场数据"}` : config?.data_mode === "REAL" ? config.screening_scope === 'real_validation_sample_10' ? "真实验证样本：执行时从官方沪深300当前成分中按代码升序取10只，尚未取数" : "实际样本：尚无真实筛选结果，成分数量待官方取数确认" : "实际样本：尚未载入，执行后显示数量；全部为虚构演示数据，非真实沪深300成分或市场数据",
    dataAsOf:execution?.run?.data_as_of || null
  };
}
export const unitLabel = (unit) => unit === "x" ? "倍" : unit;
export const escapeHtml = (value) => String(value ?? "—").replace(/[&<>"']/g, (c) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
export function formatNumber(value, digits=2) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value !== 0 && Math.abs(value) < 0.5 * 10 ** (-digits)) return value.toExponential(2);
  return value.toLocaleString("zh-CN", {minimumFractionDigits:digits, maximumFractionDigits:digits});
}
export function thresholdText(condition) {
  const value = Number.isFinite(condition.value) ? String(condition.value) : "—";
  return `${condition.operator} ${value}${unitLabel(condition.unit)}`;
}
export function projectRows(execution, snapshot=null) {
  const stocks = new Map((snapshot?.stocks || []).map((stock) => [stock.symbol, stock]));
  return execution.results.map((result) => {
    const observations = stocks.get(result.symbol)?.observations || {};
    const values = {};
    for (const metric of METRICS) {
      const checks = result.checks.filter((check) => check.metric === metric.key);
      const observation = observations[metric.key];
      // An explicit null observation wins. Never substitute a stale check or 0.
      const value = observation !== undefined ? observation.value : checks[0]?.actual_value;
      const status = checks.some((c) => c.status === "fail") ? "fail" : checks.some((c) => c.status === "unknown") ? "unknown" : checks.length ? "pass" : "inactive";
      values[metric.key] = {value, status, recorded:observation !== undefined || checks.length > 0,
        reportingPeriod:observation?.reporting_period || checks[0]?.reporting_period || null};
    }
    return {...result, values, passed:result.checks.filter((c) => c.status === "pass").length, total:result.checks.length};
  });
}
export function conditionChanges(previous, current) {
  const old = new Map(previous.map((c) => [c.condition_id, c]));
  const fresh = new Map(current.map((c) => [c.condition_id, c]));
  const changes = [];
  for (const before of previous) {
    const after = fresh.get(before.condition_id);
    const label = metricInfo(before.metric)?.label || before.metric;
    if (!after) { changes.push(`删除 ${label} ${thresholdText(before)}`); continue; }
    if (before.metric !== after.metric || before.operator !== after.operator || before.value !== after.value || before.unit !== after.unit) {
      changes.push(`${label} ${thresholdText(before)} → ${before.metric !== after.metric ? (metricInfo(after.metric)?.label || after.metric) + " " : ""}${thresholdText(after)}`);
    }
    if (before.enabled !== after.enabled) changes.push(`${after.enabled ? "启用" : "停用"} ${label}`);
  }
  for (const after of current) {
    if (!old.has(after.condition_id)) changes.push(`新增 ${metricInfo(after.metric)?.label || after.metric} ${thresholdText(after)}`);
  }
  return changes;
}
