# 单股真实线上验证 · 2026-10-29

范围：仅`300033.SZ`，3次真实请求；没有查询沪深300成分、交易日历、其他股票或运行全量筛选。当前进程和Windows用户级HITHINK_FINANCE_API_KEY均存在；只记录存在性，不记录值。

## 实际结果

开始时间：2026-10-29T12:56:52.199697+08:00。总墙钟耗时：3.132s（含HTTP客户端初始化）；下表单步耗时包含串行节流等待，不能解释为纯网络延迟。

| 能力 | HTTP / 业务code | 单步耗时 | request_id | 验证结果 |
| --- | --- | --- | --- | --- |
| daily_price_history | 200 / 0 | 0.247s | `d29eff7c70b3437c8a98b1d46f8e7eed` | completed |
| pe_ttm | 200 / 0 | 0.881s | `3bc15a652298466cafc9dd2f68ba5f18` | completed |
| financial_growth | 200 / 0 | 0.986s | `487f062c21794e7aa5445564fa1aee64` | contract_mismatch |

整体结论：**partial_failure**。行情与PE已验证；财务接口调用成功，但目标指标契约不一致，不能宣布真实财务筛选链路已可用。

## 日K行情

GET `/api/a-share/prices/historical`，`thscode=300033.SZ`、`interval=1d`、`adjust=forward`；时间窗口为2026-10-20至2026-10-28（上海时间，毫秒边界）。这是历史日K行情，不是实时tick。

实际返回7行，data字段：adjust、interval、item、thscode、timestamp；行字段：date_ms、open_price、high_price、low_price、close_price、volume、turnover。返回标的/interval/adjust与请求一致。

最新一根日K为2026-10-28上海零点，收盘价199.0；原始timestamp=1793116800000。日K日期是交易日标签，不表示其金融值在零点已可获得，不将其当作收盘披露时间。窗口不足60收益率，本轮没有计算波动率。

## PE(TTM)

GET `/api/a-share/valuations/snapshot?thscodes=300033.SZ`，仅一个代码。

data实际字段item、timestamp、total；PE(TTM)原值/规范值均37.137036倍。返回as-of为2026-10-29 12:56:54（UTC+8）；按照官方定义，这是所用上游指标元数据的最大有效时间，不表示所有金融指标同步更新。取数时间与as-of独立保存。

## 财务契约差异：不能静默别名映射

GET `/api/a-share/financials/indicators?thscode=300033.SZ&report=2026-2`。环境未配置FUYAO_REPORT，本次probe明确选择2026中报，仅用于单股历史报告期验证，不称为逐股最新报告。返回report回显2026-2，data字段abilities、report、thscode。

| 官方文档与当前Adapter预期index_id | 本次是否返回 |
| --- | --- |
| operating_income_yoy_growth_ratio | 否 |
| net_profit_yoy_growth_ratio | 否 |

实际growth块包括：

| 实际返回index_id | 原始字符串值 |
| --- | --- |
| calculate_operating_income_yoy_growth_ratio | 48.68190200 |
| calculate_operating_profit_yoy_growth_ratio | 80.13426100 |
| total_assets_growth_ratio | -9.6295 |
| fixed_asset_invest_expansion_ratio | -7.17198400 |
| calculate_parent_holder_net_profit_yoy_growth_ratio | 89.75554400 |

这些是本次真实返回字段，未将其映射成既有条件。特别是归母净利润名称不能未经核实直接替代原“净利润同比”口径。预期两ID是**缺席**，并非上游对这两ID显式返回null；现有Adapter将未找到的指标规范化为null/missing_data。用已采集证据本地运行既有Engine，两条件均Unknown，未补0/未改成Fail。财务响应没有data_as_of或披露时间，继续未知，报告期不能替代披露日。

## 证据、官方依据和验证边界

- 已保存脱敏raw response、参数、HTTP/业务码、request_id、取数时间、耗时和Adapter Evidence于本地忽略文件`artifacts/single-stock-live-20261029.json`；未保存请求头或Key。
- 最初probe只将HTTP/响应解析成功统计为completed，未检测预期ID缺席；人工式响应审查发现后，AI修正probe检查及报告为partial_failure。最初报告保留为同目录`.initial.json`，不掩盖这一修正；修正后没有追加线上请求。
- 线上验证与离线测试分开：本轮离线`pytest tests/test_fuyao.py -q`实际42 passed、1个既有Starlette/AnyIO弃用警告，2.27s；`py_compile`通过。离线fixture通过不能消除本次线上字段差异。未运行新一轮完整应用回归或全量线上验证。
- 官方[财务指标文档](https://fuyao.aicubes.cn/docs/api-reference/financial-indicators/)本轮成功读取，仍列上述预期ID及百分数不缩放口径；[估值文档](https://fuyao.aicubes.cn/docs/api-reference/valuations/)本轮成功读取。[行情文档](https://fuyao.aicubes.cn/docs/api-reference/prices/)本轮网页读取超时，依据原已保存官方llms-full.txt及当前Adapter调用，未猜接口。
- 既有Fuyao Client/Provider、Domain、API、UI、数据库结构均未修改；未切Mock，未接LLM。只增加有固定单股范围的probe脚本和验证文档。

已完成这次单股验证并停止。下一步需先核实官方财务字段与净利润口径，再决定是否修Adapter；本轮没有自动修复映射或扩大扫描。
