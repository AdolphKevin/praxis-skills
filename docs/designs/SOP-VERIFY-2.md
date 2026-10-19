---
design: "D-sop-verify-2"
task: "SOP-VERIFY-2"
revision: 2
assessment: {"complexity":"complex","risks":["public-contract","cross-service"],"effort":"约一个工作日代理时长","drivers":["sop-verify 在配置了看板时把场景文件、证据与轮次推送到看板，pending 与 report 读看板，pull 取回合并结果","入口声明增加 candidate、start、reload 与顶层 checks，回归声明引用的检查必须已声明","技能文本改为以测试岗用例为准，并在没有看板时引导把通过的场景沉淀为低成本测试","verify-backend-sop-db 与 build-scenario-validation-loop 增加按结果 JSONL 输出的步骤"],"uncertainties":[],"required_skills":["Python 标准库","HTTP","Git","技能写作"]}
roles: {"design_owner":"Claude","implementation_owner":"Codex","acceptance_owner":"AdolphKevin"}
---

# SOP-VERIFY-2：看板客户端与以用例为准

> 本文件是 tw 任务 SOP-VERIFY-2 的方案原文。总体设计见 sop-board 仓库的 `docs/proposals/2026-10-19-standalone-sop-verification.md`（v8），本需求对应其第 8 节 SOP-VERIFY-2 一行，以及 D2、D3、D9、D16、D29 与第 4 节 S1、S2 中属于本需求的部分；看板接口以 sop-board 仓库的 `docs/designs/SOP-BOARD-1.md` 至 `SOP-BOARD-3.md` 为准。验收场景见 [docs/sop/sop-verify-2.yaml](../sop/sop-verify-2.yaml)。
>
> 状态：修订 2。修订 1 于 2026-10-20 经 AdolphKevin 授权由 Claude 代批；修订 2 按测试代理 sop-verify-2-tester 的 21 个待确认问题与 10 处出入补写，并按编写场景时发现的细节补充（推送的入口对象、批次冲突的核对时机、项目不存在时的待执行清单、pull 的取数），同日代批。

## 全局范围
<!-- tw-section id=scope-global type=global-scope -->
设置了环境变量 `SOP_BOARD_URL` 时，sop-verify 以看板为轮次与报告的存放处：`submit` 把场景文件、入口声明、SOP 原文、证据与轮次推送到看板，本机不留轮次副本；`pending` 与 `report` 读看板；新增 `pull` 取回看板上的合并结果写入仓库。没有设置时行为与 SOP-VERIFY-1 相同。入口声明增加 `candidate`、`start`、`reload` 与顶层 `checks`。技能文本改为以测试岗上传的用例为准、SOP 场景只作补充，并在没有看板时引导把通过的场景沉淀为低成本测试；verify-backend-sop-db 与 build-scenario-validation-loop 增加按结果 JSONL 输出每条场景结果的步骤。同时把 SOP-VERIFY-1 方案与场景文件中对总体方案的引用改到 sop-board 仓库。

非目标：`status` 子命令与待办报告（SOP-VERIFY-3）；看板本身的改动；与 team-workflow 或 sop-board 共享代码。

技术选择沿用 SOP-VERIFY-1：Python 3.10 以上标准库与 `git` 命令；HTTP 用 `urllib.request`。

- 需求级验收：A1、A2、A3、A4、A5、A6

| 仓库 | 入口 | 操作 | 产生方 | 使用方 | 提交负责方 | 验收 |
| --- | --- | --- | --- | --- | --- | --- |
| self | sop-verify/scripts/sop.py | submit 推送、pending 与 report 读看板、pull、入口与检查核对 | 开发者与代理 | 看板、业务仓库 | praxis-skills | A1、A2、A3、A4 |
| self | sop-verify/SKILL.md 与 references | 以用例为准、看板模式、沉淀引导 | 维护者 | 使用 sop-verify 的代理 | praxis-skills | A5 |
| self | verify-backend-sop-db、build-scenario-validation-loop 的 SKILL.md | 按结果 JSONL 输出每条场景结果 | 维护者 | 使用这两个技能的代理、sop-verify | praxis-skills | A6 |

