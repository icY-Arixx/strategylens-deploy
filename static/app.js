import {METRICS, metricInfo, unitLabel, escapeHtml as esc, formatNumber as fmt, thresholdText, projectRows, conditionChanges, groupConditions, compilerPresentation, dataScope} from "/static/workspace-core.mjs";
const $ = (s) => document.querySelector(s);
const originNames = {user_explicit:"用户明确设置", llm_interpreted:"AI解释", system_default:"系统默认"};
const stateNames = {draft:"草稿 · 待确认", validated:"已校验", executed:"已执行", stale:"待重新筛选"};
const stockNames = {selected:"入选", excluded:"排除", unknown:"数据不足"};
const checkNames = {pass:"通过 · Pass", fail:"不通过 · Fail", unknown:"数据不足 · Unknown"};
let session = null, draft = [], config = null, tab = "selected", busy = false, dirty = false;
let version = 0, savePromise = null, saveTimer = null, activeStock = null;
const snapshots = new Map(), executions = new Map(), pending = new Map(), loadErrors = new Map();
let proposedPatch = null, semanticBlocked = false;
const oldResults = () => !!session?.latest_execution && (dirty || session.results_stale);
const time = (value) => value ? new Date(value).toLocaleString("zh-CN", {timeZone:"Asia/Shanghai", hour12:false}) : "未提供";
function showError(message) { $("#message").textContent = message; $("#message").hidden = false; }
function clearError() { $("#message").hidden = true; }
async function api(path, method="GET", body) {
  const response = await fetch(path, {method, headers:{"Content-Type":"application/json"}, ...(body ? {body:JSON.stringify(body)} : {})});
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join("；") : data.detail;
    const error = new Error(detail || "请求未完成"); error.status = response.status; error.category = data.category; throw error;
  }
  return data;
}
function remember() { try { localStorage.setItem("strategylens.session", session.strategy.strategy_id); } catch {} }
function rememberExecution(execution) { if (execution) executions.set(execution.execution_id, execution); }
function loadArtifact(key, path, cache, id) {
  if (cache.has(id) || pending.has(key)) return;
  pending.set(key, api(path).then((data) => { cache.set(id, data); }).catch((error) => { cache.set(id, null); loadErrors.set(key,error.message); }).finally(() => { pending.delete(key); renderResults(); renderMeta(); }));
}
function hydrate(execution) {
  if (!execution) return;
  rememberExecution(execution);
  if (execution.snapshot_id) loadArtifact("snapshot:"+execution.snapshot_id, "/api/snapshots/"+encodeURIComponent(execution.snapshot_id), snapshots, execution.snapshot_id);
  const previousId = execution.diff?.previous_execution_id;
  if (previousId) loadArtifact("execution:"+previousId, "/api/executions/"+encodeURIComponent(previousId), executions, previousId);
}
function renderHeader() {
  if (!config) return;
  const scope = dataScope(config,session?.latest_execution,oldResults());
  $("#data-status").textContent = scope.mode;
  $("#data-status").classList.toggle("demo",config.data_mode !== "REAL");
  $("#universe-label").textContent = "目标范围：沪深300";
  $("#scope-description").textContent = scope.scope;
  $("#as-of").textContent = scope.dataAsOf ? "数据截至：" + time(scope.dataAsOf) : "数据截至：未知";
  $("#as-of").title = "以金融证据截至时间为准，不以取数时间代替；各指标时点可能不同。";
  const compiler = compilerPresentation(config);
  $("#intent").readOnly = compiler.readOnly;
  $("#compiler-status").textContent = config.runtime_llm ? "AI解释说明" : "固定模板说明";
  $("#patch-tools").hidden = !config.runtime_llm || !session;
  $("#intent-label").textContent = compiler.label;
  $("#compile").textContent = compiler.action;
  $("#compiler-notice").textContent = compiler.notice + (config.runtime_llm && !config.llm_ready ? " 模型凭证未就绪，解析将明确报错。" : "");
}
function renderConditions() {
  if (!session) return;
  const row = (c) => {
    const i = draft.findIndex((item) => item.condition_id === c.condition_id);
    const name = metricInfo(c.metric)?.label || c.metric;
    return `<div class="condition-row ${c.enabled ? "" : "disabled"}" data-id="${esc(c.condition_id)}"><input type="checkbox" data-field="enabled" ${c.enabled ? "checked" : ""} aria-label="启用${esc(name)}"><label class="metric-name" for="threshold-${i}">${esc(name)}</label><select class="operator" data-field="operator" aria-label="${esc(name)}比较运算符">${[">",">=","<","<=","=="].map((op) => `<option value="${esc(op)}" ${op === c.operator ? "selected" : ""}>${esc(op)}</option>`).join("")}</select><input class="threshold" id="threshold-${i}" data-field="value" type="number" step="any" value="${c.value ?? ""}" aria-label="${esc(name)}阈值"><span class="unit">${unitLabel(c.unit)}</span><button class="origin-button ${c.origin === "llm_interpreted" ? "ai" : ""}" data-origin title="${esc(originNames[c.origin])} · 查看来源与解释" aria-label="${esc(name)}条件说明">${c.origin === "llm_interpreted" ? "AI解释" : "ⓘ"}</button><button class="icon-button" data-delete title="删除条件" aria-label="删除${esc(name)}">×</button></div>`;
  };
  $("#conditions").innerHTML = draft.length ? groupConditions(draft).map((group) => `<section class="condition-group" aria-label="${esc(group.label)}"><h3 class="group-heading">${esc(group.label)}</h3>${group.conditions.map(row).join("")}</section>`).join("") : '<p class="empty-conditions">当前没有条件。添加至少一项启用条件后才能执行。</p>';
}
function renderMeta() {
  renderHeader();
  $("#compile").disabled = busy || !!savePromise || dirty || !compilerPresentation(config).enabled;
  $("#add-condition").disabled = busy || !session || draft.length >= 30;
  $("#refresh-data").disabled = busy;
  $("#execute").disabled = busy || semanticBlocked || !session || !draft.some((c) => c.enabled) || (!dirty && session.conflicts.length > 0);
  if (!session) { $("#conditions").textContent = config?.runtime_llm ? "输入选股意图并解析，审查条件后再执行。" : "载入示例策略后可编辑条件。"; return; }
  const status = oldResults() ? "stale" : dirty ? "draft" : session.strategy.status;
  $("#strategy-status").textContent = stateNames[status]; $("#strategy-status").className = "status " + status;
  $("#condition-count").textContent = `${draft.filter((c) => c.enabled).length}/${draft.length} 项启用`;
  $("#strategy-meta").textContent = `策略 v${session.strategy.revision}`;
  $("#strategy-meta").title = session.strategy.strategy_id;
  $("#save-state").textContent = savePromise ? "保存中…" : dirty ? "修改待保存" : "已自动保存";
  $("#save-state").classList.toggle("dirty",dirty);
  $("#execute").textContent = busy ? "处理中…" : oldResults() ? "重新执行筛选" : "执行筛选";
  const run = session.latest_execution;
  $("#snapshot-state").textContent = run?.snapshot_id ? `快照 ${run.snapshot_id.slice(0,8)} · ${$("#refresh-data").checked ? "将更新" : "将复用"}` : "首次执行将获取数据";
  $("#snapshot-state").title = run?.snapshot_id || "";
  $("#conditions").querySelectorAll("input,select,button").forEach((el) => { el.disabled = busy; });
  $("#conditions").querySelectorAll("[data-id]").forEach((row) => {
    const condition = draft.find((c) => c.condition_id === row.dataset.id);
    const button = row.querySelector("[data-origin]");
    button.textContent = condition.origin === "llm_interpreted" ? "AI解释" : "ⓘ";
    button.title = originNames[condition.origin] + " · 查看来源与解释";
    button.classList.toggle("ai",condition.origin === "llm_interpreted");
  });
  const conflicts = dirty ? [] : session.conflicts;
  $("#conflicts").hidden = !conflicts.length;
  $("#conflicts").textContent = conflicts.map((c) => c.reason).join("；");
}
function renderRunState() {
  const run = session?.latest_run;
  const visible = !!run && (busy || ["failed","partial_failure","running"].includes(run.status));
  $("#run-state").hidden = !visible;
  if (!run) return;
  const label = {running:"正在获取数据", completed:"已完成", partial_failure:"部分数据调用失败，相关指标保留为未知", failed:"筛选未完成"}[run.status];
  $("#run-state").className = "run-state " + run.status;
  $("#run-state").textContent = `${label}${run.universe_size ? ` · ${run.processed_count}/${run.universe_size} 只` : ""}${run.status === "failed" ? " · 点击顶部数据状态查看原因" : ""}`;
}
function renderDiff(execution) {
  const diff = execution.diff;
  $("#diff").hidden = !diff;
  if (!diff) return;
  const previous = executions.get(diff.previous_execution_id);
  const changes = previous ? conditionChanges(previous.strategy_snapshot.conditions, execution.strategy_snapshot.conditions) : null;
  const title = changes ? changes.length ? "本次修改：" + changes.slice(0,2).join("；") + (changes.length > 2 ? `，另${changes.length-2}项` : "") : "本次条件未改动" : executions.has(diff.previous_execution_id) ? "历史条件记录未能载入，数量比较仍保留" : "正在载入条件修改记录…";
  const attribution = diff.condition_attributable ? "使用同一数据快照 · 差异可归因于条件变化" : diff.previous_snapshot_id && diff.current_snapshot_id ? "数据快照同时更新 · 本次差异不能全部归因于策略修改" : "历史执行未记录快照 · 无法确认变化归因";
  const nameFor = (symbol) => execution.results.find((s) => s.symbol === symbol)?.name || symbol;
  $("#diff").innerHTML = `<span class="change-title" title="${esc(changes?.join("；") || "")}">${esc(title)}</span><span class="delta-count">入选 ${diff.previous_count} → ${diff.current_count} · 新增 ${diff.added.length} · 新排除 ${diff.removed.length}</span><span class="attribution ${diff.condition_attributable ? "" : "warning"}">${esc(attribution)}${oldResults() ? " · 以下为历史比较" : ""}</span><details><summary>查看进出名单</summary><p>新增：${esc(diff.added.map(nameFor).join("、") || "无")}<br>新排除：${esc(diff.removed.map(nameFor).join("、") || "无")}（离开原入选集，含转为数据不足）</p>${changes?.length ? `<p>${changes.map(esc).join("；")}</p>` : ""}</details>`;
}
function renderResults() {
  const execution = session?.latest_execution;
  renderRunState();
  for (const state of ["selected","excluded","unknown"]) {
    $(`#count-${state}`).textContent = execution ? execution.results.filter((r) => r.status === state).length : "—";
    const button = $(`#tab-${state}`); button.classList.toggle("active",tab === state); button.setAttribute("aria-selected",String(tab === state)); button.tabIndex = tab === state ? 0 : -1;
  }
  $("#results-list").setAttribute("aria-labelledby", "tab-"+tab);
  $("#stale").hidden = !oldResults();
  if (oldResults()) $("#stale").textContent = session.latest_run?.status === "failed" ? "最新筛选失败。表中保留上次成功执行的历史结果。" : `条件已修改，表中为 v${execution.revision} 历史结果。重新执行后更新。`;
  if (!execution) {
    $("#diff").hidden = true;
    $("#scope-caption").textContent = "";
    const failed = session?.latest_run?.status === "failed";
    $("#result-version").textContent = failed ? "未产生有效结果" : "尚未执行";
    $("#results-list").innerHTML = `<div class="empty-results"><h3>${failed ? "本次未生成筛选结果" : session ? "条件已生成，等待确认执行" : "等待筛选"}</h3><p>${failed ? "请查看数据状态中的失败原因。系统不会切换为演示数据。" : "确认上方条件后执行，金融指标与判断依据将在这里展示。"}</p></div>`;
    $("#execution-meta").textContent = failed ? "取数失败，未生成当前结果。" : "结果、来源与时间将随执行记录保存。";
    return;
  }
  hydrate(execution);
  const snapshot = snapshots.get(execution.snapshot_id);
  const rows = projectRows(execution, snapshot).filter((row) => row.status === tab);
  const loading = execution.snapshot_id && !snapshots.has(execution.snapshot_id);
  $("#result-version").textContent = `结果 v${execution.revision} · ${oldResults() ? "历史" : "当前"}`;
  $("#scope-caption").textContent = `${execution.data_mode === "REAL" ? execution.provider.endsWith(' / REAL Validation Sample') ? "真实验证样本 · 沪深300当前成分（取数时）" : "官方成分" : "DEMO虚构样本"} · 共 ${execution.results.length} 只`;
  $("#results-list").innerHTML = `<table><thead><tr><th scope="col">股票名称</th><th scope="col">股票代码</th>${METRICS.map((m) => `<th scope="col" class="numeric">${esc(m.label)}${m.unit === "%" ? " (%)" : " (倍)"}</th>`).join("")}<th scope="col" class="numeric">满足条件</th><th scope="col">状态</th><th scope="col">主要依据</th></tr></thead><tbody>${rows.map((row) => `<tr data-symbol="${esc(row.symbol)}" class="${activeStock === row.symbol ? "is-selected" : ""}" aria-selected="${activeStock === row.symbol}" tabindex="0" aria-label="查看${esc(row.name)}判断依据"><td><button class="stock-open" data-symbol="${esc(row.symbol)}">${esc(row.name)}</button></td><td class="stock-code">${esc(row.symbol)}</td>${METRICS.map((metric) => { const v = row.values[metric.key]; return `<td class="numeric ${v.status}" title="${esc(v.recorded ? `实际值：${v.value ?? "缺失"}；${v.reportingPeriod || "报告期未提供"}` : loading ? "正在读取快照" : "该指标在历史记录中未保存")}">${v.recorded ? fmt(v.value) : loading ? "…" : "未记录"}</td>`; }).join("")}<td class="check-ratio">${row.passed} / ${row.total}</td><td><span class="result-status ${row.status}">${stockNames[row.status]}</span></td><td class="reason-cell">${esc(row.explanation)}</td></tr>`).join("")}</tbody></table>${rows.length ? "" : `<div class="empty-results"><h3>该分类暂无股票</h3><p>当前结果共 ${execution.results.length} 只，可切换分类查看。</p></div>`}`;
  $("#execution-meta").textContent = `${execution.data_mode === "REAL" ? "同花顺扶摇" : "DEMO虚构数据，非真实沪深300"} · 执行 ${time(execution.executed_at)} · ${rows.length} 只${stockNames[tab]}${snapshot ? " · 已保存证据快照" : execution.snapshot_id ? loading ? " · 正在读取快照证据" : " · 快照载入失败，已保留执行记录" : " · 历史记录无快照"}`;
  renderDiff(execution);
}
function renderAll() { renderConditions(); renderMeta(); renderResults(); }
function modified() {
  proposedPatch = null; $("#patch-preview").hidden = true;
  dirty = true; version += 1; clearError(); renderMeta(); renderResults();
  clearTimeout(saveTimer); saveTimer = setTimeout(() => { persist().catch((error) => showError(error.status === 409 ? "策略已在其他窗口更新，请刷新后重新编辑。当前修改尚未覆盖服务器。" : error.message)); },400);
}
async function persist() {
  clearTimeout(saveTimer);
  if (savePromise) return savePromise;
  const job = async () => {
    while (dirty) {
      if (draft.some((c) => c.value === null || !Number.isFinite(c.value))) throw new Error("请补全有效数值后再执行，空值不会自动变成0。");
      const captured = version;
      const response = await api(`/api/strategies/${session.strategy.strategy_id}/conditions`,"PUT",{expected_revision:session.strategy.revision,conditions:structuredClone(draft)});
      session = response;
      if (version === captured) { draft = structuredClone(response.strategy.conditions); dirty = false; }
      renderMeta(); renderResults();
    }
  };
  savePromise = job(); renderMeta();
  try { await savePromise; } finally { savePromise = null; renderMeta(); }
}
$("#conditions").addEventListener("input", (event) => {
  if (event.target.dataset.field !== "value") return;
  const c = draft.find((item) => item.condition_id === event.target.closest("[data-id]").dataset.id);
  c.value = event.target.value === "" ? null : event.target.valueAsNumber; modified();
});
$("#conditions").addEventListener("change", (event) => {
  const field = event.target.dataset.field;
  if (!["enabled","operator"].includes(field)) return;
  const row = event.target.closest("[data-id]"), c = draft.find((item) => item.condition_id === row.dataset.id);
  c[field] = field === "enabled" ? event.target.checked : event.target.value;
  row.classList.toggle("disabled",!c.enabled); modified();
});
$("#conditions").addEventListener("click", (event) => {
  const row = event.target.closest("[data-id]"); if (!row) return;
  const c = draft.find((item) => item.condition_id === row.dataset.id);
  if (event.target.closest("[data-delete]")) { draft = draft.filter((item) => item.condition_id !== c.condition_id); renderConditions(); modified(); }
  if (event.target.closest("[data-origin]")) {
    $("#origin-title").textContent = metricInfo(c.metric)?.label || c.metric;
    $("#origin-content").innerHTML = `<span class="source-label">${esc(originNames[c.origin])}</span><p>${esc(c.rationale)}</p><p>当前条件：${esc(thresholdText(c))}。${c.enabled ? "参与下次筛选。" : "已停用，不参与下次筛选。"}</p>`;
    $("#condition-details").showModal();
  }
});
$("#compiler-status").addEventListener("click", () => {
  $("#origin-title").textContent = "当前输入能力";
  $("#origin-content").innerHTML = config.runtime_llm ? '<p>AI将自然语言编译为待审查条件。AI解释表示模糊意图的暂定解释，明确条件优先；金融事实和入选判断由程序完成。</p>' : '<p>当前使用固定四条件模板，不解析任意自然语言。生成后请逐项确认；明确数值可以直接在条件行中修改。</p><p>语义编译与自然语言局部修改尚未接入。此处不会将模板行为标为AI理解。</p>';
  $("#condition-details").showModal();
});
$("#new-metric").innerHTML = METRICS.map((m) => `<option value="${m.key}">${m.label}</option>`).join("");
function configureNewMetric() { const m = metricInfo($("#new-metric").value); $("#new-operator").value = m.operator; $("#new-value").value = m.value; $("#new-unit").textContent = unitLabel(m.unit); }
$("#new-metric").addEventListener("change",configureNewMetric);
$("#add-condition").addEventListener("click", () => { $("#new-metric").value = "pe_ttm"; configureNewMetric(); $("#condition-dialog").showModal(); });
$("#add-form").addEventListener("submit", (event) => {
  event.preventDefault(); const m = metricInfo($("#new-metric").value), value = $("#new-value").valueAsNumber;
  if (!Number.isFinite(value) || draft.length >= 30) return;
  draft.push({condition_id:crypto.randomUUID(),concept:m.concept,metric:m.key,operator:$("#new-operator").value,value,unit:m.unit,enabled:true,origin:"user_explicit",rationale:"用户手动添加的结构化条件"});
  $("#condition-dialog").close(); renderConditions(); modified();
});
$("#intent-form").addEventListener("submit",async (event) => {
  event.preventDefault();
  if (!compilerPresentation(config).enabled) return;
  busy = true; clearError(); renderMeta();
  try {
    await persist();
    if (config.runtime_llm) {
      const result = await api("/api/strategies/interpret","POST",{source_text:$("#intent").value});
      showSemantic(result.semantic);
      if (!result.session) return;
      session = result.session;
    } else session = await api("/api/strategies/compile","POST",{source_text:"经营改善、估值合理，同时最近走势不要太波动"});
    draft = structuredClone(session.strategy.conditions); $("#intent").value = session.strategy.source_text; dirty = false; tab = "selected"; activeStock = null; $("#refresh-data").checked = false;
    remember();
  } catch (error) { showError(error.message); }
  finally { busy = false; renderAll(); }
});
$("#refresh-data").addEventListener("change",renderMeta);
$("#execute").addEventListener("click",async () => {
  busy = true; clearError(); renderMeta(); let polling = false;
  const poll = setInterval(async () => {
    if (polling) return; polling = true;
    try { const current = await api(`/api/strategies/${session.strategy.strategy_id}`); session.latest_run = current.latest_run; renderRunState(); } catch {} finally { polling = false; }
  },2000);
  try {
    await persist();
    if (session.conflicts.length) throw new Error("条件范围冲突，请修改后再执行。");
    rememberExecution(session.latest_execution);
    session = await api(`/api/strategies/${session.strategy.strategy_id}/execute`,"POST",{expected_revision:session.strategy.revision,refresh_data:$("#refresh-data").checked});
    tab = "selected"; activeStock = null; $("#drawer").close();
  } catch (error) {
    showError(error.status === 409 ? "策略版本已变化，请检查最新条件后再执行。" : error.message);
    if (!dirty) {
      try { session = await api(`/api/strategies/${session.strategy.strategy_id}`); draft = structuredClone(session.strategy.conditions); } catch {}
    }
  } finally { clearInterval(poll); busy = false; renderAll(); }
});
function openDrawer(symbol) {
  const execution = session?.latest_execution, stock = execution?.results.find((s) => s.symbol === symbol);
  if (!stock) return;
  activeStock = symbol;
  $("#results-list").querySelectorAll("tr[data-symbol]").forEach((row) => { row.classList.toggle("is-selected",row.dataset.symbol === symbol); row.setAttribute("aria-selected",String(row.dataset.symbol === symbol)); });
  $("#drawer-title").textContent = stock.name;
  $("#drawer-subtitle").textContent = `${symbol} · ${stockNames[stock.status]} · ${oldResults() ? "历史" : "当前"} v${execution.revision}`;
  $("#drawer-content").innerHTML = `<div class="drawer-summary ${oldResults() ? "warning" : ""}">${esc(stock.explanation)}${oldResults() ? "。当前条件已变化或执行失败，请重新筛选。" : ""}</div>${stock.checks.map((c) => {
    const ev = c.evidence;
    return `<article class="evidence-item"><div class="evidence-title"><h3>${esc(metricInfo(c.metric)?.label || c.metric)}</h3><span class="check-status ${c.status}">${checkNames[c.status]}</span></div><div class="evidence-values"><div><small>实际值</small><strong>${c.actual_value === null ? "缺失" : fmt(c.actual_value) + unitLabel(c.unit)}</strong></div><div><small>执行时条件</small><strong>${esc(thresholdText({...c,value:c.threshold}))}</strong></div></div><p class="evidence-reason">${esc(c.reason)}</p><p class="evidence-date">${esc(c.reporting_period || "报告期未提供")} · ${esc(c.data_source)}</p><details><summary>查看完整证据</summary><dl><dt>condition_id</dt><dd>${esc(c.condition_id)}</dd><dt>provider</dt><dd>${esc(ev?.provider)}</dd><dt>field / index_id</dt><dd>${esc(ev?.field)}</dd><dt>reporting_period</dt><dd>${esc(c.reporting_period)}</dd><dt>data_as_of</dt><dd>${esc(time(ev?.data_as_of))}</dd><dt>retrieved_at</dt><dd>${esc(time(c.retrieved_at))}（UTC+8）</dd><dt>request_id</dt><dd>${esc(ev?.request_id)}</dd><dt>calculation_method</dt><dd>${esc(ev?.calculation_method)}</dd><dt>adjustment</dt><dd>${esc(ev?.adjustment)}</dd><dt>request_performed</dt><dd>${ev ? ev.request_performed ? "已发外部请求" : "未发外部请求" : "历史未记录"}</dd><dt>错误类别</dt><dd>${esc(ev?.error?.category)}</dd></dl>${ev ? `<pre>${esc(JSON.stringify({raw_value:ev.raw_value,normalized_value:ev.normalized_value,calculation_inputs:ev.calculation_inputs,error:ev.error},null,2))}</pre>` : '<p>历史记录没有完整Evidence，不补造证据。</p>'}</details></article>`;
  }).join("")}<p class="drawer-footnote">仅展示该次执行的启用条件。${execution.data_mode === "REAL" ? "各数据时点不同，以每项证据为准。" : "本结果使用DEMO虚构数据，并非真实股票数据。"}</p>`;
  if (!$("#drawer").open) $("#drawer").showModal();
}
$("#results-list").addEventListener("click", (event) => { const row = event.target.closest("[data-symbol]"); if (row) openDrawer(row.dataset.symbol); });
$("#results-list").addEventListener("keydown", (event) => { if (!["Enter"," "].includes(event.key) || event.target.tagName !== "TR") return; event.preventDefault(); openDrawer(event.target.dataset.symbol); });
$("#close-drawer").addEventListener("click", () => $("#drawer").close());
function showDataDetails() {
  const execution = session?.latest_execution, run = session?.latest_run, snapshot = snapshots.get(execution?.snapshot_id);
  $("#data-content").innerHTML = `<dl><dt>服务端模式</dt><dd>${esc(config?.data_mode === "REAL" ? "真实数据 · 同花顺扶摇" : "DEMO · 虚构样本")}</dd><dt>当前结果模式</dt><dd>${esc(execution?.data_mode || (run?.status === "failed" ? "无有效结果" : "尚无结果"))}</dd><dt>目标范围</dt><dd>沪深300</dd><dt>执行股票池</dt><dd>${esc(config?.universe)}</dd><dt>范围说明</dt><dd>${esc(dataScope(config,execution,oldResults()).scope)}</dd><dt>财务报告期</dt><dd>${esc(config?.financial_report || snapshot?.parameters?.report || "未配置/不适用")}</dd><dt>数据截至</dt><dd>${esc(time(execution?.run?.data_as_of))}（各值并非同时更新）</dd><dt>Snapshot</dt><dd>${esc(execution?.snapshot_id || "无")}</dd><dt>执行记录</dt><dd>${esc(run?.run_id || "无")}</dd><dt>Provider</dt><dd>${esc(execution?.provider || config?.provider)}</dd></dl><p>${config?.data_mode === "REAL" ? config.ready ? "凭证与报告期已配置，不代表线上权限和全量性能已经验证。" : "凭证或报告期未就绪，真实线上仍未验证。" : "全部样本均为虚构DEMO，不是当前沪深300成分或市场事实。"}查看页面只读已保存数据，取数失败不会回退Mock。</p><p>默认复用本策略上次不可变快照。勾选重新获取数据会生成新快照。原始值和缺失记录均随快照保留。</p>${execution?.snapshot_id ? `<p><a href="/api/snapshots/${encodeURIComponent(execution.snapshot_id)}" target="_blank" rel="noopener">查看已保存快照 JSON ↗</a></p>` : ""}${run?.issues.length ? `<details><summary>查看调用问题（${run.issues.length}）</summary><pre>${esc(JSON.stringify(run.issues,null,2))}</pre></details>` : ""}${loadErrors.size ? `<p>部分历史资料未能载入：${esc([...loadErrors.values()].join("；"))}</p>` : ""}`;
  $("#data-dialog").showModal();
}
$("#data-status").addEventListener("click",showDataDetails);
$("#data-dialog").addEventListener("close",clearError);
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $("#"+button.dataset.close).close()));
document.querySelectorAll("dialog").forEach((dialog) => dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); }));
document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => { tab = button.dataset.tab; renderResults(); });
  button.addEventListener("keydown", (event) => {
    if (!["ArrowLeft","ArrowRight"].includes(event.key)) return; event.preventDefault();
    const names = ["selected","excluded","unknown"]; tab = names[(names.indexOf(tab)+(event.key === "ArrowRight" ? 1 : 2))%3]; renderResults(); $("#tab-"+tab).focus();
  });
});
window.addEventListener("beforeunload", (event) => { if (dirty || savePromise) { event.preventDefault(); event.returnValue = ""; } });
async function initialize() {
  try {
    config = await api("/api/config"); renderHeader();
    let id = new URLSearchParams(location.search).get("strategy_id"); try { id ||= localStorage.getItem("strategylens.session"); } catch {}
    if (id) {
      try { session = await api("/api/strategies/"+encodeURIComponent(id)); draft = structuredClone(session.strategy.conditions); $("#intent").value = session.strategy.source_text; }
      catch (error) { showError(config.runtime_llm ? "上次工作台未能恢复，可重新解析策略。" : "上次工作台未能恢复，可重新载入示例策略。"); }
    }
    renderAll();
  } catch (error) { showError("无法读取运行配置，请确认本地服务已启动。"); }
}
initialize();

