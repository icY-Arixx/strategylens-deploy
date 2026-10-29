# AI 开发与验证记录

本文件按实际工作追加，不代表人工验收。所有金融样本均为虚构 DEMO / MOCK。

## SL-000｜前期产品问题定义与市场假设
- 实际发生时间：正式编码前；未留存精确时间，不倒填日期。
- 本条补记时间：2026-10-28。编号置前用于归档产品起点，不表示本条在编码前已经写成。
- 本轮目标：记录有依据的前期产品判断，区分同期需求证据、本轮回溯陈述和本轮才完成的市场验证。
- 用户给 AI 的要求摘要：产品问题与市场假设应先于工程方案；保留真实开发时间线，不编造早期完整竞品研究。
- 有同期需求支持的前期判断：首次编码请求已明确“模糊自然语言→可检查/可修改条件→程序确定性筛选→逐股入选/排除/Unknown证据→修改后的结果变化”；明确不做普通聊天机器人，不由LLM决定股票是否符合条件；提出“LLM负责语义理解，程序负责金融事实和确定性判断”。这些要求在SL-001代码生成前已出现。
- 用户本轮回溯说明的前期过程：用户在编码前阅读三道AI产品经理题目并比较考核重点，选择本题是因为可形成完整闭环，而非易于写代码。当前材料没有三道原题或同期比较笔记；本条按用户本轮明确陈述记录，不补写不存在的题目对照表或早期网页访问。
- 早期市场假设：自然语言入口本身不足以定义产品价值；可检查的条件、明确的人机职责、双向证据与条件变化解释值得验证。初始材料直接支持产品原则；关于竞争空间的部分仍为假设，不能声称开发前已有完整竞品矩阵。
- AI 实际完成了什么：核对现有对话初始需求和SL-001历史记录，按证据级别补记产品起点；本轮开始系统化补全竞品研究，并用外部证据验证前期产品假设和差异化定位。
- 涉及文件：AI_DEV_LOG.md；正式外部研究另见本轮新增docs/COMPETITOR_RESEARCH.md，不回填为前期已完成。
- 发现的问题 / 风险：不能从“前期有产品判断”推导出“前期完成系统调研”；自然语言、透明条件或解释可能已是竞品成熟能力，差异需被外部证据修正。
- 人工决策：用户本轮明确要求此种真实性分层；本轮回溯陈述仅按原意记录。未确认的产品细节仍待人工确认。
- 验证方式：初始用户需求与现有开发日志对照；保留SL-001至SL-011原文与时间戳，另存本轮修改前历史副本用于核验。
- 实际验证结果：初始需求支持模糊意图结构化、用户可修改、人机职责分离、入选与排除证据及条件变化解释五项原则；“三题比较”的同期文档未发现，只记录为用户本轮回溯陈述；没有发现编码前完整竞品调研证据。
- 未解决事项：本轮系统研究验证与修正竞争假设；不能将后续研究日期提前。

## SL-001 · 项目初始化与核心架构设计
- 时间：2026-10-28（Asia/Shanghai）
- 本轮目标：检查目录，建立第一阶段职责边界和核心数据契约。
- 用户给 AI 的要求摘要：Python / FastAPI / Pydantic、原生前端、SQLite；仅 Mock；三态判断、条件编辑、stale、冲突阻断、Diff、自动测试与如实记录。
- AI 实际完成了什么：检查指定目录（空目录）及祖先 AGENTS.md（未发现）；确定分层结构和接口设计；创建本日志。
- 涉及文件：AI_DEV_LOG.md；后续实现文件尚未创建。
- AI 提出的关键设计或假设：固定模板编译器明确标示为 Mock，不模拟 LLM 理解；Condition 使用有限指标注册表及匹配单位；引擎仅接收 Adapter 提供的观测；结果保留版本快照；SQLite 用版本比较阻止旧请求覆盖新条件；禁用条件不参与计算，零有效条件阻断执行。
- 发现的问题 / 风险：固定模板不能理解任意输入；Mock 沪深300仅是演示股票池标签，样本和金融值不代表真实成分或市场事实；真实扶摇契约未知，预留实现必须拒绝调用。
- 人工决策：用户已明确本轮限定第一阶段、仅 Mock、不接 LLM / 扶摇；其他设计细节待人工确认。
- 验证方式：文件系统只读检查。
- 实际验证结果：指定目录存在且为空；未发现适用 AGENTS.md；尚未生成或运行应用和测试。
- 未解决事项：实现 Domain、Provider、存储、API、UI、文档及测试。

