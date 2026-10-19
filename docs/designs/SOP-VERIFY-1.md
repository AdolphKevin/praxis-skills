---
design: "D-sop-verify-1"
task: "SOP-VERIFY-1"
revision: 2
assessment: {"complexity":"medium","risks":["public-contract"],"effort":"约一个半工作日代理时长","drivers":["新增命令行工具与五种文件格式，成员与看板按格式协作","技能文本决定代理在业务仓库中的对话与派遣","场景与结果字段与 team-workflow 同义，两边各自实现"],"uncertainties":[],"required_skills":["Python 标准库","Git","技能写作"]}
roles: {"design_owner":"Claude","implementation_owner":"Codex","acceptance_owner":"AdolphKevin"}
---

# SOP-VERIFY-1：sop-verify 本机模式

> 本文件是 tw 任务 SOP-VERIFY-1 的方案原文。总体设计与决定见 team-workflow 仓库的 `docs/proposals/2026-10-19-standalone-sop-verification.md`（v7），本需求对应其第 8 节第一行。验收场景见 [docs/sop/sop-verify.yaml](../sop/sop-verify.yaml)。
>
> 状态：修订 2。修订 1 由 AdolphKevin 于 2026-10-19 批准；修订 2 新增错误代码 `state-invalid`，AdolphKevin 同日批准。

## 全局范围
<!-- tw-section id=scope-global type=global-scope -->
新增 `sop-verify` 技能。使用者在任何 Git 仓库中，不接入 tw，用一句话让代理从业务 SOP 写出正反向场景，由新开的会话经声明的入口执行，登记结果并给出报告。

本需求只做本机模式：轮次、证据与用例快照保存在仓库外的本机状态目录，业务仓库只增加 `docs/sop/` 下的场景文件与入口声明。推送看板、从看板取用例与配对属于 SOP-VERIFY-2。

非目标：看板客户端；verify-backend-sop-db 与 build-scenario-validation-loop 的输出改造；与 team-workflow 共享代码。

- 需求级验收：A1、A2、A3、A4、A5、A6

| 仓库 | 入口 | 操作 | 产生方 | 使用方 | 提交负责方 | 验收 |
| --- | --- | --- | --- | --- | --- | --- |
| self | sop-verify/scripts/sop.py | check、pending、submit、import-cases、coverage、report | 方案作者、执行者、测试同事 | 业务仓库成员与代理 | praxis-skills | A1、A2、A3、A4、A5 |
| self | sop-verify/SKILL.md 与 references | 代理按技能对话、写场景、派遣、登记、报告 | 维护者 | 使用 sop-verify 的代理与成员 | praxis-skills | A6 |

## 命令面
<!-- tw-section id=I1 type=interface depends=scope-global -->
`python3 <技能目录>/scripts/sop.py <子命令>`，Python 3.10 以上，只用标准库与 `git` 命令。在 Git 仓库内任意目录运行；`--root` 指定仓库，缺省取当前目录所在仓库的根；不在 Git 仓库中时退出码 1，错误代码 `not-a-git-repository`。`--format text|json` 缺省 text。

| 子命令 | 参数 | 结果 |
| --- | --- | --- |
| check | `<场景文件> [--entries <文件>]` | 核对场景文件与入口；输出文件 sha256 与每条场景的内容指纹；不写任何文件 |
| pending | `<场景文件>` | 列出待执行场景及原因；另列由回归守护与受阻的场景；不写任何文件 |
| submit | `<场景文件> --results <结果文件> [--implementer <姓名>]` | 核对结果并登记一轮，证据复制到状态目录；输出本轮统计与新的待执行清单 |
| import-cases | `<场景文件> <用例文件>` | 导入测试同事的用例并保存快照；输出新增、更新、未变与并集条数 |
| coverage | `<场景文件> --pairs <配对文件>` | 按历次导入的并集核对配对，保存配对快照与结论 |
| report | `<场景文件> [--format markdown\|json]` | 按数据 D2 输出报告到标准输出；缺省 markdown |

退出码：0 成功；1 输入或状态问题；2 参数用法错误。json 输出是一个对象，含 `ok`；失败时含 `error_code` 与 `problems`，每项 `{line, problem}`，与行无关时 `line` 为 null。错误代码：`scenario-file-invalid`、`entries-invalid`、`scenario-results-invalid`、`scenario-results-incomplete`、`source-stale`、`batch-conflict`、`cases-invalid`、`scenario-coverage-incomplete`、`not-a-git-repository`、`state-invalid`。text 输出逐条写出同样的问题与行号。

