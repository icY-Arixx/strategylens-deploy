# 同花顺扶摇接入核验 · 2026-10-28

正式产品名：StrategyLens｜自然语言智能选股与策略解释器。

## 证据层级

1. **官方文档已核验**：通过官方站点实际读取Schema，来源见下。
2. **离线契约已实现并测试**：HTTPX MockTransport提供明确合成数据，不是线上金融证据。
3. **历史状态（2026-10-28）**：当时没有HITHINK_FINANCE_API_KEY，smoke为not_verified；以下原表/性能记录保留为当时事实。
4. **新增真实验证（2026-10-29）**：仅300033.SZ的日K与PE成功；财务HTTP200/code0但目标index_id缺席，整体partial_failure。见[LIVE_SINGLE_STOCK_VALIDATION](LIVE_SINGLE_STOCK_VALIDATION.md)。未验证全量、日历或真实60日波动率。

聚合文档[llms-full.txt](https://fuyao.aicubes.cn/llms-full.txt)已实际下载到本地忽略缓存（501376字节）。读取时SHA256：`496cf554e73d66e50cbd9dffd90ee7a9d2202135b629a383da0b36a398c83971`。部分单页由浏览工具抓取超时，改用同一官方聚合文档核对，未猜测端点。未发现本机已安装官方CLI/SDK，因此实现官方REST，无需新装SDK。

## 确认能力与端点

| 需求 | 已确认官方入口 / 字段 | 约束 | 本轮真实调用 |
| --- | --- | --- | --- |
| 沪深300当前成分 | GET `/api/a-share-index/constituents/ths-stock-list?thscode=000300.SH`；data.item[].thscode/name | 单指数；不依赖手工名单 | 未验证 |
| 财务增长率 | GET `/api/a-share/financials/indicators`；thscode+report；abilities[].indicators[].index_id/value | 单股、显式YYYY-1/2/3/4 | 未验证 |
| 营业收入同比增长率 | `operating_income_yoy_growth_ratio` | 原值string/null；百分数值，不缩放 | 未验证 |
| 净利润同比增长率 | `net_profit_yoy_growth_ratio` | 同上 | 未验证 |
| 当前PE(TTM) | GET `/api/a-share/valuations/snapshot?thscodes=...`；data.item[].pe_ttm | 文档默认上限100个原始token/批；number/null；支持负数；没有历史估值接口语义 | 未验证 |
| 日K | GET `/api/a-share/prices/historical`；thscode、interval=1d、start/end毫秒、adjust | 单股；none/forward/backward；单窗不超过10年 | 未验证 |
| 交易日历 | GET `/api/a-share/calendar/trading-days`；data.item[].date_ms/date | 无参数，近一年；上海日期 | 未验证 |

来源：[指数数据](https://fuyao.aicubes.cn/docs/api-reference/a-share-index/)、[财务指标](https://fuyao.aicubes.cn/docs/api-reference/financial-indicators/)、[估值](https://fuyao.aicubes.cn/docs/api-reference/valuations/)、[价格](https://fuyao.aicubes.cn/docs/api-reference/prices/)、[交易日历](https://fuyao.aicubes.cn/docs/api-reference/calendar/)。

## 响应与错误

HTTP状态和`{code,message,request_id,data}`信封均需检查。0才是业务成功。2001认证、2003权限、5002超时；3001/3002/3004按缺失处理；其他业务错误为upstream_error；429或4001中止本轮，不连续重试。整个股票池缺失/空/畸形/失败时运行失败，不伪造正常空筛选。

未授权能力使用本轮熔断，避免对每只股票重复发同类失败请求；其他健康能力继续采集，相关指标Unknown，并在run标partial_failure。每个证据记录request_performed，熔断后没有发请求的股票不伪造独立request_id。错误message使用内部安全模板，上游原错误内容不进日志、响应或数据库。

依据：[通用约定与限流](https://fuyao.aicubes.cn/docs/api-reference/overview/)、[认证与权限说明](https://fuyao.aicubes.cn/docs/quickstart/)。

## 取数口径与不确定性

- 财务按显式`FUYAO_REPORT`同一报告期取数。本阶段不自动推断逐股最新披露报告，不增加其他财务指标。返回`"12.3400"`时raw保留原字符串，规范值12.34%，不乘/除100。null保持未知。
- 财务指标响应没有逐值披露日或as-of时间，Evidence.data_as_of保留null；报告期不能冒充披露日，retrieved_at不能冒充数据截至。
- PE使用官方pe_ttm，不用MRQ替代。估值timestamp是该批次上游元数据中的最大时间，不代表每个PE同时更新。负PE原样保留；现有`<30`仍按数值比较，其业务合理性待人工确认，不偷偷加第五项条件。
- 日K显式请求forward前复权。为统一避免当日未收盘K线，上海当日始终排除，即使收盘后也使用此前完成窗口。按官方日历取最近61个交易日；任何缺日、停牌导致的缺行、null或不足窗口都不跳过、不补0、不缩短。
- 60简单收益率为相邻收盘价比值减1；样本标准差ddof=1，乘sqrt(252)再乘100，得到百分点。calculation_method和calculation_inputs保留该定义及预期日历；raw_value只保存上游实际返回的日期/收盘价行，绝不补造空行。
- Snapshot并非PIT数据库或原子市场切片。各Evidence单独记录时间，汇总data_as_of为最晚已知时间，保留这层不确定性。

## 性能设计和全量情况

官方动态限流，当前文档没有可依赖的恒定高并发额度；文档称无累计调用次数限制，不代表用户具体Key拥有全部权限或任何速率下都可用。

本实现单进程单次筛选串行请求、默认请求开始间隔1秒、超时20秒；PE按100批处理，财务与日K按单股。若官方实际返回300成分且日历/数据完整，路径为1次成分+1次日历+3次PE+300次财务+300次日K=605次。仅节流间隔约604秒，加上传输/服务时间；**这只是调用计划估算，不能报告为实测耗时**。

离线300标的合成fixture验证上述605次分发及不截断范围，未向真实服务施压。真实全沪深300数量、成功率、耗时目前全部未验证。页面在长执行中轮询SQLite进度，不额外向扶摇重复取数；刷新页面仅读SQLite。

最小可行验证顺序：配置有效Key与报告期→显式1成分smoke（报告scope=sample）→确认能力权限及耗时→全量smoke（scope=full）。如果实测全量预算不合适，再经说明选择明确子集或离线预取，不能把子集标成完整沪深300。本轮未执行这一线上顺序，原因是缺Key。

## 快照和凭证

新采集必用新UUID，存SQLite并校验内容哈希；复用时从存储读取原快照，保留原取数时间。相同snapshot_id才可归因于条件；不同则明确标记数据快照变化。快照口径、Provider、模式、股票池或报告期不匹配时拒绝复用。

凭证仅读HITHINK_FINANCE_API_KEY环境变量，用X-api-key发送到白名单官方HTTPS端点；不跟随重定向。SecretStr掩码、业务错误安全模板与上游字符串脱敏用于避免回显；没有缓存凭证。`.env.example`无真实值；本地SQLite、缓存与smoke输出不进Git/源码ZIP。

## 实际线上核验记录

2026-10-28 19:57（Asia/Shanghai）执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_fuyao --full --output artifacts/phase2-live-smoke.json
```

结果为`not_verified`、`successful_capabilities=[]`、`full_universe_measured=false`。检查到无Key后未发真实金融请求。该报告elapsed_seconds=0.0仅指本地前置检查耗时，不是沪深300扫描耗时。没有认证失败/权限失败的线上证据，因此权限状态应写“未验证”，不能写“被拒绝”。


## 2026-10-29增量线上记录

仅3次请求，行情0.247s、PE0.881s、财务0.986s（含节流等待）；HTTP200/业务code0。财务实际返回calculate_*增长字段，与文档/当前Adapter预期不一致，不静默映射；保留Unknown。详见单股验证记录及本地脱敏raw report。未运行全量，历史not_verified记录不删除、不倒改。
