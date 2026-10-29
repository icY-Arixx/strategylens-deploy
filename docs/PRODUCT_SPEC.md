# StrategyLens｜自然语言智能选股与策略解释器 · 产品规格

## 用户问题与目标

个人投资研究者用“经营改善、估值合理、波动较小”描述意图，但这些词没有唯一数值含义。目标是让用户看见解释、修改条件、比较候选、审查证据，并分清条件变化与数据变化。不是让用户被动接受一个股票名单。产品评审者是验证参与方，不以其替代真实目标用户研究。

成功标准：用户可以准确复述自己的执行规则；能找到某股被排除或Unknown的原因；能识别结果是否过期；能在相同快照上解释修改影响。尚未进行真实用户可用性测量，不能称已验证产品市场匹配。

## 市场证据与机会点

本轮对前期市场假设做系统验证与补全，证据/时间/来源级别见 [COMPETITOR_RESEARCH](COMPETITOR_RESEARCH.md)。本轮资料不能倒填为编码前调研。

问财已有自然语言A股筛选及成熟生态。TradingView当前官方帮助明确支持自然语言转标准筛选条件、解释条件、手动调整；新的AI请求替换现有筛选状态。Koyfin的范围过滤、结果指标表、保存/导出是成熟研究流程。妙想公开资料体现AI选股与研究链路，但部分具体能力来自未确认认证身份的财富号材料，不能作官方功能承诺。

因此，**自然语言、透明筛选条件或解释本身不是创新主张**。机会点是更聚焦于规则审查、逐条件的双向证据与可归因修改体验。竞品公开资料未提及某功能，只能标“未从公开资料确认”，不能据此证明对方没有。尚需同任务实测与用户验证。

## Competitive Positioning

定位：**面向模糊投资判断落地的可审计策略工作台**。未来AI编译透明草稿，程序负责真实金融数据和确定性裁决；用户可检查意图如何被解释、每股每条件为什么进入/退出，并在同快照上判断修改影响。

| 差异候选 | 外部证据带来的判断 | 当前实现 / 待完成 |
| --- | --- | --- |
| Inspectable Compilation：先审查条件 | TradingView已有透明条件与理由，不能独立作为差异 | 已有固定模板和可编辑条件；真实语义编译未接入 |
| Condition Provenance：条件来源可查 | 所查资料未确认相同三类origin契约；不能声称竞品无来源记录 | system_default / user_explicit已用；llm_interpreted仅预留；来源轻量标签与解释弹窗 |
| Patch-based Modification：其他不变 | TradingView明确新AI请求替换筛选状态；其他产品Patch语义未确认 | 当前手动局部编辑保留ID/其余条件；自然语言Patch尚未实现 |
| Evidence by Condition：双向证据 | 竞品有条件解释/个股分析，不等同于逐条件执行证据 | 入选、排除、Unknown逐项Check及原始金融Evidence；真实线上数据仍not_verified |
| Missing ≠ Fail：三态缺失 | TradingView MCP文档也要求missing/reason，不能宣称行业无人处理缺失；其AI界面三态表达未确认 | null与0分开，Unknown独立Tab；失败+Unknown仍Excluded |
| Snapshot-controlled What-if：固定数据比较 | 公开资料未确认各竞品相同的冻结快照归因工作流 | revision+snapshot_id绑定，同ID才条件归因，更新快照显式警告 |

核心价值是上述机制的连贯体验与可审计契约，非功能总量优势；不宣称首创/独家。反向风险：过多来源字段、确认步骤与Unknown会增加认知成本，需要任务验证其收益。

## 核心方案与工作流