入口来源依次为 `--entries`、场景文件同目录的 `entries.yaml`、仓库 `.tw/config.json` 的 `acceptance_entries`；都没有时报 `entries-invalid`。`entries.yaml` 与 `.tw/config.json` 同时存在时使用前者，并把两处同名而内容不同的入口列为提示。

待执行判定针对每条场景的当前内容指纹：

| 原因或类别 | 条件 | 是否进入清单 |
| --- | --- | --- |
| `new` | 该场景编号从未有结果 | 是 |
| `changed` | 该编号有旧指纹的结果，当前指纹没有结果 | 是 |
| `failed` | 当前指纹的最新结果为 `fail` | 是 |
| `source-changed` | 最新结果为 `pass`，其轮次的产品指纹与当前不同，且未声明 `regression.check` | 是 |
| 由回归守护 | 同上，但声明了 `regression.check`；输出提示"需确认该检查在当前源码通过" | 否 |
| 受阻 | 最新结果为 `blocked` 或 `skip`，附 `finding` | 否 |

`submit` 要求结果覆盖清单中的全部场景，可附带清单外场景的结果。登记前后各取一次场景文件 sha256 与产品指纹，期间变化时拒绝，错误代码 `source-stale`。批次名已属于同一检出目录中另一个场景文件路径时拒绝，错误代码 `batch-conflict`。状态目录位于仓库内、含符号链接或无法读写，记录文件无法读取，或 git 无法读取仓库状态时，错误代码 `state-invalid`，问题写明路径与原因；`source-stale` 只表示登记期间场景文件或产品指纹发生了变化。

独立性：给出 `--implementer` 时，执行者与实现者的姓名折叠大小写、去掉首尾空白并把连续空白合为一个后相同标 `self-check`，不同标 `independent`；未给出时标 `undeclared`。三种标注都照常登记。

## 文件格式
<!-- tw-section id=D1 type=data depends=scope-global -->
五种文件，字段与 team-workflow 现行格式同义，各自实现。

**场景文件**。顶层 `metadata` 与 `sops`。`metadata` 必填 `requirement`、`batch`、`version`、`owner` 与非空 `sources`，每项来源含 `ref`、`version`、`confirmed_by`；可选 `tags`。节点必填 `id`、`title`、`actor`、`entry`、`scenarios`，可选 `must`、`negative_exempt`；每个节点至少一条 `positive` 场景，以及一条 `negative` 场景或非空的 `negative_exempt`。场景必填 `id`、`polarity`、`title`、`actor`、`priority`、`verify`、`initial_state`、`steps`、`expected`、`forbidden_effects`，前三个字符串数组非空，`forbidden_effects` 可为空数组；可选 `refs`、`evidence_hints`、`tags`、`regression`。反向场景必填 `negative_type`，取 `empty-input`、`over-length`、`not-found`、`permission`、`cross-tenant`、`duplicate`、`concurrency`、`disconnect`、`timeout`、`archived`、`invalid-input`、`incomplete-input`、`interrupted`、`stale-input`、`tampered-input`、`other`。节点编号与场景编号各自在文件内唯一；`verify` 是已声明的入口名。`regression` 取 `{check, cases}`（`check` 为非空字符串，`cases` 至少一项）、`{manual, owner, trigger}` 或 `{pending}`。格式外字段报错并给出行号。形如 `# 待确认 <编号>：<内容>` 的注释行是待确认预期，报告单列。

**内容指纹**。取 `initial_state`、`steps`、`expected`、`forbidden_effects` 四个字段组成对象，字符串中的 `\r\n` 与 `\r` 换成 `\n`，按 `json.dumps(对象, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` 序列化，取 UTF-8 字节的 sha256 十六进制。

**入口声明** `entries.yaml`。顶层 `entries`，入口名映射到 `surface`、`operate`（非空字符串）、`observe`、`evidence`（非空字符串数组）、`isolation`（非空字符串），可选 `address_env`（环境变量名）。从 `.tw/config.json` 读取时只取这六个字段。

**结果文件**。JSON Lines，每行一个对象。必填 `scenario`、`status`、`actual`、`evidence`、`executed_at`、`executor`；可选 `session`、`finding`、`note`；没有其他字段。`status` 取 `pass`、`fail`、`blocked`、`skip`。`evidence` 是相对结果文件目录、不越出该目录的文件路径数组，`pass` 与 `fail` 至少一项，单个文件不超过 64 MiB。`blocked` 与 `skip` 必填非空 `finding`。`executed_at` 是带时区、不晚于当前时间的 ISO 8601 时间。同一文件每个场景一行，`scenario` 引用场景文件中的编号。

