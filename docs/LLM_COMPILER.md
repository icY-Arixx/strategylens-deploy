# 运行时策略编译器与验证记录

最终冻结说明：现有26条是Development Evaluation。最终新句式出现>=方向反转，未通过继续调Prompt掩盖；用户额度用尽后停止所有新增模型调用。最终演示采用显式草稿审查修正、既有真实Patch重放及真实缓存快照，详见[FINAL_VALIDATION](FINAL_VALIDATION.md)。不能将本文件早期固定集100%视为泛化保证。

日期：2026-10-29。LLM负责语义草稿，程序负责金融事实/判断。未改Fuyao、Domain、Snapshot/Evidence或SQLite结构。下文保留智谱失败历史，当前Provider已按用户要求切到硅基流动。

## 运行配置

- `STRATEGYLENS_COMPILER=demo`：明确固定模板，DemoStrategyCompiler；兼容旧StrategyCompiler导入。
- `STRATEGYLENS_COMPILER=llm`：LLMStrategyCompiler；`STRATEGYLENS_LLM_PROVIDER=siliconflow`（当前默认Provider），模型默认`Qwen/Qwen3-8B`；凭证只读`SILICONFLOW_API_KEY`。
- 智谱可显式选`STRATEGYLENS_LLM_PROVIDER=zhipu`，独立读取`ZHIPU_API_KEY`，其默认模型为`glm-4.7-flash`；若覆盖模型变量，须与所选Provider匹配。不猜测凭证归属、不跨Provider尝试或自动切换。
- Windows用户变量改动不更新已运行进程，须重启FastAPI；`scripts/start_llm.ps1`会安全读取已知用户变量。凭证不放到命令参数/浏览器/源码/文档，.env.example不含值。
- `STRATEGYLENS_LLM_MODEL`可显式指定模型名。金融Provider与Compiler独立配置，真实金融失败不会改Demo，LLM失败也不会改Demo。
- 当前使用硅基官方`https://api.siliconflow.cn/v1/chat/completions`，JSON object输出、`enable_thinking=false`、temperature=0、最多4096输出tokens、30秒超时；未开启工具/搜索，不发送金融快照或股票事实。局部Patch只发送已有条件的ID、指标、操作符、阈值、单位、启用状态，排除历史rationale以减少错误复述。

