# 驱动与执行

## 命令与路径

运行环境为 Python 3.10 以上与 Git。脚本随技能安装，在任意 Git 仓库中直接使用。为以下变量填写本机绝对路径；结果、证据、用例导入副本与配对文件统一放在仓库外：

| 变量 | 内容 |
| --- | --- |
| `SOP_PY` | 已安装技能的 `scripts/sop.py` |
| `REPO` | 业务仓库根目录 |
| `SCENARIOS` | 仓库内 `docs/sop/<批次>.yaml` |
| `WORK` | 本轮仓库外的过程与证据目录 |
| `CASES`、`PAIRS`、`RESULTS` | `WORK` 中的用例文件、配对文件、结果文件 |
| `IMPLEMENTER` | 被测代码的实际实现者姓名或会话标识 |

相对文件参数按仓库根目录解析；本指南统一使用 `--root` 与绝对路径。执行会话沿用发起者的状态配置，缺省位置见[本机状态目录](formats.md#本机记录与报告)；命令直接以 `python3` 开头。以下命令的输出由调用方保存在 `WORK`。设置了 `SOP_BOARD_URL` 时先读[看板模式](board.md)，按其中的上传、取回与推送规则执行。

| 子命令 | 用途 |
| --- | --- |
| `check` | 核对场景、入口与检查声明 |
| `import-cases` | 导入用例；看板模式下同时上传 |
| `pull` | 取回看板的合并场景，可同时下载配对文件；参数与命令见[上传与取回](board.md#上传与取回) |
| `coverage` | 在本机核对用例并集与场景配对 |
| `pending` | 读取待执行、回归守护与受阻清单 |
| `submit` | 登记结果；看板模式下推送场景、入口、SOP、证据与轮次 |
| `report` | 输出本机或看板报告 |

确认场景后核对文件与入口：

```sh
python3 "$SOP_PY" --root "$REPO" check "$SCENARIOS"
```

有测试同事用例时，按[配对格式](formats.md#配对文件)核对用例含义，再执行：

```sh
python3 "$SOP_PY" --root "$REPO" import-cases "$SCENARIOS" "$CASES"
python3 "$SOP_PY" --root "$REPO" coverage "$SCENARIOS" --pairs "$PAIRS"
```

获取当前待执行清单，用于下节交接：

```sh
python3 "$SOP_PY" --root "$REPO" pending "$SCENARIOS" --format json
```

收到执行者写好的[结果文件](formats.md#结果文件)后登记，再核对新的清单：

```sh
python3 "$SOP_PY" --root "$REPO" submit "$SCENARIOS" --results "$RESULTS" --implementer "$IMPLEMENTER"
python3 "$SOP_PY" --root "$REPO" pending "$SCENARIOS" --format json
```

生成报告，供人阅读或后续处理：

```sh
python3 "$SOP_PY" --root "$REPO" report "$SCENARIOS" --format markdown
python3 "$SOP_PY" --root "$REPO" report "$SCENARIOS" --format json
```

除 `report` 外，命令默认输出文本，可选 `--format json`。JSON 业务输出为含 `ok` 的对象；失败时有 `error_code` 与 `problems`，每项为 `{line, problem}`，无行号时 `line` 为 `null`。文本逐条写问题，有行号时写“第 N 行：问题”，无行号时只写问题。成功退出码为 0，输入或状态问题为 1，参数用法错误为 2。

### 清单与登记

`pending` 的 JSON 分为 `pending`、`guarded`、`blocked` 三组。本机模式按当前内容指纹判断如下；看板模式的结果来源与差异见[推送、读取与授权](board.md#推送读取与授权)。

| 原因或类别 | 条件与后续动作 |
| --- | --- |
| `new` | 编号从未有结果，执行本条 |
| `changed` | 编号有历史结果，当前内容指纹尚无结果，执行本条 |
| `failed` | 当前内容最新结果为 `fail`，交回修复后复测 |
| `source-changed` | 已通过但产品指纹变化且没有 `regression.check`，重新执行 |
| `guarded` | 已通过、产品变化且有 `regression.check`，按提示“需确认该检查在当前源码通过”核对 |
| `blocked` | 当前最新结果为 `blocked` 或 `skip`，单列其 `finding` 并在报告说明范围 |

`submit` 的结果覆盖清单全部场景，可附带清单外场景。登记前后核对场景 SHA-256 与产品指纹；批次绑定同一检出目录中的场景路径。错误按实际输出处理：

| 错误代码 | 处理 |
| --- | --- |
| `scenario-file-invalid` | 按行号修正场景结构、正反向覆盖、入口引用或未声明的 `regression.check` |
| `entries-invalid` | 补齐有效入口与检查声明 |
| `scenario-results-invalid` | 按行号补齐结果、真实时间和可读取的证据；空文件至少填写一条结果 |
| `scenario-results-incomplete` | 补齐列出的待执行场景结果 |
| `source-stale` | 仅用于登记前后场景 SHA-256 或产品指纹不一致，按当前版本重新准备本轮 |
| `state-invalid` | 按问题中的路径和原因，恢复仓库外、无符号链接且可读写的状态目录与记录，处理记录解析问题，或修复 Git 读取问题 |
| `batch-conflict` | 核对已绑定的场景路径，为不同场景文件使用独立批次 |
| `cases-invalid` | 修正用例结构、必填字段或重复编号 |
| `scenario-coverage-incomplete` | 按列出的用例与场景，处理遗漏、重复归类、冲突和无效引用 |
| `not-a-git-repository` | 将 `REPO` 指向实际 Git 仓库 |

保存工具的实际输出。已识别的问题按上表处理；其余异常保留原始异常信息，依据该信息定位原因。

## 独立会话交接

从子代理、独立命令行会话（例如 `codex exec`）、使用者新开的窗口中任选一种新开会话。发起者准备好仓库外的 `WORK` 与缺省状态目录，在启动时为执行会话配置以下权限，并将权限范围写进入口环境说明：

- 读取业务仓库、已安装技能与所选入口需要的文件。
- 读写仓库外的 `WORK`，用于结果文件、证据及会话身份记录；读写缺省状态目录，用于轮次登记。
- 执行[命令与路径](#命令与路径)中列出的 `python3` 命令和已确认的业务入口命令，允许规则使用实际展开后的绝对路径。

Claude Code 可用启动参数 `--add-dir` 加入已存在的证据目录和缺省状态目录；文件写入与 Bash 执行权限按该会话的权限模式及具体允许规则配置。无头会话在启动前完成这些配置，执行者按已获权限操作；权限缺失时在结果中记录 `blocked` 与所需目录或命令，交回发起者处理。目录范围与操作权限的区别见[Claude Code 权限说明](https://code.claude.com/docs/en/permissions#working-directories)。

将交接内容限定为三项：

1. 待执行清单：编号、当前内容指纹及对应的已确认场景内容，包括初始状态、步骤、预期和应保持不变的结果。
2. 入口：仓库绝对路径、所用入口声明与必要操作环境；执行方法按下节选择。
3. 仓库外的证据目录：给出绝对路径，并指明其中结果文件的绝对路径。

在这份说明中要求执行者：逐条经声明的真实入口操作，保存每条场景的请求或命令原文、完整输出、前后数据与文件清单，以及相应驱动要求的证据；按[结果文件格式](formats.md#结果文件)每行写一条结果，按下节确定身份并填写真实执行时间，逐个引用证据文件。将成功、失败、受阻、跳过的实际情况分别填写，受阻和跳过说明 `finding`。证据与结果一并交回。

用当前内容的清单组织一轮执行，登记前保持该轮的场景与产品版本一致；发现版本变化时，按更新后的清单重新执行。凭证沿用项目环境中的引用方式，证据中仅保留环境变量名并对敏感内容脱敏。

## 会话标识

发起者优先从工具的会话元数据、启动回执或结构化输出取得真实会话编号，保存到 `WORK` 的身份记录并随入口环境说明交接。执行者从交接记录或自身工具提供的会话信息核对该编号。具体来源：

- Claude Code 使用 `--output-format json` 返回的 JSON 中取 `session_id`，见[官方会话说明](https://code.claude.com/docs/en/headless#continue-conversations)。
- Codex 使用 `codex exec --json` 返回的事件流中取 `thread.started` 事件的 `thread_id`，见[OpenAI Docs](https://learn.chatgpt.com/docs/non-interactive-mode#make-output-machine-readable)。

真实编号无法取得时，创建一次“工具名-日期时间-用途”的稳定标签，例如 `ClaudeCode-20200101T120000+0800-退款验收`，记录为替代标签，并在同一会话的后续执行、重试与登记中复用。

结果的 `executor` 与 `session` 都填写执行会话的这个非空标识。`--implementer` 填被测代码的实际实现者：人使用姓名，AI 使用其实现会话按本节取得的标识。当前会话同时实现代码和执行验证时，两个角色复用同一身份记录。结果字段约定见[结果文件](formats.md#结果文件)。

## 按入口执行

### 浏览器

使用 Playwright 连接使用者已经登录的真实浏览器。真实账号的交互式登录由使用者本人完成，再沿该浏览器会话操作。逐条保存截图、控制台输出与请求记录，核对界面、请求结果和业务数据的变化。

### 命令行

在被测进程的启动参数中配置临时 `HOME` 与临时工作目录，按入口说明准备隔离数据。逐条记录命令原文、标准输出、错误输出、退出码，以及运行前后的文件清单；有持久化结果时同时记录前后数据。登记进程沿用本机 `HOME` 与缺省状态位置。

### 接口与数据库

使用 [verify-backend-sop-db](../../verify-backend-sop-db/SKILL.md) 的真实接口与数据库验证方法，保留请求、响应和持久化数据的确切结果。由执行者把该验证的实际结论与证据引用写入本技能的[结果文件](formats.md#结果文件)。

### 对话智能体

使用 [build-scenario-validation-loop](../../build-scenario-validation-loop/SKILL.md) 运行真实对话并保存完整证据，按该技能完成独立审核。由执行者将审核结论及其证据引用整理为本技能的[结果文件](formats.md#结果文件)。