## 看板配置与项目身份
<!-- tw-section id=I1 type=interface depends=scope-global -->
`SOP_BOARD_URL`（去掉末尾斜杠）非空时为看板模式，空字符串按未设置处理；写入请求带 `Authorization: Bearer <SOP_BOARD_TOKEN>`。看板模式下需要写入而 `SOP_BOARD_TOKEN` 为空时，在本机核对之后、发出任何看板请求之前以退出码 1 结束，错误代码 `board-token-missing`。看板不可达、超时（30 秒），或约定返回 JSON 的接口返回了非 JSON 时，退出码 1，错误代码 `board-unavailable`，问题写明地址与原因（`report.md` 与合并结果原文按文本读取，只看状态码）；看板返回失败响应时退出码 1，错误代码为 `board-rejected`，`problems` 第一项为"看板错误代码 <error_code>"，其后每项看板问题写成 `{line, problem}`：`line` 取看板问题的 `line`（没有时为 null），`problem` 为"<field>：<problem>"。令牌不出现在任何输出中。

**项目身份**取 `git remote get-url origin`：去掉协议、用户信息、端口与末尾的 `.git`，`git@<主机>:<路径>` 写作 `<主机>/<路径>`，全部转小写；例如 `git@github.com:Demo-Org/demo-app.git` 的身份是 `github.com/demo-org/demo-app`。环境变量 `SOP_BOARD_PROJECT` 有值时以它为准，同样去掉协议与末尾 `.git` 并转小写。两者都没有时退出码 1，错误代码 `project-identity-missing`。项目键按 SOP-BOARD-1 I1 的规则由身份计算；项目名称取仓库根目录名。

## 推送与登记
<!-- tw-section id=I2 type=interface depends=scope-global,I1,D1 -->
看板模式下 `submit <场景文件> --results <结果文件> [--implementer <姓名>]`：

1. 按 SOP-VERIFY-1 的规则在本机核对场景文件、入口与结果文件（错误代码不变）。
2. 推送场景文件：`PUT …/batches/<批次>/scenario-file`，正文含 SOP-BOARD-1 I2 的字段（`project`、`path` 为仓内路径、`commit`、`dirty`、`product_digest` 按 SOP-VERIFY-1 D2、`content`、`fingerprints`、`pushed_by` 取 `git config user.name`，没有时取 `sop-verify`），以及 SOP-BOARD-3 I5 的 `entries`（所用入口声明的内容对象：来自 `entries.yaml` 时为该文件解析后的整个对象；来自 `.tw/config.json` 时为 `{entries: <acceptance_entries>, checks: <checks>}`）与 `sop_sources`（与 SOP-BOARD-3 I5 相同的取法：场景文件 `metadata.sources` 每项 `ref` 按空白切分，去掉各段 `#` 及其后的锚点，取第一个指向仓库内已有文件的相对路径，读取工作区中的原文，附 HEAD 提交号、原文 sha256 与该项 `confirmed_by`；都没有时省略）。
3. 逐个上传证据（`POST /api/v1/evidence`），按 sha256 去重。
4. 登记轮次：`POST …/rounds`，`scenario_file_sha256` 为推送的场景文件原文 sha256，`idempotency_key` 为场景文件 sha256 与结果文件 sha256 两个十六进制字符串直接拼接后再取 sha256，`implementer` 取参数，`submitted_by` 同 `pushed_by`，`product` 为登记前计算的提交号、产品指纹与 `dirty`，每条结果带当前内容指纹与证据的 `{name, sha256}`。
5. 推送前与登记轮次前各取一次场景文件 sha256 与产品指纹，期间变化时在登记前停止，错误代码 `source-stale`（同 SOP-VERIFY-1）；已推送的场景版本留在看板上，不登记轮次。
6. `batch-conflict` 照旧按本机状态目录的 `batch.json` 核对，在推送之前进行；看板模式下本机仍写 `batch.json`。