**用例文件**。JSON 或 YAML，顶层 `test_cases` 或 `cases` 数组，每项必填非空字符串 `id`、`title`，其余字段原样保存；同一文件内编号重复报错，错误代码 `cases-invalid`。多次导入按编号取最后一次的完整内容，覆盖要求针对历次导入的并集。

**配对文件**。JSON，含 `covered`、`conflict`、`disposed` 三个数组。前两者每项 `{case, scenarios, note}`，`scenarios` 引用场景文件中的编号；`disposed` 每项 `{case, state, reason, confirmed_by}`，`state` 取 `blocked`、`deferred`、`out-of-scope`。每条导入用例恰好归入一类。存在 `conflict`、遗漏或重复归类时结论为 `scenario-coverage-incomplete`，按遗漏、重复、冲突分别列出用例编号；引用不存在的场景编号时同样报错并点名。

**YAML 子集**。对象、数组、字符串、整数、浮点数、布尔与空值；块样式与流样式；单引号（`''` 转义）与双引号字符串；跨行折叠的普通标量与引号标量，覆盖 PyYAML 以 `allow_unicode=True, default_flow_style=False` 写出的文件；注释。锚点、别名、标签、块标量（`|`、`>`）与多文档报行号拒绝。

## 本机状态与报告
<!-- tw-section id=D2 type=data depends=scope-global,D1 -->
**状态目录**为环境变量 `SOP_VERIFY_STATE`，缺省为 `${XDG_STATE_HOME:-~/.local/state}/sop-verify`。每个检出目录一个子目录，名称为仓库根目录名加其绝对路径 sha256 的前 12 位；其下每个批次一个目录：`batch.json` 记录场景文件的仓内路径，`rounds/<轮次>/round.json` 与证据副本，`cases/` 保存每次导入的快照与当前并集，`coverage/` 保存配对快照与结论。所有子命令都不在仓库内写文件。

**产品指纹**。`git ls-files -z --cached --others --exclude-standard` 列出的文件中，排除 `docs/sop/` 目录、当前场景文件与所用入口文件；按路径排序，每个文件取路径与内容 sha256，已删除的已跟踪文件记为删除，序列化后取 sha256。轮次同时记录 HEAD 提交号与工作区是否有未提交变化（`dirty`）。

**轮次记录** `round.json` 含 `data_version: 1`、`kind: sop-round`、批次、场景文件路径与 sha256、轮次编号、产品指纹、提交号、`dirty`、`implementer`、`submitted_at`、逐条结果（附内容指纹、独立性与证据 `{path, sha256}`）以及本轮统计。

**报告**区块：

1. 头部：批次、需求、来源与确认人、产品提交号与指纹、生成时间。
2. 场景表：编号、极性、当前状态、最新结果、执行者、独立性、实际结果、证据文件名与 sha256 前 12 位、`finding`。
3. 轮次表：每轮执行数、四种结果数、通过率（`pass` 数除以执行数）。
4. 一次通过率：每条场景当前内容指纹的首次结果中，`pass` 数除以 `pass` 与 `fail` 之和。
5. 回归声明：`check`、`manual`、`pending`（含未声明）三类计数与明细。
6. 待确认预期：场景文件中的待确认注释。
7. 未验证范围：受阻与跳过的场景及其 `finding`。

比率在 json 中为 `{numerator, denominator, rate}`，分母为零时 `rate` 为 null；markdown 写"分子/分母"，分母为零时写"无数据"。没有任何轮次时，报告说明尚无执行记录。

## 验收 A1：场景文件与入口核对
<!-- tw-section id=A1 type=acceptance depends=scope-global,I1,D1 -->
SOP-01 节点全部场景通过。

- 场景：docs/sop/sop-verify.yaml#SOP-01
- 依据：位置 AdolphKevin/sop-board docs/proposals/2026-10-19-standalone-sop-verification.md 第 3、4 节；版本 v7（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-1.md 的 I1、D1、D2 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A2：待执行清单
<!-- tw-section id=A2 type=acceptance depends=scope-global,I1,D1,D2 -->
SOP-02 节点全部场景通过。