## SL-002 · Domain、Mock Adapter 与持久化主链路
- 时间：2026-10-28（Asia/Shanghai）
- 本轮目标：实现数据契约、确定性筛选、冲突检测、版本和执行快照持久化。
- 用户给 AI 的要求摘要：三态判断；缺失不能当作 0；启用条件同时满足；任何修改使执行结果 stale；重新执行提供 Diff；预留扶摇 Adapter 而不捏造接口。
- AI 实际完成了什么：建立 Pydantic 契约和指标单位表；实现固定四条件编译器、10 只虚构股票 Provider、纯比较引擎、解释模板、范围冲突检测、SQLite 快照与乐观并发保护、FastAPI 编译/读取/编辑/校验/执行端点；扶摇实现仅抛出 NotImplementedError。
- 涉及文件：app/domain/*、app/adapters/*、app/services/*、app/store/*、app/api/*、app/main.py、requirements.txt、pytest.ini、.env.example、.gitignore。
- AI 提出的关键设计或假设：百分数以百分点储存（30 = 30%）；固定模板条件 source=system_default，修改后为 user_explicit；禁用条件不生成检查；零启用条件不可执行；Diff 比较相邻执行的 selected 集合，新排除定义为离开该集合（包括转 Unknown）；策略修改增 revision，执行不增条件版本；比较整份旧快照以阻止同版本状态竞争。
- 发现的问题 / 风险：首次 uv 默认缓存被 Windows 拒绝访问；改为项目内 .uv-cache 后建立 .venv；首次依赖安装部分失败，copy 模式重试成功。依赖安装使用网络，业务应用没有调用 LLM / 扶摇。真实数据口径、负 PE 的业务处理尚不在本阶段。
- 人工决策：除 SL-001 所记用户约束外，待人工确认。
- 验证方式：.venv/Scripts/python.exe -m pytest -q；独立 Provider 注入；API、SQLite 重启恢复及并发快照测试。
- 实际验证结果：首轮 47 passed，1 warning（Starlette TestClient 使用 AnyIO 弃用别名），耗时 1.24s；默认 3 Selected / 5 Excluded / 2 Unknown；PE <20 后 1 Selected，移除 DEMO002 / DEMO008；旧快照阈值仍为 30。
- 未解决事项：浏览器实际交互与视觉验证；补齐产品说明、测试计划和 README；依赖弃用警告尚未处理。

## SL-003 · 原生三栏 Workspace 实现
- 时间：2026-10-28（Asia/Shanghai）
- 本轮目标：将 Domain/API 主链路接入可操作的单页工作台。
- 用户给 AI 的要求摘要：三栏；可修改阈值/启用/删除；三个结果 Tab；逐条件证据 Drawer；stale 提示与 What-if Diff；简洁金融研究工具界面。
- AI 实际完成了什么：创建原生 HTML/CSS/JS 工作台；编辑即本地标记旧结果 stale，防抖自动保存到后端；执行前等待保存；显示版本与历史结果标识；结果详情显示实际值、执行时阈值、状态、原因、来源、取数时间、报告期；localStorage 仅保存策略 ID，SQLite 保存业务状态；提供窄屏布局、键盘 Tab 切换及原生 dialog。
- 涉及文件：static/index.html、static/app.js、static/styles.css。
- AI 提出的关键设计或假设：数据未保存成功时保留 dirty 和历史提示；重新生成保留数据库中的旧策略但切换当前工作台；删除所有条件后只能重新生成；不新增复杂可视化。
- 发现的问题 / 风险：原生 JS 的自动保存、焦点和 Drawer 需要浏览器验证；目前尚不能以 API 测试推定 UI 已通过。
- 人工决策：待人工确认。
- 验证方式：FastAPI TestClient 检查静态页面与脚本路由；浏览器验证待执行。
- 实际验证结果：首页与静态资源均返回 200（包含在首轮 47 项测试中）；尚未进行浏览器交互验收。
- 未解决事项：浏览器验证、必要修复及文档。

## SL-004 · 文档与浏览器主链路验证
- 时间：2026-10-28（Asia/Shanghai；浏览器执行证据时间18:57–18:58，未完整采集其他步骤的分钟）
- 本轮目标：补齐 README、产品规格和测试计划，验证页面真实交互。
- 用户给 AI 的要求摘要：交付完整第一阶段，文档说明边界，不虚构 UI 或测试通过。
- AI 实际完成了什么：编写 README、PRODUCT_SPEC、TEST_PLAN；定位沙箱进程监听但其他进程/浏览器连接超时的问题；尝试同端口发现占用，停止原服务后改用沙箱外仅监听127.0.0.1:8766的服务，健康检查200并成功打开桌面浏览器；没有修改防火墙或扩展业务范围。
- 涉及文件：README.md、docs/PRODUCT_SPEC.md、docs/TEST_PLAN.md、AI_DEV_LOG.md；本地运行生成 data/strategylens.sqlite3（忽略文件）。
- AI 提出的关键设计或假设：API 测试不等同于 UI 验收；Diff 的新排除语义需明确包含 Unknown；真实数据接入后仍需区分数据变化和条件变化。
- 发现的问题 / 风险：初次预览失败被如实记录；页面目前不支持添加条件，同指标冲突通过 API 测试覆盖；窄屏及完整键盘遍历未验证。
- 人工决策：待人工确认；本轮操作和结果由 AI 完成，不代表用户人工验收。
- 验证方式：桌面浏览器实际点击与填写，检查 AX 状态和页面截图；独立HTTP健康检查；node --check static/app.js。
- 实际验证结果：默认3/5/2；Unknown Drawer PE为缺失/UNKNOWN且有来源/取数时间/报告期；改PE20立即stale，历史Drawer阈值仍为30；重新执行1/7/2、Diff3→1/移除002与008；禁用PE得到5/4/1；删除波动率后刷新恢复v4、2/3项启用与历史结果；清空阈值不能执行；JS语法检查exit0。
- 未解决事项：最终契约测试、截图留存、启动过程收尾；未模拟网络保存失败，未测试窄屏和完整键盘遍历。

## SL-005 · 核心数据契约加固
- 时间：2026-10-28（Asia/Shanghai）
- 本轮目标：在收尾审查中强化类型边界，补足不一致观测与Diff边界用例。
- 用户给 AI 的要求摘要：核心Domain稳定；数据缺失严格区分unknown；测试断言不能弱化。
- AI 实际完成了什么：静态审查发现默认数值类型可能隐式接收布尔值或数字字符串，且ConditionCheck尚未禁止pass/fail搭配null；改为严格有限数字和严格enabled；增加检查状态与实际值一致性及单位验证；加入相应拒绝用例、重复股票及转Unknown的Diff用例。
- 涉及文件：app/domain/models.py、app/services/explanation_service.py、tests/test_domain.py、tests/test_workflow.py、docs/TEST_PLAN.md。
- AI 提出的关键设计或假设：外部Adapter必须提供明确数字/null，不能把字符串/布尔值隐式转换成金融数值；unknown与实际缺失必须一致。
- 发现的问题 / 风险：此轮是契约审查加固，没有声称发现真实数据错误；新增Diff边界用例加入后仍需再运行。
- 人工决策：待人工确认。
- 验证方式：实际运行pytest；严格类型、状态一致性、重复股票等新增用例。
- 实际验证结果：加固后已运行54 passed、1 warning、1.17s；随后新增的转Unknown Diff用例尚待最终运行，不能沿用54项结果宣称已通过。
- 未解决事项：运行含最后新增用例的最终测试；更新最终验证记录。

## SL-006 · 第一阶段收尾与交付核验
- 时间：2026-10-28 19:04（Asia/Shanghai；工具时钟11:04 UTC）
- 本轮目标：核对最终文件、运行记录、实际浏览器证据，停止第一阶段工作。
- 用户给 AI 的要求摘要：报告实际新增文件、可运行流程、实际测试、已知问题、开发记录和下一阶段建议；不要继续接入其他功能。
- AI 实际完成了什么：运行包含最后Diff边界用例的完整测试；重启最终契约代码并从浏览器重新完成生成→执行→PE20→重新执行；保存并检查完整工作台截图；核对SQLite保存内容及文件清单；关闭所有本轮验证服务，确认8765/8766均无监听；更新README和测试计划实际结果。
- 涉及文件：本轮累计新增33个源码/配置/文档文件，清单见下；额外本地运行文件为data/strategylens.sqlite3、artifacts/workspace-pe20.jpg、.venv/、.uv-cache/和Python/pytest缓存（均忽略）。没有删除或覆盖用户原文件，初始目录为空。
- AI 提出的关键设计或假设：截图和测试日志作为可复核开发证据，不视作人工验收；验收后下一阶段先确认真实数据契约，再接语义编译器。
- 发现的问题 / 风险：1条Starlette/AnyIO弃用警告仍存在；窄屏、完整键盘遍历、网络保存失败场景未验证；模板不理解任意文本；真实数据字段/口径仍未知；真实数据下Diff的因果归属需要另行设计。
- 人工决策：除用户最初明确的范围与技术约束外，待人工确认；未声称用户已检查、批准或验收此实现。
- 验证方式：.venv/Scripts/python.exe -m pytest -q；已运行node --check static/app.js；桌面浏览器实际交互和完整页截图；SQLite只读计数；监听端口检查。
- 实际验证结果：最终55 passed、1 warning、1.35s；JS语法exit0；最终浏览器PE20结果1/7/2，Diff3→1、新增0、新排除002/008；截图116749字节；演示库有2个策略、5次执行，最后工作台为PE20的已执行策略；两个验证端口均已停止监听。浏览器和API均未调用真实LLM或扶摇。
- 未解决事项：上述未验证场景与弃用警告；第一阶段已实现，本轮停止，不继续扩展。用户可按README重新启动本地服务。

### 本轮实际新增文件清单（33）
```text
.env.example
.gitignore
AI_DEV_LOG.md
README.md
pytest.ini
requirements.txt
app/__init__.py
app/main.py
app/api/__init__.py
app/api/strategy.py
app/api/screening.py
app/domain/__init__.py
app/domain/models.py
app/domain/strategy_engine.py
app/domain/conflicts.py
app/services/__init__.py
app/services/strategy_compiler.py
app/services/explanation_service.py
app/services/session_service.py
app/adapters/__init__.py
app/adapters/financial_base.py
app/adapters/mock_financial.py
app/adapters/fuyao_financial.py
app/store/__init__.py
app/store/sqlite_store.py
static/index.html
static/app.js
static/styles.css
tests/conftest.py
tests/test_domain.py
tests/test_workflow.py
docs/PRODUCT_SPEC.md
docs/TEST_PLAN.md
```

## SL-007 · 第二阶段现状核验与官方契约调查
- 时间：2026-10-28 19:32（Asia/Shanghai）
- 本轮目标：保留分层架构与开发环境，核验正式命名、凭证和官方扶摇能力，为 Snapshot / Evidence 和真实 Adapter 做准备。
- 用户给 AI 的要求摘要：统一 StrategyLens；保留虚拟环境/缓存/SQLite；新增快照和执行追溯；区分 origin 与 data_source；只接官方扶摇，不接运行时 LLM；线上结果与 fixture 测试分开记录。
- AI 实际完成了什么：发现项目目录已由外部改为 StrategyLens（未执行目录改名）；确认旧目录不存在，README仍含旧拼写；只检查指定凭证环境变量是否存在（未输出值）；查阅官方财务指标及快速开始文档；运行原有基线测试。
- 涉及文件：AI_DEV_LOG.md；只读检查 app/、static/、docs/、README.md、.gitignore、requirements.txt；未删除本地开发文件。
- AI 提出的关键设计或假设：保留旧数据库历史，通过兼容读取/显式迁移接续契约；新增不可变数据快照和执行记录，复用同一快照才允许条件变化归因；真实上游错误不得回退Mock。具体实现待后续日志记录。
- 发现的问题 / 风险：进程/User/Machine均未设置HITHINK_FINANCE_API_KEY；本机未发现命名匹配的扶摇CLI/包；目录中有旧命名RAR归档，保留不删除；真实线上请求尚未验证。
- 人工决策：人工确认保留当前分层架构、Pass/Fail/Unknown、stale/revision、Mock与真实Adapter隔离；不引入LangGraph/多Agent；先真实数据后运行时LLM；新增Snapshot；正式名StrategyLens；保留本地虚拟环境和开发缓存，仅排除提交。其他设计待人工确认。
- 验证方式：文件和配置只读检查；官方文档 https://fuyao.aicubes.cn/docs/api-reference/financial-indicators/ 与 https://fuyao.aicubes.cn/docs/quickstart/；原环境pytest -q。
- 实际验证结果：基线55 passed、1 warning、1.23s；官方确认financials/indicators按单标的+报告期请求，财务百分数值不应乘/除100，null表示缺失，HTTP200仍可能业务失败；尚无任何真实金融数据接口调用成功记录。
- 未解决事项：核验指数成分、PE、日K及复权、批量与速率约束；实现Snapshot/Evidence/Adapter/页面/兼容存储/新增测试；凭证缺失时线上验证须保持未验证。

## SL-008 · Snapshot / Evidence 与官方 REST Adapter 实现
- 时间：2026-10-28（Asia/Shanghai；本阶段工具操作在19:32后）
- 本轮目标：在原架构增加快照追溯和真实官方Adapter，保持确定性判断、错误显式化。
- 用户给 AI 的要求摘要：每次执行绑定strategy_revision+snapshot_id；区分条件变化与数据变化；origin/data_source分义；真实原值、时间、报告期、request_id与计算方法可追溯；禁止真实失败回退Mock。
- AI 实际完成了什么：新增DataSnapshot、Evidence、ScreeningRun和DataIssue；Condition序列化origin、观测/检查序列化data_source，旧source仅作兼容读取别名；实现SQLite不可变快照、内容哈希、运行中进度/失败记录、旧库备份迁移；默认真实模式，Mock仅显式配置/测试注入；实现官方REST统一信封、Key头、业务码、限速与安全错误；实现成分、交易日历、PE批量、单股财务与前复权历史日K；程序计算60收益率样本波动率。
- 涉及文件：app/domain/models.py、app/domain/strategy_engine.py、app/domain/volatility.py、app/adapters/financial_base.py、app/adapters/mock_financial.py、app/adapters/fuyao_client.py、app/adapters/fuyao_financial.py、app/services/session_service.py、app/services/strategy_compiler.py、app/store/sqlite_store.py、app/api/screening.py、app/main.py、.env.example、.gitignore。
- AI 提出的关键设计或假设：每次新取数使用新UUID，不以相同内容伪造相同ID；相同ID只通过读取已存快照实现；默认复用本策略上次快照，可显式刷新；财务期必须配置FUYAO_REPORT，不猜最新披露期；日K请求forward，剔除上海当日，按官方日历要求完整61收盘价形成60简单收益率，样本标准差(ddof=1)*sqrt(252)*100；财务未提供数据截至时间则保留null；快照data_as_of仅为最晚已知上游时间，不能宣称同步切片。
- 发现的问题 / 风险：财务与日K为单股接口，300成分常规需要605次调用（成分1+日历1+PE3+财务300+K300），仅为契约推导，不是线上实测；默认串行、请求开始间隔1秒，遇限流停止而非重试风暴；正式权限未验证。曾有一次apply_patch因同一补丁删除/新增同文件而被工具拒绝，未修改目标；改为Update后成功。
- 人工决策：沿用SL-007已明确人工确认项；报告期配置方式、前复权、ddof=1、请求节流和默认快照复用策略待人工确认。
- 验证方式：原有测试保留断言意图，字段断言更新为origin/data_source，扶摇占位断言替换为无凭证显式失败；扩充offline官方schema fixture；源代码静态检查；JS语法检查。
- 实际验证结果：接入后原55项通过；加入契约/错误/快照测试后95项通过；后续新增用例结果在SL-009记录。没有真实接口调用成功记录。
- 未解决事项：页面真实交互、实际旧库迁移核验、文档与源码打包检查；线上数据真实性、权限和延迟因缺Key未验证。

## SL-009 · 离线契约测试与线上验证边界
- 时间：2026-10-28 19:57（Asia/Shanghai；工具报告11:57 UTC）
- 本轮目标：覆盖第二阶段要求的错误、证据、快照、波动率、隔离及凭证安全，区分线上与fixture结果。
- 用户给 AI 的要求摘要：保持原测试，新覆盖13类真实Adapter风险；未执行线上请求不能写PASS；不静默缩减沪深300范围。
- AI 实际完成了什么：增加离线官方形状合成fixture、Snapshot迁移与归因测试、交付ZIP白名单测试、显式opt-in线上测试和独立smoke入口；用合成300标的验证全量605次串行路径与3个100标的PE批次；新增请求路径白名单、报告期变化拒绝复用、无凭证复用已有真实快照等检查；实际执行smoke命令并保存not_verified报告。
- 涉及文件：tests/test_domain.py、tests/test_workflow.py、tests/conftest.py、tests/test_fuyao.py、tests/test_snapshots.py、tests/test_delivery.py、tests/test_live_fuyao.py、pytest.ini、scripts/smoke_fuyao.py、scripts/package_release.py、scripts/__init__.py；artifacts/phase2-live-smoke.json（本地忽略）。
- AI 提出的关键设计或假设：合成fixture不是市场数据；测试中的固定凭证为明确的非真实sentinel，仅用于泄漏断言；LIVE测试要求显式RUN_FUYAO_LIVE=1且实际Key存在，常规pytest不得暗中联网。
- 发现的问题 / 风险：真实Key在进程、User和Machine均未配置；官方MCP变量API_KEY也未配置；线上能力、权限、全沪深300耗时均不能确认。单进程串行筛选是当前部署边界。
- 人工决策：除已确认项外待人工确认。
- 验证方式：原环境python -m pytest -q；python -m scripts.smoke_fuyao --full --output artifacts/phase2-live-smoke.json；node --check static/app.js；ZIP内容断言。
- 实际验证结果：102 passed、1 skipped、1 warning，7.04s；skipped为线上测试（无Key/未启用）。smoke报告status=not_verified、successful_capabilities=[]、full_universe_measured=false，未构造真实Provider发出请求；报告elapsed_seconds仅为本地前置检查耗时，绝非沪深300执行耗时。JS语法检查exit0。
- 未解决事项：页面回归与文档；真实Key配置后需执行单股probe和全量smoke，本轮不得将其记为成功。

## SL-010 · Evidence 原值修复、实际迁移与页面回归
- 时间：2026-10-28（Asia/Shanghai；页面证据20:07–20:11，最终测试20:14）
- 本轮目标：修正审查发现的证据混淆，完成原数据库和页面真实交互验证。
- 用户给 AI 的要求摘要：raw_value保留真实原值；缺失/错误/快照可回看；不删除本地开发数据；页面不能掩盖失败。
- AI 实际完成了什么：审查发现日历对齐的程序空行可能混入raw_value，改为只保存上游实际行，预期日期另存calculation_inputs；增加request_performed，熔断跳过不伪造独立请求ID；拒绝数值溢出/下溢；实际启动REAL服务并迁移原库；浏览器发现失败后空结果区仍写“等待执行”，修为明确“本次未生成筛选结果”；验证DEMO同/不同快照与原始null展开；更新正式命名和说明。
- 涉及文件：app/domain/models.py、app/adapters/fuyao_financial.py、app/adapters/fuyao_client.py、app/adapters/mock_financial.py、static/index.html、static/app.js、static/styles.css、tests/test_fuyao.py、README.md、docs/PRODUCT_SPEC.md、docs/FUYAO_INTEGRATION.md、docs/TEST_PLAN.md；data/backups/和artifacts/phase2-*.jpg为忽略的本地验证证据。
- AI 提出的关键设计或假设：raw与程序对齐输入必须分开；错误证据时间表示观察失败的时间，request_performed区分实际请求和熔断跳过；新模型序列化origin/data_source，旧字段仅兼容读取。
- 发现的问题 / 风险：第一次按button角色定位details控件未匹配，读取实际DOM后按文本定位成功；一次截图捕获报错，但前一张已落盘，随后通过本地view_image核实最终两张截图，未把报错当成功。前复权/报告期/负PE口径和真实权限仍待确认。
- 人工决策：沿用SL-007明确人工确认项；新增细节待人工确认。页面与代码审查由AI执行，不虚构用户验收。
- 验证方式：旧库与自动备份的策略ID/条件值/执行数量只读对照；浏览器实际点击/输入/刷新、AX状态和截图；原环境pytest；node --check；正式文本搜索旧拼写。
- 实际验证结果：原库自动备份1份，原2个策略ID/条件值保留、5历史执行仍为5，未补造历史Snapshot；REAL缺Key运行failed/authentication_error，未生成结果；DEMO PE20复用snapshot=08a6086b-3003-45cd-8c9a-b151e281b6a5，Diff3→1可归因；显式刷新变6021390d-f5b8-4383-80a4-9b517f55b82e，Diff1→1仍明确数据快照变化；Drawer raw_value与normalized_value均为null而非0；最终104 passed、1 skipped、1 warning，18.10s；JS语法exit0。正式源码/页面/当前文档未发现旧拼写；第一阶段日志与用户旧RAR保留原样。
- 未解决事项：最终源码打包内容核验与验证服务关闭；真实金融请求/全量性能仍未验证；完整键盘/窄屏交互未验收。

## SL-011 · 第二阶段交付清单与安全打包核验
- 时间：2026-10-28 20:19（Asia/Shanghai；工具时钟12:19 UTC）
- 本轮目标：完成命名/工程清洁交付核验，保留本地开发环境，明确线上未验证状态后停止扩展。
- 用户给 AI 的要求摘要：不删除虚拟环境、缓存和SQLite，只排除Git/ZIP；汇报官方能力、真实调用、口径、范围、测试、日志及接LLM前风险。
- AI 实际完成了什么：核对正式产品名、源码和文档无旧拼写；列出本轮33个新增/修改文件；用源码白名单生成ZIP并检查43个正式文件、成员集合和CRC；核对.env.example真实Key位置为空，ZIP不含环境/缓存/数据库/旧归档；原本地开发目录与用户RAR仍保留；关闭REAL与DEMO本地验证服务并确认8766/8767均无监听；保留线上not_verified报告和三张截图。
- 涉及文件：下方本轮文件清单；交付包artifacts/StrategyLens-phase2-source.zip与截图/smoke报告为本地忽略输出，不提交Git。requirements.txt未改动，没有重建或重装.venv。
- AI 提出的关键设计或假设：源码交付包包含必要测试和文档，但不夹带本地运行状态或凭证；正式源码根由__file__定位，目录已正确命名，无需用户再改名；旧历史日志和旧归档不作为当前产品拼写改写。
- 发现的问题 / 风险：没有有效Key，因此真实接口成功列表为空，权限不是“已拒绝”而是“未验证”；全沪深300耗时、实际成分数、数据新鲜度未实测；原测试依赖弃用警告仍存在；长请求的进程中断恢复、逐股最新财务期、负PE业务口径待后续确认。
- 人工决策：保留用户在SL-007明确确认的决策；其他细节待人工确认，本轮没有编造新增人工验收。
- 验证方式：104项自动化通过、1项LIVE跳过、JS语法exit0的既有最终结果；ZIP成员与源码白名单严格相等、CRC校验、配置示例Key空值断言；文件存在性及端口检查。
- 实际验证结果：源码43文件，第二阶段新增/修改33文件；源码包校验通过；.venv/.uv-cache/.pytest_cache/原SQLite与用户旧RAR仍存在；两个验证端口均无监听。原始线上smoke=not_verified，不存在真实成功调用记录。数据事实与条件判定仍分层、没有运行时LLM或其他扩展。
- 未解决事项：必须由有效环境凭证完成真实单股probe与全量smoke，确认权限/数据口径/耗时后才能宣称线上接入验证完成；本轮停止继续扩展。

### 第二阶段实际新增 / 修改文件（33）
```text
.env.example
.gitignore
AI_DEV_LOG.md
README.md
pytest.ini
app/adapters/financial_base.py
app/adapters/fuyao_client.py                 新增
app/adapters/fuyao_financial.py
app/adapters/mock_financial.py
app/api/screening.py
app/domain/models.py
app/domain/strategy_engine.py
app/domain/volatility.py                    新增
app/main.py
app/services/session_service.py
app/services/strategy_compiler.py
app/store/sqlite_store.py
docs/FUYAO_INTEGRATION.md                   新增
docs/PRODUCT_SPEC.md
docs/TEST_PLAN.md
scripts/__init__.py                        新增
scripts/package_release.py                 新增
scripts/smoke_fuyao.py                     新增
static/app.js
static/index.html
static/styles.css
tests/conftest.py
tests/test_delivery.py                     新增
tests/test_domain.py
tests/test_fuyao.py                        新增
tests/test_live_fuyao.py                    新增
tests/test_snapshots.py                    新增
tests/test_workflow.py
```

## SL-012 · 系统化补全竞品研究与历史证据分层
- 时间：2026-10-28 21:25（Asia/Shanghai；工具时钟13:24 UTC附近）
- 本轮目标：用外部证据验证前期产品假设和差异化定位，补记前期判断但不倒填正式研究。
- 用户给 AI 的要求摘要：保留数据架构；系统研究问财、TradingView、妙想、Koyfin；重构投研工作台；SL-000区分真实早期原则和本轮研究，历史不删改。
- AI 实际完成了什么：核对初始需求与现有材料，增加SL-000并分开同期需求证据和用户本轮回溯陈述；备份SL-001至SL-011历史用于核验；完成公开资料矩阵，给官方帮助、历史教程和社区材料分级；实际检查凭证并运行最小probe前置检查及原测试。
- 涉及文件：AI_DEV_LOG.md、docs/COMPETITOR_RESEARCH.md；.cache/phase3历史副本和artifacts/phase3-live-probe.json为忽略的本地证据。
- AI 提出的关键设计或假设：自然语言/可见条件/解释本身是基线；聚焦审查、逐股三态证据、条件保留Patch与快照归因；自然语言Patch仍是下一阶段目标，不假称已实现。
- 发现的问题 / 风险：TradingView当前帮助已支持移动端/Crypto，早期发布说明不同，按当前帮助处理；问财百科是社区贡献版本，不能当官方能力承诺；财富号教程作者认证未确认，只作辅助；公开资料未确认不等于不支持；没有编码前完整竞品矩阵证据。官方PDF读取失败未作为细节依据。
- 人工决策：人工确认保留Snapshot/Evidence/ScreeningRun、三态与stale/revision、Adapter隔离；重构三栏大卡为表格主导工作台；正式补竞品研究；不以自然语言选股本身创新；聚焦可检查策略/来源/证据/Patch/快照；保留Drawer，产品原理移出主界面；线上扶摇仍P0，本轮不草率接运行时LLM。其他细节待人工确认。
- 验证方式：官方公开帮助/能力页与辅助教程交叉读取，来源列于COMPETITOR_RESEARCH；环境变量只检查存在性；原环境pytest与最小smoke入口。
- 实际验证结果：基线104 passed、1 skipped、1 warning，6.75s；进程/User/Machine未配置HITHINK_FINANCE_API_KEY，最小probe=not_verified，未发真实金融请求，未跑全量；TradingView明确已有映射解释且新AI请求覆盖配置，修正“透明即差异”的宽泛假设；Koyfin成熟表格/可编辑条件证实应提高信息密度；更细审计链条仍待对照实测验证。
- 未解决事项：按研究结论改造UI、增加条件入口与结果指标；更新产品叙事、设计决策和未来LLM Eval计划；浏览器验证1366/1440/1920；真实线上仍未验证。

## SL-013 · 投研工作台信息架构与证据交互
- 时间：2026-10-28 21:59（Asia/Shanghai；记录此前实际完成的实现与浏览器检查）
- 本轮目标：将三栏架构Demo改为表格主导的研究工作台，不破坏既有数据判断。
- 用户给 AI 的要求摘要：移除01/02/03等高大卡与大段答题说明；命令输入、紧凑条件行、添加条件、操作条、四指标结果表、分层Evidence Drawer与轻量What-if。
- AI 实际完成了什么：重写原生HTML/CSS/JS；新增纯展示投影模块；四指标持续展示，缺失与未记录分开；添加既有指标条件且保留原条件；历史条件差异按稳定ID比较；增加只读历史执行GET，支持重载后恢复具体修改摘要；保留stale、冲突、运行错误、快照复用/刷新与DEMO身份；修复载入失败不应永久显示载入中及极小非零数显示成0的风险。
- 涉及文件：static/index.html、static/styles.css、static/app.js、static/workspace-core.mjs、app/main.py、app/store/sqlite_store.py、tests/test_product_workspace.py、tests/workspace_core.test.mjs、tests/test_workflow.py。
- AI 提出的关键设计或假设：结果四指标固定列，即使条件删除仍读取已存快照；证据先给实际值/阈值/原因，技术字段折叠；轻量来源按钮；1366/1440两列条件、1920四列。以上细节待人工确认；不宣称已通过真实用户测试。
- 发现的问题 / 风险：固定模板仍不能解析任意自然语言，使用“示例模板”入口解释，不标AI理解；旧浏览器session来自不同预览库时会恢复失败并明确提示；真实模式无Key，不能验证金融数据；快照加载失败时只能保留执行记录可用字段，不补数据。
- 人工决策：用户已确认重构三栏、结果表优先、保留Drawer及数据契约、减少架构说明与Mock大横幅但不能隐藏身份；其他排版/字段顺序/交互细节待人工确认。
- 验证方式：Python及Node离线测试，IAB浏览器实际操作，DOM宽度检查与本地截图；使用独立DEMO/REAL预览SQLite，不改变原开发数据库。
- 实际验证结果：新增用例后Python107 passed、1 skipped、1 warning，8.71s；Node7/7，148.89ms；两JS语法检查exit0。浏览器1366×900、1440×900、1920×1080无整页横向溢出；默认3/5/2，PE20后1/7/2同快照Diff3→1；刷新新ID且显示数据变化警告；Unknown PE raw/normalized=null；添加PE>30保留原PE<20并显示冲突/禁用执行按钮（试点按钮因disabled被浏览器拒绝，随后核验为预期阻断）；禁用/删除可恢复；PE<=20后2/6/2；删除PE后5/4/1且四数值列仍在；重载恢复删除摘要；行Enter开抽屉、Escape关抽屉成功。
- 未解决事项：完整移动端、全套键盘与屏幕阅读器验收未做；真实用户任务研究未做；本条后续数字格式修正需最终回归；真实扶摇请求仍not_verified。

## SL-014 · 产品叙事、设计取舍与未来语义评测方案
- 时间：2026-10-28 21:59（Asia/Shanghai）
- 本轮目标：按产品经理逻辑呈现问题、市场、定位、方案与验证，保持开发历史真实。
- 用户给 AI 的要求摘要：正式竞品矩阵、Competitive Positioning、设计决策与Initial Compile/Patch Eval；不把第三阶段研究倒填到编码前，不接运行时LLM。
- AI 实际完成了什么：README/PRODUCT_SPEC按用户问题→竞品→机会→定位→方案→职责→实现/验证重组；明确透明条件/解释已有竞品重叠；记录来源、逐条件证据、缺失三态、Patch及快照的差异候选与证据边界；新增11项决策及代价/验证方法；TEST_PLAN新增产品用例和未来语义评测类别、分母/全对判定/失败样本要求；源码包输出改新文件名避免覆盖第二阶段交付包。
- 涉及文件：README.md、docs/PRODUCT_SPEC.md、docs/COMPETITOR_RESEARCH.md、docs/DESIGN_DECISIONS.md、docs/TEST_PLAN.md、scripts/package_release.py、AI_DEV_LOG.md。
- AI 提出的关键设计或假设：Initial Compile与局部Patch分契约；Patch基于ID和base_revision，明确条件优先、其余字段完全保留；该接口和Eval均为下一阶段设计，不是假称已实现。竞品相对优势需账号内同任务对照及真实用户验证。
- 发现的问题 / 风险：公开材料无法确认不等于不支持；妙想具体流程部分来自未确认作者认证的社区资料；没有三题比较同期文档，仅按用户本轮回溯记入SL-000；不采用失败读取的官方PDF作为细节证据。
- 人工决策：用户已确认不以自然语言本身创新，聚焦可检查策略/来源/逐条件证据/局部Patch/快照，真实验证P0，本轮不接LLM；具体未来Patch Schema、Eval样本数/门槛与UI细节待人工确认。
- 验证方式：文档与当前功能/官方资料交叉检查；历史SL-001至SL-011原文SHA256核验将在最终检查记录；测试方案明确标“设计，未执行”。
- 实际验证结果：文档已写入；没有执行真实LLM Eval，没有声称竞品账号实测或市场独占；最终历史哈希/交付包检查尚待运行。
- 未解决事项：最终回归、历史完整性与源码包核验；真实Key与单股probe、调用预算、报告期及负PE处理仍待验证/确认。


## SL-015 · 最终产品回归、历史完整性与源码交付核验
- 时间：2026-10-28 22:04（Asia/Shanghai；工具时钟14:04 UTC）
- 本轮目标：核验现有可信执行链路及新工作台，保留真实历史并生成不含环境/数据/凭证的源码包。
- 用户给 AI 的要求摘要：自动测试与浏览器实际验收分开；真实probe未验证就保持not_verified；不删本地环境；完成本轮后停止扩展。
- AI 实际完成了什么：运行最终Python与Node回归、JS语法检查；补验空阈值阻断和方向键Tab；修正极小非零事实显示及条件摘要/Drawer保留完整阈值精度；核对SL-001至SL-011原文哈希；生成48文件白名单源码包并逐成员核验字节和CRC；保留第二阶段旧包及所有本地开发环境/数据库；恢复视口覆盖，停止本轮8766/8767预览服务并核验已无监听。
- 涉及文件：本轮新增5个正式文件：docs/COMPETITOR_RESEARCH.md、docs/DESIGN_DECISIONS.md、static/workspace-core.mjs、tests/test_product_workspace.py、tests/workspace_core.test.mjs。本轮修改11个正式文件：AI_DEV_LOG.md、README.md、docs/PRODUCT_SPEC.md、docs/TEST_PLAN.md、app/main.py、app/store/sqlite_store.py、static/index.html、static/styles.css、static/app.js、tests/test_workflow.py、scripts/package_release.py。本地忽略的artifacts包含实际截图、not_verified报告和源码ZIP；.cache/phase3包含本轮前历史副本。
- AI 提出的关键设计或假设：仅新增只读历史执行查询和展示投影；金融Domain/Provider/判断及快照契约方向保留。未来Initial Compile/Patch与Eval是设计方案，未接LLM；没有扩大指标或加入框架。
- 发现的问题 / 风险：真实Key缺失，最小金融线上请求、权限、单股速度与全量605次请求估算都没有实测；统一显式财务报告期、负PE、单进程长执行恢复仍待确认；竞品只有公开案头证据，未做账号内同任务实验；移动端、完整无障碍和真实用户研究尚未验收。原Starlette/AnyIO弃用警告存在。
- 人工决策：仅记录用户本轮明确保留架构/三态/stale/revision/证据/模式隔离、正式补研究、表格工作台/Drawer/收敛技术说明、扶摇P0及本轮不接LLM等既有确认；本轮最终实现与视觉尚待人工审查，其他细节待人工确认。
- 验证方式：pytest全套；Node内置test及两模块语法；IAB实际交互和1366/1440/1920布局/截图；源文件与ZIP逐字节比较、CRC、空Key示例检查；历史SHA256与本轮前备份对照；本机监听端口只读检查。
- 实际验证结果：最终Python107 passed、1 skipped、1 warning，20.96s；LIVE跳过。最终Node7/7，127.82ms；两JS语法exit0。空PE值执行被明确阻断、结果历史且revision不变，补20恢复1/7/2；方向键切Tab成功；最终浏览器新资源回归3/5/2→PE20→1/7/2，同快照Diff3→1且未捕获console error。REAL缺Key显示authentication_error和未产生有效结果，无fallback；线上probe=not_verified、成功能力为空、未发金融请求、全量未测。SL-001至SL-011规范化原文SHA256完全相同，时间戳未改。首版源码包48个成员均与源文件一致，CRC正确、示例Key为空；最终记录写入后重打同一包并复核。环境/缓存/data目录存在，预览端口已无监听。
- 未解决事项：真实扶摇P0需有效Key后单股probe，依据实际权限/耗时制定全量方案；产品差异需任务对照验证；运行时LLM接入前确认Patch契约、歧义策略与语义Eval标注/门槛。本轮停止，不继续扩展。


## SL-016 · 现行问财视觉参考与金融筛选UI重构
- 时间：2026-10-28 23:48（Asia/Shanghai，UTC+8；本轮实际完成后追加，不倒填到编码前）。
- 本轮目标：依据当前正式问财页面重做前端表现、范围身份和固定模板交互，保留可信执行契约。
- 用户给 AI 的要求摘要：先访问官方页面、写UI审查与规范；统一布局、语义分组、金融表格、数据身份；固定模板不冒充自然语言理解；仅UI/必要前端测试，不改后端、不接LLM。
- AI 实际完成了什么：官方首页经Edge实际渲染/screener并查看截图、读取可见DOM；结果URL跳到新版结果页但有登录弹窗，未登录；index读取超时，旧帮助403。基于可确认的浅色/冷蓝强调与输入关联工具，实施统一1440px居中容器、经营质量/估值与风险分组、14px金融表格、蓝/灰/赭黄判定状态、持续样本范围、只读“载入示例策略”、选中行和分层Evidence；修复窄屏Drawer默认max-width及背景滚动；添加表内键盘横滚及6项前端回归，原7项断言保留。
- 涉及文件：新增docs/UI_DESIGN_SPEC.md；修改static/index.html、static/styles.css、static/app.js、static/workspace-core.mjs、tests/workspace_core.test.mjs、AI_DEV_LOG.md。artifacts/ui-refresh保存实际参考/验收截图和viewport-checks.json；.cache/ui-refresh保留原日志和后端哈希，均为忽略的本地证据。
- AI 提出的关键设计或假设：当前问财左导航、白底与冷色强调是实际观察；所测单个AI选股元素为#165dff/14px，不代表全站官方Token。StrategyLens自主选择#3655c9品牌、1440px容器、轻量横导航、两语义组及三态/快照表达；不复制Logo、专有图标、多应用栏或增加假自选/收藏。样本数从执行结果读取，未知截至不以取数时间替代。
- 发现的问题 / 风险：问财部分页面读取超时/登录限制，官方表格行高、列宽和编辑行为未确认；本产品色值和排版为AI方案。一次多Tab视口设置作用目标不符，随后按实际innerWidth/innerHeight重新完成四尺寸记录、覆盖误标截图并逐张查看。390验收不是手机真机或完整无障碍。收尾记录工具缺tzdata，改用明确UTC+8记录时间，无依赖或环境重建。
- 人工决策：用户明确仅改UI/交互/必要前端测试，保留已有功能及后端契约，不接LLM/其他模块；具体色值、排版、示例表达等AI方案待人工确认，未虚构最终人工验收。
- 验证方式：官方浏览器实际截图/可见DOM；完整pytest、Node test、两模块语法检查；IAB四尺寸截图逐张查看，执行/编辑/冲突/快照/Drawer/重载/模式实际操作；后端21文件SHA256与本轮前对照，原日志字节前缀核验。
- 实际验证结果：首轮Python107 passed、1 skipped、1 warning，7.65s；最终107 passed、1 skipped、1 warning，20.43s；LIVE跳过，既有Starlette/AnyIO警告保留。Node最终13/13，153.148ms；两JS语法exit0。1366×900、1440×900、1920×1080、390×844实际宽高/截图完成，无整页横向溢出；1920输入/结果同宽1440px。示例3/5/2，PE20后立即stale，旧证据仍阈值30；重执行1/7/2、同快照Diff3→1；Unknown raw/normalized=null；添加冲突保留5项并禁执行，禁用解除/删除恢复4项；<=20为2/6/2；刷新新ID且计数相同时仍警告数据变化；重载恢复v6与摘要；窄屏键盘横滚scrollLeft=98，全宽Drawer/Escape关闭成功。REAL缺配置显示authentication_error、无有效结果、as-of未知，无fallback；专用预览进程置空凭证/报告期，不改变用户配置，未发金融请求，不是线上smoke。21个后端源文件未改；原SL-000至SL-015字节保留。最终8766/8767已无监听，临时视口覆盖已重置。
- 未解决事项：问财登录后表格/编辑细节未核实；真实用户评审、真机触控、完整无障碍/跨浏览器待验证；真实金融线上不能据UI测试称通过；运行时LLM仍未接入。本轮停止扩展。


## SL-017 · 用户凭证读取与单股真实线上验证
- 时间：2026-10-29（Asia/Shanghai）；真实请求开始12:56:52，3.132s结束；本条事后追加。
- 本轮目标：确认Key存在，只验证一只A股的行情→PE→财务，记录真实字段和失败，随后停止。
- 用户给AI的要求摘要：仅报告凭证是否存在；不输出或保存Key；不回退Mock、不全量沪深300；明确线上与离线，单股完成后等待确认。
- AI实际完成：确认进程与Windows用户变量均存在；核对现有Adapter及当前官方财务/估值文档；新建固定300033.SZ、2026-2报告期的串行单股probe；调用既有Client和Provider，不修改生产Adapter；记录脱敏原响应/状态/ID/时间/耗时；审查财务真实ID差异；补充测试记录。
- 涉及文件：scripts/probe_fuyao_single.py、docs/LIVE_SINGLE_STOCK_VALIDATION.md、docs/FUYAO_INTEGRATION.md、docs/TEST_PLAN.md、README.md、AI_DEV_LOG.md；artifacts/single-stock-live-20261029.json及.initial.json为忽略的本地证据。
- 关键设计/假设：行情按已有historical日K能力验证，非实时tick；短窗口前复权，不算波动率；未配置FUYAO_REPORT，因此probe显式选择2026中报，不声称最新。只3次真实请求，不取指数成分/日历，不写生产策略或快照库。
- 问题/风险：HTTP/业务成功并不保证现有条件字段可用。预期operating_income_yoy_growth_ratio和net_profit_yoy_growth_ratio缺席；实际为calculate_operating_income_yoy_growth_ratio、calculate_parent_holder_net_profit_yoy_growth_ratio等。未确认语义，特别归母净利润不可擅自替代净利润。Adapter规范值null来自ID缺席，非上游该ID显式null。最初probe只检查调用/解析而报completed，响应审查后修正检查和最终报告partial_failure；初始报告保留，未追加线上请求。
- 人工决策：用户明确授权单股真实测试、禁止泄露Key/Mock假成功/全量，完成后停止；具体测试代码及2026-2报告期由AI选择，待人工确认；未虚构人工认可字段映射。
- 验证方式：3次真实官方HTTPS，安全response hook仅采集脱敏响应体不采集请求头；当前官方财务/估值文档读取；离线契约测试与脚本语法编译；本地Engine运行已采集财务证据；检查交付文本无真实凭证。
- 实际结果：日K HTTP200/code0，0.247s，7根，request_id=d29eff7c70b3437c8a98b1d46f8e7eed，最新交易日2026-10-28、收盘199.0；PE HTTP200/code0，0.881s，37.137036倍，as-of=2026-10-29 12:56:54 UTC+8，request_id=3bc15a652298466cafc9dd2f68ba5f18；财务HTTP200/code0，0.986s，request_id=487f062c21794e7aa5445564fa1aee64，但契约ID不一致，两财务检查Unknown、as-of未知。单步耗时含节流，不是纯网络时延。离线test_fuyao.py：42 passed、1 warning，2.27s；py_compile通过。没有全量、LLM或Mock fallback。
- 未解决：真实财务字段/净利润口径需先与官方确认，再经用户确认决定Adapter修正；真实成分/日历/完整波动率及全量性能未验证。本次单股结束，等待用户确认下一步。

## SL-018 · 硅基流动配置核验与官方模型查询契约
- 时间：2026-10-29 14:31:19（Asia/Shanghai）。
- 本轮目标：用户改用硅基流动且不知道模型ID，核验环境变量并准备官方模型列表查询。
- 用户给AI的要求摘要：已填写SILICONFLOW_API_KEY，希望无需自行判断模型型号；禁止输出或记录真实Key。
- AI实际完成：读取现有GLMProvider，确认当前生产地址仍固定智谱；访问硅基流动官方模型列表与JSON模式文档；只检查已知变量的存在性，未打印值。准备的模型列表probe因缺少可读取凭证未发出线上请求。
- 涉及文件：AI_DEV_LOG.md；artifacts/siliconflow-models-probe.json（本地忽略的检查记录）。无源码、金融Adapter、Domain或数据库契约修改。
- 关键设计/假设：先GET官方/v1/models?sub_type=chat确认真实可用ID，再选择结构化输出模型；不能把硅基Key发送到智谱地址，不能把官方示例ID冒充本账号已授权型号。
- 发现的问题/风险：本次检查Process、Windows User、Machine三个范围的SILICONFLOW_API_KEY均不存在；与用户已填写的描述存在环境可见性差异，尚不能定位为保存未完成、名称差异或运行环境差异。
- 人工决策：用户明确切换硅基流动并称已填写Key；具体模型与Provider实现细节待人工确认。未虚构凭证有效或模型可用。
- 验证方式：PowerShell仅输出存在性布尔值；核对官方https://api-docs.siliconflow.cn/docs/api/models-get及https://api-docs.siliconflow.cn/docs/userguide/guides/json-mode。
- 实际验证结果：三个范围均False；真实硅基模型列表请求0次、生成请求0次，线上验证not_verified；未fallback Demo，未请求扶摇。
- 未解决事项：确认变量保存及进程可见性后，再查询官方模型列表、配置硅基Provider并开展真实编译/Eval。当前代码仍为智谱Provider，不能仅换Key宣称迁移完成。
## SL-019 · 运行时Compiler实现补记与硅基流动Provider切换
- 时间：2026-10-29 15:04:10（Asia/Shanghai）。部分Compiler源码已在前序交互生成，本条为事后补记，时间是记录时间，不倒填更早开发时间。
- 本轮目标：落实自然语言草稿与安全局部Patch，并在用户从智谱改为硅基流动后完成配置。
- 用户给AI的要求摘要：运行时LLM只负责语义，金融事实和裁决仍由程序负责；严格Schema/allowlist/来源；用户确认后执行/应用Patch；失败禁止Demo fallback；原架构和金融契约保留；用户不知道型号，希望AI协助配置。
- AI实际完成：DemoStrategyCompiler保留；LLMStrategyCompiler及独立严格语义契约、编译/预览/确认API、HMAC提案绑定策略版本与过期时间、前端必要输入/预览/澄清状态；新增硅基官方JSONCompletion Provider，保留智谱显式入口与独立Key；安全Windows启动脚本；26例固定Eval及离线测试。
- 涉及文件：app/services/compiler_models.py、llm_compiler.py、llm_provider.py、strategy_compiler.py、session_service.py；app/api/compiler.py、app/main.py；static/index.html、app.js、styles.css、workspace-core.mjs；tests/test_llm_compiler.py、test_siliconflow_provider.py、workspace_core.test.mjs、eval/strategy_cases.json；scripts/eval_llm.py、start_llm.ps1；.env.example、README.md、docs/PRODUCT_SPEC.md、TEST_PLAN.md、LLM_COMPILER.md、AI_DEV_LOG.md。
- 关键设计/假设：模型只从4个canonical指标选择，结构化JSON仍须本地Pydantic及语义检查；Patch对副本按原condition_id应用，确认才写入现有库，不增加表；未知/冲突/过期/篡改/版本冲突阻断；模糊修改先澄清，运行时最多一次格式纠正。Provider明确配置，不跨供应商尝试凭证，不自动回退。
- 发现的问题/风险：早期智谱401/code1000未修复，保留其失败报告；本轮User级硅基变量保存后可读，旧Process仍缺失，不能仅重刷网页；普通沙箱启动的本地服务无法从本机浏览器访问，改在已授权本机启动，健康检查成功。
- 人工决策：用户明确允许运行时Compiler、保留分层/金融契约、不做其他模块；明确将模型供应商改为硅基流动并保存Key。Qwen/Qwen3-8B型号、具体Prompt/Schema/HMAC及启动脚本由AI提出，待人工确认，未虚构人工改Prompt。
- 验证方式：读取当前源码与官方模型/对话/JSON文档；安全存在性检查；官方模型列表真实GET；独立离线Provider测试；本地浏览器及完整回归。
- 实际验证结果：User=True、Process=False、Machine=False；官方模型列表HTTP200、1.014s、66个chat ID，其中含Qwen/Qwen3-8B；首条真实PE20编译成功。新服务config确认llm、llm_ready=true、金融DEMO/MOCK。没有打印或保存Key，金融Adapter/Domain/SQLite结构未改。
- 未解决事项：所选型号、延迟及预算待用户验收；财务真实contract mismatch仍保留Unknown；本轮不继续财务核验或全量扫描。

## SL-020 · 真实LLM Bad Case、Prompt与程序规则修复
- 时间：2026-10-29 15:04:10（Asia/Shanghai）。按实际4轮评测结果事后汇总，原始报告分别保留。
- 本轮目标：用固定gold检查真实模型行为，修复局部Patch错误与显式阈值误处理，不能以HTTP200冒充语义正确。
- 用户给AI的要求摘要：至少20–30条Eval，统计Schema/明确值/目标与保持率/澄清/unsupported/冲突/合规；记录模型原始错误、程序拦截及修复效果，不能放松断言。
- AI实际完成：26例完整运行4轮，补3例定向复测；保留baseline/round2/round3/final；修复“必须”正则误拒，补中文<=映射、PEG非PE、操作字段说明与当前ID的合法JSON形状、目标约束、有限修复的具体校验反馈；BASE排除历史Demo rationale；新增明确add必须追加的程序检查与测试。
- 涉及文件：app/services/llm_compiler.py、compiler_models.py、llm_provider.py；tests/test_llm_compiler.py、test_siliconflow_provider.py；scripts/eval_llm.py；docs/LLM_COMPILER.md、TEST_PLAN.md；artifacts/llm-eval-siliconflow-baseline.json、round2.json、round3.json、final.json及llm-targeted-round3.json（均为忽略的本地证据）。
- 关键设计/假设：Schema合法与语义正确分别计分；Patch Preservation按gold目标检查，而非相信模型自报目标；网络/鉴权失败不计作有语义样本；程序预检与模型路径分开；不通过修改gold提高得分。
- 发现的问题/风险：真实模型曾将不超过写成<、PEG映射成PE、update夹带完整condition、remove/enable填写enabled或boolean、修改非目标条件；Schema/allowlist/目标检查拦截。程序也曾把正确“PE必须低于20”误套模糊30规则，已修正。第三轮add被模型写成update(c1)，当时Compiler接受了此提案；Eval保持率真实失败，只在评测副本应用、未写正式库，随后增加程序guard修复。没有声称所有坏case最初都已拦截。
- 人工决策：用户已授权上述评测维度和禁止覆盖/猜阈值；具体Prompt与程序修复由AI完成，待人工确认，没有人工修改Prompt的证据。
- 验证方式：每轮相同26例、串行且运行时单例最多2次生成；实际输出/首次Schema/错误/安全request_id/耗时保存；回放相应离线正反测试；未调用扶摇或混入Mock模型输出来评分。
- 实际验证结果：baseline Schema11/19、Patch0/7、语义响应16/26；round2 Schema17/19、Patch5/7、Conflict1/2、语义响应24/26；round3 Schema19/19、Patch6/7，含明确add错误；final Schema19/19、Patch7/7、Conflict2/2，全部gold断言通过。4轮生成响应数量31+22+19+19=91，不含另行probe/定向/浏览器请求。保留安全澄清冲突但gold判失败的中间结果，未篡改计分。
- 未解决事项：这是依据固定集迭代后的开发回归，没有独立盲测、重复稳定性和全面对抗提示注入测试；不能从最终100%推断任意输入可靠。

## SL-021 · 最终回归、浏览器闭环与交付核验
- 时间：2026-10-29 15:04:10（Asia/Shanghai）。
- 本轮目标：实际验证运行时语义闭环，确认原金融执行架构/证据未受损，整理真实记录后停止扩展。
- 用户给AI的要求摘要：草稿先审查，Patch先预览确认；stale/revision和Snapshot保留；DEMO金融与真实模型不混淆；现有Python/Node测试继续通过；凭证不落源码/日志/浏览器。
- AI实际完成：浏览器真实生成4条件草稿；PE30→20真实Patch预览/确认，重执行和SQLite重载；模糊Patch程序澄清；打开Unknown及完整null证据；保存并实际查看截图。修正文案将编译中的“筛选中”改为“处理中”，区分待澄清/待确认/初建提示；不再次大改UI。
- 涉及文件：static/app.js；scripts/start_llm.ps1；README.md、docs/PRODUCT_SPEC.md、TEST_PLAN.md、LLM_COMPILER.md、AI_DEV_LOG.md；本地artifacts/siliconflow-patch-whatif.png、siliconflow-unknown-evidence.png及独立预览data/llm-ui-check.sqlite3。
- 关键设计/假设：模型成功不意味着金融真实性；当前预览明确mock，只有股票数值为虚构，模型确为硅基线上调用。模糊Patch由确定性安全预检处理，不将其称为LLM判断成功；金融缺失继续Unknown。
- 发现的问题/风险：澄清/unsupported响应没有独立持久化，刷新后需重新解析；固定26例不覆盖任意中文表达；1280宽AI解释轻量标签可能换行，本轮未重做布局；原Starlette/AnyIO弃用警告仍在。
- 人工决策：用户授权的Compiler/UI必要调整和保留架构已执行；型号与细节仍待人工确认，未虚构人工浏览器验收。
- 验证方式：完整pytest、Node及两JS语法；PowerShell脚本解析并实际启动；1280x720真实浏览器操作和截图；保护源码SHA256、历史日志前缀、凭证精确扫描。
- 实际验证结果：Python154 passed、1 skipped、1 warning，11.05s；Node13/13，122.7893ms；两JS语法exit0；PowerShell解析0错误且启动后健康/config成功。最终Eval26例，19真实模型请求/19首次Schema、7程序预检，116.399s；Explicit三项各7/7、Patch两项各7/7、Unsupported3/3、Conflict2/2，Clarification4/4及Compliance3/3均为该集程序预检效果。浏览器草稿未自动执行；DEMO手动执行3/5/2，Patch预览时v1/PE30不变，确认v2/stale，重跑1/7/2、同快照入选3→1；模糊修改不变版本；服务重启/页面重载恢复v2、PE20与快照；Unknown raw/normalized=null、as-of未提供。Adapter/Domain/Store保护哈希无变化，旧日志字节前缀保留；74个文本凭证扫描0匹配。
- 未解决事项：本轮只检查1280x720，不冒充重跑此前多分辨率；LIVE金融skip，不重新验证财务/全量。提交前应补独立holdout与多次稳定性评测、重复指标指代/复杂Patch及异常体验验收；本轮到此停止，不扩展RAG/回测/交易等。
## SL-022 · 最终真实验证样本与冻结审查
- 时间：2026-10-29 15:40:41（Asia/Shanghai）。
- 本轮目标：冻结LLM，将真实模型、真实10只成分、PE、60日波动率、Patch与Snapshot接成最终交付流程。
- 用户给AI的要求摘要：不再调主Prompt/模型/参数/指标/核心Patch/澄清；只10只官方成分验证样本，真实证据；财务别名不阻塞；完成后冻结。
- AI实际完成：新增FuyaoValidationSampleProvider，官方成分按代码升序取10只；沿用现有真实PE与波动率计算，显式跳过未验证财务；增加价格标的/周期/复权回显核验及实际交易日范围；真实流程脚本通过生产API串联编译、执行、Patch预览/确认与同快照重跑。增加范围文案、保存策略链接、相关测试；没有重做UI或修改Domain/SQLite。
- 涉及文件：app/adapters/fuyao_validation.py、app/main.py、static/app.js、static/workspace-core.mjs、scripts/final_real_validation.py、scripts/start_llm.ps1、.env.example、tests/test_validation_sample.py、tests/workspace_core.test.mjs。
- 关键设计/假设：固定采样只依赖官方代码排序，不依据结果挑选；新Provider身份及snapshot scope隔离完整范围；财务request_performed=false、null/Unknown，不映射alias；真实数据缺失不补0；默认真实路径有界10只。
- 发现的问题/风险：最终新句式被真实模型错误解释为PE>=30与vol>=30，rationale也反向误述；Schema合法但语义错误，原验证脚本漏检并初报completed。原报告保留uncorrected副本，不能宣称原始编译正确；新增执行前方向断言。原Prompt及模型参数未改。
- 人工决策：用户明确批准本轮范围与冻结规则，随后明确“没有额度，立刻收尾”；没有人工点击或确认具体草稿的证据，不虚构人工审查。
- 验证方式：官方文档及2次成分/日历预检；真实流程13次金融请求；独立statistics核验61收盘价/60收益率/ddof1/252；保存请求状态、ID、raw/normalized与快照。
- 实际验证结果：预检2次HTTP200；正式成分300只、选固定10只，PE10/10、前复权61根与波动率10/10；正式13次均HTTP200/code0，取数区间2026-07-28至10-28。第一次流程34.509s，原始错误草稿得到0/10/0，不能作为用户意图成功。真实Patch确实只更新原PE值、其他条件不变，revision/stale/快照复用成功。
- 未解决事项：原始新句式方向错误；财务contract mismatch；无完整300只性能验证；没有真实Unknown样本，不为演示伪造。

## SL-023 · 额度停止后的审查修正、零网络复用与最终回归
- 时间：2026-10-29 15:40:41（Asia/Shanghai）。
- 本轮目标：按用户要求立即停止新增模型请求，用已保存证据收尾，不继续优化或调参。
- 用户给AI的要求摘要：没有额度，需要立刻收尾；最终只交付事实、限制与正确源码包。
- AI实际完成：保留原始错误报告；通过明确标记的授权脚本将两个方向审查修正为<30，使用既有真实Snapshot执行；重放已取得的真实PE Patch到20，确认保存后stale再同快照执行。脚本将所有潜在新增金融请求设置为禁止；没有新增LLM调用。整理最终README与FINAL_VALIDATION、增强正式打包契约和测试。
- 涉及文件：scripts/final_review_existing.py、scripts/final_real_validation.py、scripts/package_release.py、tests/test_delivery.py、README.md、docs/FINAL_VALIDATION.md、docs/TEST_PLAN.md、docs/LLM_COMPILER.md、AI_DEV_LOG.md。
- 关键设计/假设：审查修正非模型原始输出，human_click_claimed=false；既有真实Patch重放不等于新增模型成功；26条只称Development Evaluation，沿用此前记录，不再运行Eval/sanity；缺陷原样披露。
- 发现的问题/风险：首次打包回归在Windows沙箱中rename报WinError5，保留1failed/160passed记录；改为复制ZIP字节并核验，再完整回归通过。没有弱化缺文件、凭证拒绝或逐文件SHA断言。原始LLM语义泛化问题未修复。
- 人工决策：用户明确要求停止额度消耗并收尾；脚本审查动作由AI根据已授权演示条件完成，具体阈值沿用原始30，未虚构用户本人点击或认可模型输出。
- 验证方式：修正前后/原始报告分别保存；Snapshot与非PE条件逐字段比较；完整pytest、Node、两JS语法；新包强制必需文件、排除项与凭证扫描。
- 实际验证结果：审查后v3与Patch后v4均5Selected/5Excluded/0Unknown；same snapshot=bd85cbde-b035-46a0-b248-491b6b04cb86，5→5、新增0、新排除0。额度停止后模型新增0、金融新增0；缓存审查验证0.150s。最终Python161 passed/1 skipped/1 warning，11.12s；Node14/14，116.9057ms；两JS语法exit0。原LLM Compiler/Provider/Schema、Domain与Store保持冻结，正式包核验单独记下一条。
- 未解决事项：原始LLM方向反转、未验证财务、无独立Blind Test和本轮sanity；源码ZIP不带本机SQLite，换电脑需要自行配置凭证并取数。用户仍需本人上传题目平台与答辩。
## SL-024 · 正式包完整性、凭证扫描与最终冻结
- 时间：2026-10-29 15:44:23（Asia/Shanghai）。
- 本轮目标：交付包含最新运行时实现的正式源码ZIP并冻结，不再新增功能。
- 用户给AI的要求摘要：立即收尾，最新源码包、逐文件SHA256与凭证安全，真实失败必须披露。
- AI实际完成：核查旧ZIP只有48文件且缺LLM Compiler/Provider/文档/评测等；新包强制必需文件，排除环境/数据库/缓存/截图/日志，逐文件对比并生成外部manifest；凭证扫描；本机服务切到REAL验证样本并读取已保存v4结果。没有新增模型或金融请求。
- 涉及文件：scripts/package_release.py、tests/test_delivery.py、README.md、docs/FINAL_VALIDATION.md、AI_DEV_LOG.md；artifacts/StrategyLens-workspace-source.zip、同名manifest.json、final-security-scan.json（交付包/外部校验记录）。
- 关键设计/假设：Authorization/Bearer/X-api-key是必要源码关键字，检查真实值而非删除正常调用代码；包自身SHA放外部manifest，避免包内自引用。最后追加本条后重新打包核对，不让ZIP停留在旧日志版本。
- 发现的问题/风险：最终历史前缀检查发现SL-000补记说明一行与本轮开工快照不同：日期仍为2026-10-28，括号内阶段/补记依据说明被缩短。本轮工具未编辑该行，来源未确认；保留当前文本及开工副本，不擅自回滚可能的外部编辑，也不声称字节历史完全一致。其他历史Log没有删除。此前“不再调Prompt”的冻结哈希全部一致。
- 人工决策：用户要求最后一轮后冻结并本人提交；未虚构人工对包或错误草稿的确认。
- 验证方式：必需文件清单、源码/ZIP SHA256、已配置硅基/扶摇/智谱凭证精确扫描及sk-token模式；正常header关键字分类；本机只读health/config/session。
- 实际验证结果：首个新包66文件、66/66一致；工作区97个文本/SQLite文件与ZIP内全部文件未命中真实凭证；模型/Provider/Schema、Domain/Store冻结哈希无变化。REAL服务config=real_validation_sample_10，已保存v4结果5/5/0可读。最终Python161通过/1跳过/1警告、Node14通过；没有因额度停止后再跑模型Eval或sanity。
- 未解决事项：原始LLM最终句式方向反转仍需显式审查；财务契约未确认；10只非完整300；本机缓存不进源码包，换机需配置凭证和取数。用户本人仍需上传ZIP/manifest并据实演示与答辩。到此冻结。
## SL-025 · GitHub正式上传清单与精选截图
- 时间：2026-10-29 16:01:10（Asia/Shanghai）。
- 本轮目标：上传至用户指定icY-Arixx/StrategyLens，排除中期产物；功能保持冻结。
- 用户要求摘要：上传项目到GitHub，不上传多余中期测试东西；用户随后明确允许截图，并提供仓库链接。
- AI实际完成：确认目标为空的公开仓库且连接账号有写权限；沿用正式源码白名单，保留必要自动化测试、可复现验证脚本和产品/验证文档；仅将两张最终DEMO截图复制至docs/screenshots并嵌入README；打包器仅额外放行这两个图片路径。
- 涉及文件：README.md、scripts/package_release.py、docs/screenshots/workspace-demo.png、docs/screenshots/evidence-unknown-demo.png、AI_DEV_LOG.md。
- 设计/假设：截图明确DEMO身份，不冒充REAL；不删除本地中期产物，只排除上传；保留坏案例和局限，不因发布修改金融/LLM实现。
- 问题/风险：本地原来没有Git仓库/远程；当前仓库为public，上传前须做凭证扫描；正常Authorization等字段名不等于密钥泄露。
- 人工决策：用户明确授权GitHub上传、允许截图并指定仓库；未授权发布临时报告或密钥。
- 验证方式：正式白名单、图片视觉检查、凭证扫描、源码包SHA256；远端文件树与本地Git blob逐文件核对。
- 实际结果：上传前清单准备完成，两图已查看且均标识DEMO；上传结果以本轮后续GitHub提交与远端核验为准，不提前编造上传成功。
- 未解决事项：此条写入时尚待提交远端与核验；不新增模型或金融调用，不扩展产品。
## SL-026 · GitHub上传成功与范围核验
- 时间：2026-10-29 16:07:54（Asia/Shanghai）。
- 本轮目标/用户要求：完成指定GitHub仓库上传，仅正式文件及允许的精选截图。
- AI实际完成：创建本地main仓库，白名单暂存68文件并提交807fa16；连接工具网络故障、Git直连超时后，使用用户已启用的本机系统代理，仅对命令生效，成功推送icY-Arixx/StrategyLens/main。
- 涉及文件：AI_DEV_LOG.md；Git元数据；正式68文件及更新源码包。无产品功能更改。
- 设计/假设：不全量git add，不改全局代理，不强制覆盖远端；必要测试与验证脚本保留，中期产物不发布。
- 问题/风险：直连GitHub不可用，推送依赖现有代理；截图明确为DEMO。
- 人工决策：用户指定仓库并明确允许截图；上传已授权，无额外发布范围。
- 验证方式：git push成功回执、ls-remote与本地HEAD比较、提交树白名单与截图清单、此前凭证扫描。
- 实际结果：主分支已推送；提交树68文件，禁止产物0，两张最终DEMO截图。后续本条日志单独提交同步；不发模型或金融请求。
- 未解决事项：无上传阻断；保留原项目Known Limitations，功能继续冻结。