成功输出看板返回的轮次号与统计、批次页面地址 `<SOP_BOARD_URL>/p/<项目键>/b/<批次>`，以及登记后的待执行清单（按 I3）。本机状态目录中不写轮次与证据。看板模式下 `import-cases` 把用例文件上传到看板（SOP-BOARD-2 I3，`uploaded_by` 同 `pushed_by`），输出看板返回的上传序号与并集条数，同时照旧保存本机快照供 `coverage` 核对；`coverage` 照旧在本机核对。

## 读取看板
<!-- tw-section id=I3 type=interface depends=scope-global,I1 -->
看板模式下 `pending <场景文件>` 读 `GET …/batches/<批次>/scenarios`，对本地场景文件的每条场景：看板当前版本中没有该编号时原因 `new`；指纹与看板不同时原因 `changed`；指纹相同时按看板给出的最新 Agent 结果与最新人工结果中轮次号较大的一条（"最新结果"）与队列：没有结果为 `new`；最新结果为 Agent `fail`、人工 `fail` 或人工 `blocked` 为 `failed`；在待执行队列而有过 Agent 通过为 `source-changed`。声明了 `regression.check` 的场景，看板 `regression_status`（SOP-BOARD-4 I5）为 `failed` 时按 `failed` 进入清单，其余列为"由回归守护"并附"检查通过"或"检查待运行"（字段缺失按待运行）；最新结果为 Agent `blocked` 或 `skip` 的列为"受阻"；这两类不进入清单。`pending` 只发读取请求。项目或批次在看板上不存在时，全部场景按 `new` 列出。输出格式与 SOP-VERIFY-1 相同，另附批次页面地址。

看板模式下 `report <场景文件>`：`--format markdown`（缺省）输出 `GET …/batches/<批次>/report.md` 的原文；`--format json` 输出 `{ok: true, batch: <GET …/batches/<批次> 的响应>}`。批次不存在时退出码 1，错误代码 `board-rejected`。

## 取回合并结果
<!-- tw-section id=I4 type=interface depends=scope-global,I1 -->
新增子命令 `pull <场景文件> [--pairs <文件>]`，只在看板模式下可用（未设置 `SOP_BOARD_URL` 时退出码 1，错误代码 `board-not-configured`）。批次名取场景文件的 `metadata.batch`；场景文件尚不存在时用 `--batch <批次>` 指定。参数先行核对：场景文件不存在且没有 `--batch`、`--batch` 与已存在场景文件的 `metadata.batch` 不同、`--pairs` 指向仓库内，都以退出码 2 结束，不发请求、不写文件。读取 `GET /api/v1/tasks?project=<项目键>&batch=<批次>` 中种类为 `merge`、状态为"已完成"的最新任务（任务字段 `scenario_file_sha256` 为其依据的场景版本原文 sha256，SOP-BOARD-3 I3）：

- 没有这样的任务时退出码 1，错误代码 `merge-not-found`。
- 该任务依据的场景版本原文 sha256 与本地场景文件的 sha256 不同（本地文件不存在时视为依据为空），且本地文件也不等于合并结果时，退出码 1，错误代码 `pull-conflict`，问题写明本地修改需先 `submit` 推送后由看板重新合并；不写任何文件。
- 否则把 `GET …/merges/<任务编号>/scenario-file` 的原文写入场景文件（已相同时不改写）；给出 `--pairs` 时把 `pairs.json` 写到该路径。输出写入的文件、合并任务编号与对应关系条数（条数取自 `…/merges/<任务编号>/pairs.json`；"最新"指任务编号最大）。写入后的场景文件可直接 `check`。