- 场景：docs/sop/sop-verify.yaml#SOP-02
- 依据：位置 AdolphKevin/sop-board docs/proposals/2026-10-19-standalone-sop-verification.md 第 3、4 节；版本 v7（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-1.md 的 I1、D1、D2 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A3：结果登记
<!-- tw-section id=A3 type=acceptance depends=scope-global,I1,D1,D2 -->
SOP-03 节点全部场景通过。

- 场景：docs/sop/sop-verify.yaml#SOP-03
- 依据：位置 AdolphKevin/sop-board docs/proposals/2026-10-19-standalone-sop-verification.md 第 3、4 节；版本 v7（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-1.md 的 I1、D1、D2 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A4：用例导入与覆盖
<!-- tw-section id=A4 type=acceptance depends=scope-global,I1,D1,D2 -->
SOP-04 节点全部场景通过。

- 场景：docs/sop/sop-verify.yaml#SOP-04
- 依据：位置 AdolphKevin/sop-board docs/proposals/2026-10-19-standalone-sop-verification.md 第 3、4 节；版本 v7（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-1.md 的 I1、D1、D2 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A5：报告
<!-- tw-section id=A5 type=acceptance depends=scope-global,I1,D2 -->
SOP-05 节点全部场景通过。

- 场景：docs/sop/sop-verify.yaml#SOP-05
- 依据：位置 AdolphKevin/sop-board docs/proposals/2026-10-19-standalone-sop-verification.md 第 3、4 节；版本 v7（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-1.md 的 I1、D1、D2 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A6：技能对话
<!-- tw-section id=A6 type=acceptance depends=scope-global,I1 -->
SOP-06 节点全部场景通过。技能场景由只装候选技能的新会话执行，没有自动检查。

- 场景：docs/sop/sop-verify.yaml#SOP-06
- 依据：位置 AdolphKevin/sop-board docs/proposals/2026-10-19-standalone-sop-verification.md 第 3、4 节与 D10；版本 v7（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-1.md 的任务 T2；版本 修订 2；确认人 AdolphKevin
- 检查：无

## 任务 T1：sop.py 与测试
<!-- tw-section id=T1 type=task depends=scope-global,I1,D1,D2 -->
实现命令面、五种文件格式、状态目录与报告。测试放在 `sop-verify/scripts/test_sop.py`，用 `unittest` 编写，以子进程运行 `sop.py`，每个测试使用临时 Git 仓库与临时状态目录；先写失败测试再实现。把 `sop-verify/scripts` 加入 `.tw/config.json` 中 `unit` 检查的命令参数与覆盖入口。本任务一并提交本仓的 tw 接入文件。

- 验收：A1、A2、A3、A4、A5
- 范围：sop-verify/scripts、.tw/config.json、AGENTS.md、CLAUDE.md、docs/verification.md
- 前置任务：无

## 任务 T2：技能文本
<!-- tw-section id=T2 type=task depends=scope-global,I1,D1,D2 -->
在 T1 交回并通过审核之后实施。编写 `sop-verify/SKILL.md`、`references/formats.md`（五种文件的字段与示例）、`references/drivers.md`、`agents/openai.yaml`，并在 README 增加技能条目与安装示例。

技能对话：读 SOP 原文与项目事实（入口、认证、存储、已有测试）；SOP 原文缺失时先询问来源；写 `docs/sop/<批次>.yaml` 与 `docs/sop/entries.yaml`，推断出的预期写成待确认注释，不写入 `expected`；请 SOP 负责人确认，这是唯一必停点，确认人写入 `sources.confirmed_by`；运行 `check`；有测试同事用例时 `import-cases`，按语义写配对并 `coverage`；默认新开一个会话作为执行者，只交给它待执行清单、入口与仓库外的证据目录，执行者身份写会话标识；`submit --implementer <实现者>`；失败场景交回成员自己的开发流程，修复后按 `pending` 复测；最后 `report`。使用者要求不派新会话时，由当前会话执行，`--implementer` 照实填写，报告按独立性标注。

驱动指南：浏览器以 Playwright 连接使用者已登录的真实浏览器，真实账号由使用者本人登录，证据为截图、控制台与请求记录；命令行使用临时 `HOME` 与工作目录，记录命令、输出、退出码与文件清单；接口与数据库指向 verify-backend-sop-db，对话智能体指向 build-scenario-validation-loop，由执行者把它们的结果写成结果文件。

- 验收：A6
- 范围：sop-verify/SKILL.md、sop-verify/references、sop-verify/agents、README.md
- 前置任务：无