1. 顶部展示产品、股票池、数据模式与已知截至时间；数据标签点击可看快照和取数状态。DEMO始终可识别，缺失as-of不以取数时间冒充。
2. Command Bar描述意图；当前“示例模板”清楚提示编译边界，非空文本固定生成四条件。示例不承诺当前无法理解的任意数值输入。
3. 紧凑条件行可改操作符/阈值、启停、删除或添加已有四指标；每个条件来源和rationale可点开。添加不覆盖原条件；重复指标空交集阻止执行。
4. 操作条集中执行、保存状态、快照复用/刷新和revision。自动保存编辑，执行前用户通过按钮确认当前条件；该步骤不等于每次编辑都弹确认框。
5. 首次/显式刷新采集DataSnapshot；默认复用本策略上次快照。生成ScreeningRun并绑定策略版本；Engine逐股票逐启用条件确定性判断。
6. 结果主区域使用高密度表格，固定展示名称、代码、两项增长率、PE、波动率、满足条件数、状态、主要排除/Unknown原因；三轻量Tab切换。即使某指标条件删除/禁用，已存快照的四指标仍可比较，不为表格刷新外部接口。
7. 点击行打开Evidence Drawer。首层是实际值、执行时阈值、三态、原因、数据来源/报告期；折叠层保留完整Evidence。不用当前编辑阈值改写历史检查。
8. 编辑已执行策略立即stale；重执行显示具体条件旧→新、候选计数与进出名单；同快照才可归因。换快照即使值未变也警告。相邻比较基准为最近成功执行，不是最近一次键盘操作。
9. 页面重开只读SQLite；可读历史执行恢复修改摘要；失败运行保留历史成功结果并明确失效；真实接口失败绝不静默切DEMO。

## 技术职责边界与未来编译接口

当前保留FastAPI / Domain Engine / Adapter / SQLite / 原生前端；不推倒数据架构。Domain不依赖金融HTTP返回形状。官方Adapter只取数、规范化、保留证据；Engine负责比较；波动率由程序计算。原始缺失、错误与未发请求分别可追溯。

当前编译实现仍是fixed/mock，无运行时LLM和自然语言Patch。下一阶段接口设计（**方案，未实现**）：

- Initial Compile：输入source_text+universe+可支持指标表；返回待Schema/冲突校验的Draft及解释，不能返回股票或金融事实。
- Patch：输入基础strategy_id/revision+现有条件+新指令；返回基于condition_id的add/update/remove操作及解释；不可将整份替换伪装成局部修改。
- 程序应用Patch前检验base_revision、字段白名单、ID与冲突；未触及的条件逐字段保持。明确数值/运算符记录user_explicit并优先；模糊解释为llm_interpreted并展示假设；“严格一点”需明确建议或澄清，不能改动其他条件。
- 编译/应用Patch产生草稿或stale策略，用户审查后显式执行。真正取数与筛选不由LLM触发或裁决。Eval方案见TEST_PLAN，尚未执行真实LLM评测。

## Domain 契约

以app/domain/models.py为可执行真源；禁止额外字段、隐式布尔/字符串金融值、NaN/Inf和重复条件ID。支持四指标、五运算符和百分数百分点口径。

| 对象 | 关键字段/约束 |
| --- | --- |
| Condition | condition_id、concept、metric、operator、value、unit、enabled、origin、rationale；origin=user_explicit/llm_interpreted/system_default |
| Strategy | strategy_id、revision、source_text、universe、conditions、status、created_at、updated_at |
| Observation | metric、value/null、unit、data_source、retrieved_at、reporting_period、missing_reason、evidence |
| Evidence | provider、field/index_id、raw_value、normalized_value、unit、retrieved_at、data_as_of、reporting_period、request_id、calculation_method、calculation_inputs、adjustment、request_performed、error |
| ConditionCheck | condition_id、metric、status、actual_value/null、threshold、operator、unit、data_source、retrieved_at、reporting_period、reason、evidence；unknown与实际值缺失一致 |
| DataSnapshot | snapshot_id、universe、provider、data_mode、captured_at、data_as_of、as_of_semantics、parameters、stocks、universe_evidence、calendar_evidence、issues、content_hash |
| ScreeningRun | run_id、strategy_id、strategy_revision、snapshot_id、universe、provider、started_at、completed_at、data_as_of、status、selected/excluded/unknown_count、universe_size、processed_count、snapshot_reused、issues |
| Execution | 保留execution_id/revision及strategy_snapshot/results；新增snapshot_id和run；execution_id=run_id，revision=strategy_revision |

source旧名仅作第一阶段兼容输入/迁移别名，不作为新JSON字段输出。Condition.origin是产生方式，data_source/Evidence是金融事实来源，两者不能互换。

## 状态

