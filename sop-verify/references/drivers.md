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

相对文件参数按仓库根目录解析；本指南统一使用绝对路径。沿用同一[本机状态目录](formats.md#本机记录与报告)登记和复测。以下命令的输出由调用方保存在 `WORK`。

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

`pending` 按当前内容指纹判断，JSON 分为 `pending`、`guarded`、`blocked` 三组：

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
| `scenario-file-invalid` | 按行号修正场景结构、正反向覆盖或入口引用 |
| `entries-invalid` | 补齐有效入口声明 |
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

从子代理、独立命令行会话（例如 `codex exec`）、使用者新开的窗口中任选一种新开会话。将交接内容限定为三项：

1. 待执行清单：编号、当前内容指纹及对应的已确认场景内容，包括初始状态、步骤、预期和应保持不变的结果。
2. 入口：仓库绝对路径、所用入口声明与必要操作环境；执行方法按下节选择。
3. 仓库外的证据目录：给出绝对路径，并指明其中结果文件的绝对路径。

在这份说明中要求执行者：逐条经声明的真实入口操作，保存每条场景的请求或命令原文、完整输出、前后数据与文件清单，以及相应驱动要求的证据；按[结果文件格式](formats.md#结果文件)每行写一条结果，使用自己的会话标识与真实执行时间。将成功、失败、受阻、跳过的实际情况分别填写，受阻和跳过说明 `finding`。证据与结果一并交回。

用当前内容的清单组织一轮执行，登记前保持该轮的场景与产品版本一致；发现版本变化时，按更新后的清单重新执行。凭证沿用项目环境中的引用方式，证据中仅保留环境变量名并对敏感内容脱敏。

## 按入口执行

### 浏览器

使用 Playwright 连接使用者已经登录的真实浏览器。真实账号的交互式登录由使用者本人完成，再沿该浏览器会话操作。逐条保存截图、控制台输出与请求记录，核对界面、请求结果和业务数据的变化。

### 命令行

为被测命令准备临时 `HOME` 与临时工作目录，按入口说明准备隔离数据。逐条记录命令原文、标准输出、错误输出、退出码，以及运行前后的文件清单；有持久化结果时同时记录前后数据。登记脚本沿用本轮原有状态目录，临时 `HOME` 仅用于被测命令。

### 接口与数据库

使用 [verify-backend-sop-db](../../verify-backend-sop-db/SKILL.md) 的真实接口与数据库验证方法，保留请求、响应和持久化数据的确切结果。由执行者把该验证的实际结论与证据引用写入本技能的[结果文件](formats.md#结果文件)。

### 对话智能体

使用 [build-scenario-validation-loop](../../build-scenario-validation-loop/SKILL.md) 运行真实对话并保存完整证据，按该技能完成独立审核。由执行者将审核结论及其证据引用整理为本技能的[结果文件](formats.md#结果文件)。
