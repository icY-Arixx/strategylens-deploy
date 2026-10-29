# 最终交付验证与冻结记录

日期：2026-10-29（Asia/Shanghai）。本轮结束后冻结功能。原Prompt、Qwen/Qwen3-8B、temperature、canonical registry、Patch及Clarification规则未修改；没有为评测继续调优。

## 结论与必须披露的限制

真实金融数据和审查后的执行闭环成功；**原始最终查询的LLM解释不正确**，因此不是“零修改全自动成功”。

原句“帮我找估值不要太高、最近走势比较稳定的股票。”真实返回PE>=30、波动率>=30，rationale也误述为不看估值/波动。Schema合法但语义方向反转，原校验与验证脚本未拦截，最初报告误标completed。原报告保留为本地`final-real-validation.uncorrected.json`，没有删除失败证据。

用户随后要求额度用尽立即收尾。此后**模型新增请求0次**，没有再次Eval或sanity、没有调Prompt。授权审查脚本将两个操作符显式修正为<30，再复用已保存真实Snapshot；记录`human_click_claimed=false`，不是虚构人工确认。生产验证脚本增加执行前方向断言，今后遇到同类输出停止执行，未把修正结果冒充模型原始输出。

此前已取得的真实局部Patch为update原PE条件value到20，condition_id正确，其他条件保持。审查后重放该已有语义操作，不新增模型调用；确认保存后revision增加、stale、再执行。最终状态`completed_after_review_correction`，`raw_initial_compile_correct=false`。

## 真实金融请求与范围

官方文档：[完整契约](https://fuyao.aicubes.cn/llms-full.txt)。本轮成分/日历预检2次均HTTP200/code0；正式流程13次请求：成分1、日历1、批量估值1、10只日K，全部HTTP200/code0。未请求财务、未扫描完整300只。

成分接口实际返回300只。按官方thscode升序选前10只，选择规则在取数前确定，未依据筛选结果挑样本。成分request_id=`3a6d7de44c1e4c6bafa604e3efa53692`，retrieved_at=`2026-10-29T07:26:49.001274Z`，上游timestamp=`2026-10-29T07:26:49.033Z`。该timestamp是上游返回时间字段，不额外声称为成分生效日。

Provider为“同花顺扶摇 / official REST / REAL Validation Sample”。范围明确为**真实验证样本：10只沪深300当前成分股（取数时成分，非完整沪深300筛选）**。

## 样本实际结果

下表为审查修正后的PE<30与vol<30；PE改20后状态完全相同。数值仅为本次取数截面，不代表实时行情或投资建议。

| 股票代码 | 名称 | PE(TTM)倍 | 60日年化波动率% | 两次结果 |
| --- | --- | ---: | ---: | --- |
| 000001.SZ | 平安银行 | 5.150513 | 17.230531 | Selected |
| 000002.SZ | 万科Ａ | -0.415667 | 51.943465 | Excluded |
| 000063.SZ | 中兴通讯 | 30.517533 | 26.330887 | Excluded |
| 000100.SZ | TCL科技 | 15.195249 | 25.313010 | Selected |
| 000157.SZ | 中联重科 | 12.202235 | 20.304000 | Selected |
| 000166.SZ | 申万宏源 | 12.299888 | 15.196499 | Selected |
| 000301.SZ | 东方盛虹 | 15.665912 | 40.894111 | Excluded |
| 000333.SZ | 美的集团 | 15.041299 | 21.320887 | Selected |
| 000338.SZ | 潍柴动力 | 13.637219 | 51.735928 | Excluded |
| 000408.SZ | 藏格矿业 | 14.912615 | 41.792600 | Excluded |

真实计数5/5/0；没有数据缺失，不能为了演示而伪造Unknown。DEMO与离线测试继续覆盖Unknown。负PE语义是既有边界，本轮未加PE>0；此样本万科因高波动被排除。

## 波动率与Evidence

10只均取得61个有效前复权收盘价，交易日范围2026-07-28至2026-10-28。公式为60个simple returns的sample standard deviation(ddof=1)×sqrt(252)×100；用独立statistics计算核对结果。未填充、未缩短窗口。验证样本Adapter检查上游symbol/interval/adjust回显，异常进入Unknown。

Snapshot保存全部61根raw close与normalized波动率，adjustment=forward、公式、实际使用交易日、起止日、close_count/return_count、retrieved_at、data_as_of、request_id及官方成分证据。财务字段未验证，raw/normalized=null、request_performed=false，无别名映射；若启用财务条件，仍Unknown。

Snapshot=`bd85cbde-b035-46a0-b248-491b6b04cb86`；策略=`fb958858-a70c-4422-a772-bf44fdbbe863`。审查后v3执行run=`36dac15e-8923-49e9-8836-3cd31c56df7f`；真实Patch重放确认后v4，run=`c9a351fd-1830-436d-afc6-15397944bf32`。非PE条件逐字段相同，stale已验证；What-if同快照，5→5、新增0、新排除0，金融新增请求0。

原首次模型+13次取数流程34.509秒；零网络的审查/重放/缓存执行0.150秒。这不代表完整沪深300性能。

## 自动化、评测与包装

最终Python：161 passed、1 skipped、1 warning，11.12秒；Node14/14，116.9057ms；app.js/workspace-core.mjs语法exit0。LIVE测试默认跳过，与已实际执行的真实13次流程分开。保留Starlette/AnyIO弃用提示。打包首次测试遇Windows沙箱rename拒绝，修正为字节复制并再次核对后完整回归通过，未弱化断言。

26条称Development Evaluation，沿用上轮真实结果；不是Blind Test。本轮在用户要求停止额度后不重跑，也未运行额外5–10条sanity。新句式失败是实际泛化反例，不能用开发集100%掩盖。

正式ZIP强制检查源码、LLM/Adapter/Snapshot/Evidence实现、文档及测试，逐文件源码/ZIP SHA256一致；排除环境、SQLite、缓存、截图和日志。外部manifest提供文件数与ZIP自身SHA256，避免将自引用摘要写入包内。Key只从环境读取，扫描已配置真实凭证及sk-token模式；Authorization/Bearer/X-api-key关键字是合法代码与文档，不能据此声称泄密，也不能保存带真实值的请求头。

## 最终演示与提交

本机已有缓存结果可在REAL服务打开`/?strategy_id=fb958858-a70c-4422-a772-bf44fdbbe863`；加载页面不调用模型/金融接口。源码ZIP不带SQLite，因此换机器须重新配置凭证/安装依赖再获取真实数据。无模型额度时保留本机缓存或使用固定模板并显式审查条件；不能冒充新的LLM成功。

提交源码ZIP与外部manifest，附本记录说明审查修正和模型失败。密钥、.venv、SQLite、原始本地截图和运行日志不提交。用户仍需亲自完成题目平台上传与演示/答辩。