## 入口与检查声明
<!-- tw-section id=D1 type=data depends=scope-global -->
`entries.yaml` 的入口增加可选字段：`candidate` 取 `checkout`、`start`、`in-place`，缺省 `in-place`；`start` 与 `reload` 为非空字符串数组，`candidate` 为 `start` 时 `start` 与 `address_env` 必填。顶层增加可选 `checks`，字段同 tw 的 `checks`：核对 `argv`（非空字符串数组）、`cwd`（字符串，缺省 `.`）、`timeout`（正整数）、`format`（`junit` 或 `go-json`）、`report`（`format` 为 `junit` 时必填）、`required_env`（字符串数组）；tw 的其他检查字段（如 `purpose`、`required_cases`、`environment`、`coverage`）原样接受而不使用。入口与检查的来源同 SOP-VERIFY-1 的入口来源顺序；`entries.yaml` 与 `.tw/config.json` 同时存在时检查也取前者，两处同名而内容不同的检查列为提示。场景的 `regression.check` 引用的检查编号不在已声明的检查中时，`check`、`pending` 与 `submit` 报 `scenario-file-invalid` 并给出行号。不合格的入口与检查声明报 `entries-invalid` 并给出行号。

## 技能文本
<!-- tw-section id=D2 type=data depends=scope-global,I2,I3,I4 -->
sop-verify 的 SKILL.md 与 references 按下面改写（篇幅保持精简，原有对话流程中仍有效的部分保留）：

1. **以用例为准**：测试岗提供了用例时，以用例为验收标准，全面覆盖用例中的场景；本仓已有的 SOP 场景只作补充。有看板时用例上传到看板，由看板合并，开发者 `pull` 取回；没有看板时代理按总体方案 S7 把每条用例转成同编号的场景（节点按 `section:` 分组，编号规则同 SOP-BOARD-3 I4），表述不同而内容相同的 SOP 场景按语义去重（写明与哪条用例重复及理由），再 `import-cases` 与 `coverage`。
2. **看板模式**：设置了 `SOP_BOARD_URL` 时说明结果推送到看板、`pending` 与 `report` 读看板，执行、修复与沉淀可由开发者授权的看板完成；开发者在本会话中执行时照常派遣新会话。缺写入令牌时请使用者设置 `SOP_BOARD_TOKEN`，不自行改用本机模式。
3. **沉淀引导**：没有看板时，场景经 Agent 执行通过后，代理建议把它们沉淀为仓库内最低成本的自动化测试（单元、接口、集成依次选择），断言来自 `expected` 与 `forbidden_effects`；沉淀后另开一个新会话一次复核本轮全部测试，复核中的临时改动全部丢弃，最多三轮；通过后把 `regression: {check, cases}` 写入场景，并在入口声明的 `checks` 中声明检查；三轮仍未通过的场景不写回归声明，告知使用者这些场景继续由浏览器执行及理由。仓库未经开发者授权给看板时（看板不会为它沉淀），即使在看板模式下也给出这一引导。
4. 命令表增加 `pull`，入口声明说明增加 `candidate`、`start`、`reload` 与 `checks`。

## 驱动的结果输出
<!-- tw-section id=D3 type=data depends=scope-global -->
verify-backend-sop-db 与 build-scenario-validation-loop 的 SKILL.md 各增加一节"按场景结果输出"：调用方给出场景文件与待执行清单时，执行完成后在调用方指定的仓库外目录写 `results.jsonl`（字段与 SOP-VERIFY-1 D1 的结果文件相同，证据为该目录内的文件路径，`blocked` 与 `skip` 写明 `finding`），每条场景一行，并说明该文件可由 `sop-verify submit` 或 `tw team scenarios submit` 登记。两个技能其余内容不变。

## 引用更正
<!-- tw-section id=D4 type=data depends=scope-global -->
`docs/designs/SOP-VERIFY-1.md`、`docs/sop/sop-verify.yaml` 与 `.tw/decisions/2026-10-19-sop-verify-local-mode.md` 中指向 team-workflow 仓库 `docs/proposals/2026-10-19-standalone-sop-verification.md` 的引用，改为 sop-board 仓库的同名文件（该文件已迁入 sop-board，v8 保留 v7 的批准记录）。只改引用位置，其余文字不变；SOP-VERIFY-1 场景的内容指纹不变。

