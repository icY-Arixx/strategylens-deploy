import test from "node:test";
import assert from "node:assert/strict";
import {METRICS, projectRows, conditionChanges, formatNumber, escapeHtml, groupConditions, compilerPresentation, dataScope} from "../static/workspace-core.mjs";

test('REAL validation sample is explicitly bounded and never presented as a full scan',()=>{
  const view=dataScope({data_mode:'REAL'}, {data_mode:'REAL',provider:'同花顺扶摇 / official REST / REAL Validation Sample',results:Array(10).fill({}),run:{data_as_of:null}});
  assert.match(view.scope,/真实验证样本：10只沪深300当前成分股/);
  assert.match(view.scope,/非完整沪深300筛选/);assert.match(view.mode,/REAL/);assert.equal(view.dataAsOf,null);
});

const pe = {condition_id:"pe", metric:"pe_ttm", operator:"<", value:30, unit:"x", enabled:true, origin:"system_default"};
const revenue = {condition_id:"revenue", metric:"revenue_yoy", operator:">", value:0, unit:"%", enabled:true};
test("four financial columns remain available from snapshot even when conditions are disabled or deleted", () => {
  const run = {results:[{symbol:"X",status:"selected",checks:[{metric:"revenue_yoy",actual_value:12,status:"pass"}]}]};
  const snapshot = {stocks:[{symbol:"X",observations:{revenue_yoy:{value:12},net_profit_yoy:{value:8},pe_ttm:{value:18},volatility_60d:{value:22}}}]};
  const row = projectRows(run,snapshot)[0];
  assert.deepEqual(METRICS.map((m) => row.values[m.key].value),[12,8,18,22]);
  assert.equal(row.values.pe_ttm.status,"inactive");
  assert.equal(row.passed,1); assert.equal(row.total,1); assert.equal(row.status,"selected");
});
test("explicit null never becomes zero or a stale check value", () => {
  const run = {results:[{symbol:"X",status:"unknown",checks:[{metric:"pe_ttm",actual_value:18,status:"unknown"}]}]};
  const row = projectRows(run,{stocks:[{symbol:"X",observations:{pe_ttm:{value:null}}}]} )[0];
  assert.equal(row.values.pe_ttm.value,null); assert.equal(row.status,"unknown");
  assert.equal(formatNumber(null),"—"); assert.equal(formatNumber(0),"0.00");
});
test("table projection preserves server judgement rather than comparing financial numbers", () => {
  const run = {results:[{symbol:"X",status:"excluded",checks:[{metric:"pe_ttm",actual_value:1,status:"fail"}]}]};
  const row = projectRows(run)[0];
  assert.equal(row.status,"excluded"); assert.equal(row.values.pe_ttm.status,"fail");
});
test("legacy missing records stay unrecorded and duplicate metric checks still count individually", () => {
  const run = {results:[{symbol:"X",status:"excluded",checks:[{metric:"pe_ttm",actual_value:18,status:"pass"},{metric:"pe_ttm",actual_value:18,status:"fail"}]}]};
  const row = projectRows(run)[0];
  assert.equal(row.values.volatility_60d.recorded,false); assert.equal(row.values.volatility_60d.value,undefined);
  assert.equal(row.passed,1); assert.equal(row.total,2); assert.equal(row.values.pe_ttm.status,"fail");
});
test("PE threshold summary uses immutable old/new conditions and does not mutate inputs", () => {
  const before = [revenue,pe], after = [structuredClone(revenue),{...pe,value:20,origin:"user_explicit"}];
  const original = JSON.stringify({before,after});
  assert.deepEqual(conditionChanges(before,after),["PE(TTM) < 30倍 → < 20倍"]);
  assert.deepEqual(conditionChanges([{...pe,value:1.12345}],[{...pe,value:1.12346}]),["PE(TTM) < 1.12345倍 → < 1.12346倍"]);
  assert.equal(JSON.stringify({before,after}),original);
});
test("add/delete/disable/operator changes are represented, not collapsed into a regenerated strategy", () => {
  const changes = conditionChanges([revenue,pe],[{...pe,operator:"<=",enabled:false},{...revenue,condition_id:"new"}]);
  assert.deepEqual(changes,["删除 营业收入同比 > 0%","PE(TTM) < 30倍 → <= 30倍","停用 PE(TTM)","新增 营业收入同比 > 0%"]);
  assert.deepEqual(conditionChanges([pe],[{...pe,origin:"user_explicit"}]),[]);
});
test("small nonzero facts do not display as zero and text is escaped", () => {
  for (const value of [0.0000001,0.0001,0.001,0.0049,-0.001]) {
    assert.notEqual(formatNumber(value),"0.00");
    assert.notEqual(formatNumber(value),"-0.00");
  }
  assert.equal(formatNumber(0),"0.00");
  assert.equal(formatNumber(0.005),"0.01");
  assert.equal(formatNumber("0"),"—");
  assert.equal(escapeHtml('<img src=x onerror="x">'),"&lt;img src=x onerror=&quot;x&quot;&gt;");
});