官方依据：[模型页](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash)、[对话补全](https://docs.bigmodel.cn/api-reference/模型-api/对话补全)。官方JSON模式不等于本地Schema保证；本产品始终进行Pydantic及语义校验，不宣称服务端已强制json_schema。

硅基官方依据（2026-10-29访问）：[模型列表](https://api-docs.siliconflow.cn/docs/api/models-get)、[对话补全](https://api-docs.siliconflow.cn/docs/api/chat-completions-post)、[JSON模式](https://api-docs.siliconflow.cn/docs/userguide/guides/json-mode)。实际GET模型列表HTTP200、1.014秒、66个chat模型，包含所选型号；这只证明列表查询成功，具体生成另做真实验证。request_id仅读取官方x-siliconcloud-trace-id响应头，进行格式与凭证排除检查；不保存Authorization或上游错误message。

## 工作流与新增接口

1. POST `/api/strategies/interpret`：source_text→结构化semantic（universe/conditions/clarifications/unsupported_requests/compliance_status）。无澄清且非合规阻断时才保存draft；有冲突的draft明确标冲突，既有执行入口阻断。
2. 用户审查并手动编辑条件，点击原“执行筛选”；解析接口绝不取数或自动执行。
3. POST `/{id}/patch/preview`：source_text+expected_revision，只产生add/update/remove/enable/disable操作及预览。程序按稳定ID应用到副本，不重建整份策略。未知/重复目标、非法字段、额外指标、单位错误被拒绝；常见明确数值与不相关目标额外核验。
4. 明确Patch预览后，用户点“确认应用修改”，POST `/{id}/patch/apply`：签名proposal_token+expected_revision。服务端验签、10分钟过期、基础版本、冲突，再通过现有SQLite乐观锁保存；revision增加，有旧执行则stale。未目标条件逐字段保持。
5. 提案使用本机进程临时签名密钥，重启后需重新解析；没有新增数据库表。签名不包含API Key，不能用前端改JSON绕过审查。旧版`/compile`在LLM模式明确unsupported_intent，禁止偷偷产生固定模板。

模型返回JSON→严格Pydantic→metric/operator/unit/value→明确阈值/来源与目标验证→冲突检测→草稿或提案。结构/语义非法最多一次纠正重试；鉴权、超时、上游错误不连续重试。错误分类：llm_timeout、llm_auth_error、invalid_structured_output、llm_upstream_error、unsupported_intent、invalid_patch_proposal。

初次模糊概念允许透明默认（origin=llm_interpreted）；明确条件为user_explicit；Demo为system_default。模糊Patch如“严格一点”在程序预检返回当前条件和阈值澄清，operations为空，不生成可应用提案。重复同指标目标不明确时禁止随意选择。当前一次提案不接受针对同一ID的多条操作，复杂修改可能需要分步/澄清。

## 固定Eval

`tests/eval/strategy_cases.json`共26条，包含明确值/操作符、多个条件、模糊初建、显式优先、Patch其他不变、remove/add/enable/disable、模糊Patch、冲突、不支持、合规和空/无意义输入。

运行：`.venv/Scripts/python.exe -m scripts.eval_llm`。串行，每例最多2次生成，鉴权失败立即停止；绝不请求金融数据。完整报告保存在本地忽略的`artifacts/llm-eval.json`，记录模型、每例输出、首次Schema状态、纠正重试及耗时。程序预检与model路径分开记录，不把程序拒绝称为模型理解成功。

指标均保存passed/total/rate；无有效样本时rate=null：Schema Valid Rate（首输出）、Explicit Metric/Operator/Value Accuracy、Patch Target Accuracy、Patch Preservation Rate（按gold目标检查未触及条件）、Clarification Accuracy、Unsupported Metric Handling、Conflict Handling、Compliance Boundary Accuracy。真实语义分数按任务类别统计，另有case_conditions_exact核对origin及整体条件；不能只用HTTP200做成功标准。

## 智谱阶段实际结果与Bad Case（历史，不改写）

- 最初未发现模型凭证：真实Eval为not_verified，26计划/0执行、所有比率null，保留`llm-eval-before-key.json`。
- 用户随后配置Windows用户级变量；旧进程仍缺失，已将用户变量仅读入新启动子进程并重启本地FastAPI，未打印或持久化Key。
- 共发起2次真实GLM首样本尝试，均鉴权失败；第二次安全诊断确认HTTP401、业务码1000。没有取得任何真实模型结构化输出，没有继续26条批量请求。最终报告status=failed；模型语义正确率仍未验证，10项指标均null。初次错误把鉴权失败算进明确值准确率0/1，已修正为无语义样本不计分母；原报告保留`llm-eval-first-auth-error.json`。
- **真实GLM的Initial/Patch/澄清尚未验证跑通**。不能把下面离线通过、程序预检或HTTP错误当作真实模型成功。
- 离线注入Bad Case：非法JSON、peg指标、!=操作符、错误单位、bool数值、PE20被改成30、额外股票字段、Patch误改营收、模糊Patch猜值、凭证错误、超时；程序Schema/allowlist/明确条件与目标检查或澄清预检拦截。坏case不是实际GLM输出，不虚构模型失败率改善。
- 程序修复：有限纠正一次；未知字段拒绝；签名和revision防止篡改/过期Patch；Eval按gold目标判断非目标修改，不根据模型自报目标刷高；离线Eval测试改写到pytest临时目录，避免覆盖真实报告。
- 用户只明确选择了GLM-4.7-Flash及配置凭证；Prompt/Schema/程序规则修改由AI完成，未虚构人工修改Prompt或人工验收。
- 实际浏览器：LLM输入可编辑、“解析策略”、缺凭证llm_auth_error且0条件/执行禁用；程序合规预检提示且不生成条件。尚未浏览器验收成功的真实GLM草稿/Patch。

## 风险与下一步边界

用户已将运行时Provider改为硅基流动，智谱鉴权不再阻塞本轮；未声称智谱Key已修好。正则语义保护仅覆盖常见明确表达，不能替代真实语义Eval；未标定词形/指代可能仍出错。澄清/unsupported提示暂为本次响应UI状态，不单独持久化；重载需重新解析。没有多轮聊天或自动建议阈值闭环。通用指标来源、负PE、财务真实contract mismatch继续是数据层风险，不以LLM编译失败处理。本轮不做新闻/RAG/回测/交易/多Agent。

## 硅基流动真实验证与修复（2026-10-29）

用户保存变量前，Process/User/Machine三个范围均未读到硅基Key（SL-018）。用户确认保存后，User=True、Process=False；安全地将用户变量加载到新服务进程。官方模型列表请求HTTP200、66个chat型号；选择列表实际包含的Qwen/Qwen3-8B。未改写原“读不到”或智谱鉴权失败记录。

固定26例保持不变，共完整执行4轮。报告保存在忽略的artifacts目录；baseline、round2、round3、final各有独立文件。表中的“语义响应”只表示Compiler返回结果，不等于gold断言全对。

| 真实轮次 | 首次Schema | Patch目标/保持 | 冲突 | 有语义响应 | 实际生成请求 |
| --- | --- | --- | --- | --- | --- |
| baseline | 11/19 | 0/7 | 2/2 | 16/26 | 31 |
| round2 | 17/19 | 5/7 | 1/2 | 24/26 | 22 |
| round3 | 19/19 | 6/7 | 2/2 | 26/26 | 19 |
| final | 19/19 | 7/7 | 2/2 | 26/26 | 19 |

实际Bad Case与修改，均由AI实施、没有虚构人工改Prompt：

- 模型将“不超过18.5”输出成`<18.5`：语义校验拒绝；Prompt增加中文操作符映射，纠正重试包含实际校验原因，保留`<=`断言。
- 正确的“估值合理，但PE必须低于20”被程序误拒：原明确条件正则不认识“必须”，错误套用模糊30默认；修复识别并增加显式优先的正反回归。
- PEG被映射成PE，或创造peg字段：unsupported验证/metric allowlist拒绝；Prompt明确“PEG不是PE”。
- update夹带完整condition、remove写enabled、enable写boolean：Schema拒绝，未放松字段规则；补充nullable字段说明和针对当前目标ID的合法JSON形状。
- Patch试图额外删除PE、禁用财务等非目标字段：目标检查拒绝；Prompt强调只允许明确提及的目标ID，BASE不再包含旧Demo的rationale，避免模型复述“未调用LLM”。
- 第三轮“再加一个营收同比>10%”被错误返回为update(c1)，当时Compiler接受了此提案；Eval的目标与保持率真实失败，未掩盖为通过，且没有写正式策略库。随后新增程序规则：纯新增指令必须add，否则拒绝；增加旧ID/值/条件均保留的测试，并在Prompt给出add形状。最终同样本正确add。
- round2及定向复测曾将冲突作为澄清而不返回两个条件；原gold要求程序识别矛盾范围，因此照实记失败，未放宽计分。最终保留两个条件，程序冲突检测成功。

最终26例全部gold断言通过，用时合计116.399秒。19例实际请求模型、HTTP200且首次Schema通过，无修复重试；7例走程序预检（E13–16、E24–26），**不能把预检效果描述成模型自身的合规/澄清理解能力**。

| 指标 | 最终分子/分母 | 比率 | 路径说明 |
| --- | --- | --- | --- |
| Schema Valid Rate | 19/19 | 100% | 实际模型首输出 |
| Explicit Metric Accuracy | 7/7 | 100% | 实际模型 |
| Explicit Operator Accuracy | 7/7 | 100% | 实际模型 |
| Explicit Value Accuracy | 7/7 | 100% | 实际模型 |
| Patch Target Accuracy | 7/7 | 100% | 实际模型+程序应用 |
| Patch Preservation Rate | 7/7 | 100% | 按gold目标检查非目标字段 |
| Clarification Accuracy | 4/4 | 100% | 该评测集由程序预检处理 |
| Unsupported Metric Handling | 3/3 | 100% | 实际模型+allowlist |
| Conflict Handling | 2/2 | 100% | 模型提条件、程序检测 |
| Compliance Boundary Accuracy | 3/3 | 100% | 该评测集由程序预检阻断 |

浏览器实际视口1280×720：真实模糊初建生成4个llm_interpreted条件且未自动执行；手动执行DEMO得到3/5/2；真实Patch预览PE30→20时旧v1/PE30仍在，确认后v2/stale；同快照重跑1/7/2，Diff入选3→1；“估值严格一点”程序澄清且版本不变；重启/重载恢复v2、PE20与相同快照；Unknown Drawer实际打开，raw与normalized均null、as-of未提供，未用取数时间代替。截图siliconflow-patch-whatif.png、siliconflow-unknown-evidence.png是实际页面，股票全部虚构，模型调用是真实的。未把之前UI阶段的多个分辨率验收算作本轮重测。

最终离线回归：Python154 passed、1 skipped、1 warning，11.05秒；Node13/13，122.7893ms；app.js/workspace-core.mjs语法exit0；PowerShell启动脚本语法0错误且实际启动成功。LIVE金融用例未执行；Starlette/AnyIO弃用警告仍存在。保护清单中Adapter/Domain/Store源码SHA256未变化，旧日志字节前缀保留；对74个交付/报告文本做凭证精确扫描，匹配0，扫描不打印凭证。

提交前风险：这是同一固定26例上的开发回归，Prompt根据其Bad Case迭代，**没有独立盲测集、重复多次稳定性或对抗注入评测**；100%不代表任意自然语言可靠。只覆盖4个指标、AND条件、有限中文表达。重复指标的模糊指代仍应澄清；同ID多字段复杂Patch可能需要分步。待用户确认具体型号/延迟与调用预算；本轮由AI选择Qwen3-8B，不声称用户指定了该型号。真实财务contract mismatch继续Unknown，未请求全量沪深300或改金融Adapter。