function showSemantic(semantic) {
  semanticBlocked = semantic.compliance_status === "blocked" || semantic.clarifications.length > 0;
  const intro = semantic.compliance_status === "blocked" ? "不进行确定性涨跌预测、收益承诺或直接买卖建议。" : semantic.clarifications.length ? "请先明确以下问题，当前策略尚未修改。" : semantic.operations?.length ? "请审查下方修改，确认后才会应用。" : semantic.conditions?.length ? "AI将你的要求理解为以下条件，请审查后执行。" : "以下要求暂不能转换为可执行条件。";
  const messages = [intro,...semantic.clarifications,...semantic.unsupported_requests];
  $("#semantic-notice").textContent = messages.join("\n"); $("#semantic-notice").hidden = false;
}
$("#patch-form").addEventListener("submit",async event => {
  event.preventDefault(); if (!session || busy) return;
  busy = true; proposedPatch = null; $("#patch-preview").hidden = true; clearError(); renderMeta();
  try {
    await persist();
    const id = session.strategy.strategy_id, revision = session.strategy.revision;
    const result = await api(`/api/strategies/${id}/patch/preview`,"POST",{source_text:$("#patch-intent").value,expected_revision:revision});
    showSemantic(result.semantic);
    if (result.preview_conditions) {
      $("#patch-summary").textContent = conditionChanges(session.strategy.conditions,result.preview_conditions).join("；") + (result.conflicts.length ? "；条件冲突，请调整指令" : "");
      $("#patch-preview").hidden = false;
      $("#apply-patch").disabled = !result.proposal_token;
      proposedPatch = result.proposal_token ? {id,revision,token:result.proposal_token} : null;
    }
  } catch(error) { showError(error.message); }
  finally { busy = false; renderMeta(); }
});
$("#apply-patch").addEventListener("click",async () => {
  if (!proposedPatch || busy) return;
  busy = true; renderMeta();
  try {
    const p = proposedPatch;
    session = await api(`/api/strategies/${p.id}/patch/apply`,"POST",{expected_revision:p.revision,proposal_token:p.token});
    draft = structuredClone(session.strategy.conditions); dirty = false; proposedPatch = null;
    $("#patch-preview").hidden = true; semanticBlocked = false;
  } catch(error) { showError(error.message); }
  finally { busy = false; renderAll(); }
});