test("semantic groups preserve duplicate constraints, disabled state, IDs and untouched values", () => {
  const profit = {...revenue,condition_id:"profit",metric:"net_profit_yoy"};
  const extra = {...pe,condition_id:"lower",operator:">",value:10,enabled:false};
  const input = [pe,revenue,extra,profit];
  const copy = structuredClone(input);
  const groups = groupConditions(input);
  assert.deepEqual(groups.map((g) => g.label),["经营质量","估值与风险"]);
  assert.deepEqual(groups[0].conditions,[revenue,profit]);
  assert.deepEqual(groups[1].conditions,[pe,extra]);
  assert.deepEqual(input,copy);
  assert.equal(groups.flatMap((g) => g.conditions).length,input.length);
  assert.equal(groups[1].conditions[1].enabled,false);
});

test("fixed compiler stays an explicit read-only example in both DEMO and REAL modes", () => {
  for (const data_mode of ["DEMO / MOCK","REAL"]) {
    const view = compilerPresentation({compiler:"fixed_demo_template",data_mode,runtime_llm:true});
    assert.equal(view.action,"载入示例策略");
    assert.equal(view.readOnly,true);
    assert.equal(view.enabled,true);
    assert.match(view.notice,/不解析任意自然语言/);
    assert.doesNotMatch(view.action,/AI理解|解析并生成/);
  }
});

test("unknown compiler cannot be presented as functioning natural-language understanding", () => {
  assert.equal(compilerPresentation(null).enabled,false);
  assert.equal(compilerPresentation({compiler:"unrecognized"}).enabled,false);
  assert.equal(compilerPresentation({compiler:"llm",runtime_llm:true}).enabled,true);
  assert.equal(compilerPresentation({compiler:"llm",runtime_llm:true}).readOnly,false);
});

test("DEMO actual scope derives count from saved results, never from the target universe", () => {
  for (const count of [2,10]) {
    const view = dataScope({data_mode:"DEMO / MOCK"},{data_mode:"DEMO / MOCK",results:Array(count).fill({}),run:{data_as_of:null}});
    assert.match(view.mode,/演示数据/);
    assert.match(view.scope,new RegExp(count+"只虚构样本，非真实沪深300成分或市场数据"));
    assert.equal(view.dataAsOf,null);
    assert.doesNotMatch(view.scope,/只官方成分/);
  }
});

test("unexecuted scope does not invent sample size or replace financial as-of with retrieval time", () => {
  const fresh = dataScope({data_mode:"DEMO / MOCK"},null);
  assert.match(fresh.scope,/尚未载入/);
  assert.doesNotMatch(fresh.scope,/10只/);
  const noTime = dataScope({data_mode:"REAL"},{data_mode:"REAL",results:[],executed_at:"2026-10-28T12:00:00Z",run:{data_as_of:null,retrieved_at:"2026-10-28T12:00:00Z"}});
  assert.equal(noTime.dataAsOf,null);
  const known = dataScope({data_mode:"REAL"},{data_mode:"REAL",results:[{}],run:{data_as_of:"2026-10-27T07:00:00Z"}});
  assert.equal(known.dataAsOf,"2026-10-27T07:00:00Z");
  assert.match(known.scope,/1只官方成分/);
});

test("historical DEMO records retain their identity even when the current server is REAL", () => {
  const view = dataScope({data_mode:"REAL"},{data_mode:"DEMO / MOCK",results:[{}]},true);
  assert.match(view.mode,/真实数据/);
  assert.match(view.scope,/历史样本：1只虚构样本/);
  assert.match(view.scope,/非真实沪深300/);
});