| 对象/触发 | 状态或结果 |
| --- | --- |
| Strategy生成 | draft |
| 草稿显式校验通过 | validated |
| 未执行策略编辑 | draft，revision+1 |
| 执行成功（含明确的部分数据失败） | executed，保存快照绑定的结果 |
| 已执行策略修改 | stale，revision+1；保留原执行阈值与结果 |
| stale再次校验 | 仍stale；校验不能恢复历史结果有效性 |
| ScreeningRun开始 | running；先持久化，再取数 |
| 数据请求正常完成，可能有合法缺失 | completed；缺失股票/条件按三态判断 |
| 部分请求超时、权限或上游/结构失败 | partial_failure；页面告知，受影响指标Unknown |
| 整个股票池失败、认证失败、限流或执行提交失败 | failed；不产生本次正常结果，旧结果仅作历史 |

未修改保存不增revision，执行不增条件revision。执行开始使用乐观版本校验，完成时比较旧策略整份快照防止覆盖并发修改。单进程同一时间最多一次筛选；不引入分布式任务系统。

## 快照和时间

每次实际采集生成新ID，即使值恰巧相同也不伪造复用。SQLite快照表只允许新增，不提供修改接口，读取校验SHA256；已存快照是历史证据，不是永久最新值。

默认复用本策略上次快照，适合只改阈值的What-if；用户勾选刷新才重新取数。Provider、模式、股票池、报告期或计算口径不同则拒绝复用。复用真实快照不需要重新提供Key；新取数仍须凭证。

同snapshot_id → “条件变化可归因”；不同snapshot_id → “本次比较同时存在数据快照变化。” Diff比较相邻成功执行的Selected集合，added=new-old，removed=old-new，后者包含转Unknown。

各观测保留独立时间和报告期。未知as-of不以retrieved_at补充；报告期不等于披露时间。快照汇总as-of仅为最晚已知上游时间，不代表原子市场切片或PIT回放。

## 数据与错误边界

仅使用已核验的官方扶摇REST。财务显式指定报告期；PE使用pe_ttm；前复权日K对齐官方交易日历，上海当日一律排除。61收盘价形成60简单收益率，样本标准差*sqrt(252)*100。不足、缺日或null不缩窗、不补0。raw_value保存实际返回行，预期日历单独放calculation_inputs。

错误分类：authentication_error、permission_error、upstream_error、timeout、missing_data、invalid_payload；运行状态另含partial_failure。缺失是数据状态，不等同于服务失败；权限熔断跳过的后续请求通过request_performed=false明确标识。

官方接口和性能细节见FUYAO_INTEGRATION.md。当前真实股票池只允许官方返回全量成分，UI显示实际股票数；不按10股DEMO偷换范围。Mock只在明确演示或测试注入使用。

## 兼容与工程

保留本地虚拟环境、缓存和SQLite。原库先备份后迁移字段，保留版本与值；第一阶段执行没有DataSnapshot，不补造证据并标stale。AI_DEV_LOG的SL-001至SL-011历史与时间戳不改写；SL-000是本轮有证据分层的补记；本轮工作与人工确认追加新Log。

Git与最终源码ZIP排除环境、缓存、凭证、SQLite、临时输出和旧归档。正式源码、文档和必要测试资源保留。

## Non-goals 与待确认

不做新闻/公告、回测、监控、交易、行业估值、额外指标、复杂图表、LangGraph、多Agent或RAG。运行时LLM仅限Strategy Draft和局部Patch，不负责金融数值和裁决。

待确认：显式统一财务报告期是否满足评审目标、forward与ddof=1口径、负PE的产品处理、全量真实调用预算与性能、单进程长请求的进程中断恢复体验。下一阶段接LLM前须补真实线上证据和权限核验。


## 2026-10-29运行时Compiler增量

原“下一阶段Initial Compile/Patch方案”现已实现为可切换官方Provider、严格语义契约、草稿审查、签名Patch预览/确认和澄清预检；未改金融数据契约。保留Demo模式和当前UI信息架构。用户将智谱改为硅基流动后，使用官方接口与Qwen/Qwen3-8B完成真实草稿和局部Patch验证；原智谱HTTP401/code1000保留为历史记录。26条Eval及实际Bad Case见[LLM_COMPILER](LLM_COMPILER.md)。