## 验收 A1：看板配置与推送登记
<!-- tw-section id=A1 type=acceptance depends=scope-global,I1,I2 -->
SOP-21 节点全部场景通过。

- 场景：docs/sop/sop-verify-2.yaml#SOP-21
- 依据：位置 sop-board 仓库 docs/proposals/2026-10-19-standalone-sop-verification.md 的 D3、D16 与第 4 节 S1；版本 v8（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-2.md 的 I1、I2 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A2：读取看板
<!-- tw-section id=A2 type=acceptance depends=scope-global,I3 -->
SOP-22 节点全部场景通过。

- 场景：docs/sop/sop-verify-2.yaml#SOP-22
- 依据：位置 sop-board 仓库 docs/proposals/2026-10-19-standalone-sop-verification.md 的 D3 与第 4 节 S1、S2；版本 v8（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-2.md 的 I3 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A3：取回合并结果
<!-- tw-section id=A3 type=acceptance depends=scope-global,I4 -->
SOP-23 节点全部场景通过。

- 场景：docs/sop/sop-verify-2.yaml#SOP-23
- 依据：位置 sop-board 仓库 docs/proposals/2026-10-19-standalone-sop-verification.md 的 D16 与第 4 节 S1；版本 v8（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-2.md 的 I4 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A4：入口与检查声明
<!-- tw-section id=A4 type=acceptance depends=scope-global,D1 -->
SOP-24 节点全部场景通过。

- 场景：docs/sop/sop-verify-2.yaml#SOP-24
- 依据：位置 sop-board 仓库 docs/proposals/2026-10-19-standalone-sop-verification.md 的 D2、D23；版本 v8（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-2.md 的 D1 节；版本 修订 2；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A5：技能文本
<!-- tw-section id=A5 type=acceptance depends=scope-global,D2 -->
SOP-25 节点全部场景通过。

- 场景：docs/sop/sop-verify-2.yaml#SOP-25
- 依据：位置 sop-board 仓库 docs/proposals/2026-10-19-standalone-sop-verification.md 的 D16、D29；版本 v8（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-2.md 的 D2 节；版本 修订 2；确认人 AdolphKevin
- 检查：无

## 验收 A6：驱动的结果输出与引用更正
<!-- tw-section id=A6 type=acceptance depends=scope-global,D3,D4 -->
SOP-26 节点全部场景通过。

- 场景：docs/sop/sop-verify-2.yaml#SOP-26
- 依据：位置 sop-board 仓库 docs/proposals/2026-10-19-standalone-sop-verification.md 的 D9；版本 v8（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-2.md 的 D3、D4 节；版本 修订 2；确认人 AdolphKevin
- 检查：无

## 任务 T1：看板客户端与入口声明
<!-- tw-section id=T1 type=task depends=scope-global,I1,I2,I3,I4,D1 -->
实现 I1 至 I4 与 D1。测试在临时 Git 仓库中运行 sop.py，看板用测试内以标准库 http.server 启动的模拟看板（按 SOP-BOARD-1 至 3 的接口记录请求并返回预设响应），另有一项真实入口验证由验收执行者以本机启动的 sop-board 看板完成。先写失败测试再实现。

- 验收：A1、A2、A3、A4
- 范围：sop-verify/scripts
- 前置任务：无

## 任务 T2：技能文本、驱动与引用
<!-- tw-section id=T2 type=task depends=scope-global,D2,D3,D4 -->
在 T1 之后实施。按 D2 改写 sop-verify 的 SKILL.md 与 references，按 D3 修改两个驱动技能，按 D4 更正引用。技能文本的效果由验收执行者以只装候选技能的新会话检验。

- 验收：A5、A6
- 范围：sop-verify、verify-backend-sop-db、build-scenario-validation-loop、docs/designs/SOP-VERIFY-1.md、docs/sop/sop-verify.yaml、.tw/decisions
- 前置任务：无
