# 文件格式

五种文件与 team-workflow 的场景格式同义，由本技能独立实现。以下示例使用虚构的人民币退款流程；真实使用时按已确认的 SOP 填写。命令和执行方法见[驱动指南](drivers.md)。

## 场景文件

顶层为 `metadata` 与 `sops`。场景文件、来源对象、节点和场景采用下表所列字段；格式外字段会报所在行。

| 层级 | 必填字段 | 可选字段与约束 |
| --- | --- | --- |
| `metadata` | `requirement` 需求、`batch` 批次、`version` 版本、`owner` 负责人、非空 `sources` 来源数组 | `tags` 标签数组 |
| 每项来源 | `ref` 原文位置、`version` 原文版本、`confirmed_by` 确认人 | 确认流程见[技能入口](../SKILL.md) |
| 每个节点 | `id`、`title`、`actor`、`entry` 入口描述、`scenarios` 场景数组 | `must` 业务保证数组、`negative_exempt` 反向场景豁免理由 |
| 每条场景 | `id`、`polarity`、`title`、`actor`、`priority`、`verify`、`initial_state`、`steps`、`expected`、`forbidden_effects` | `refs`、`evidence_hints`、`tags` 字符串数组，`regression` 回归声明；反向场景必填 `negative_type` |

节点编号与场景编号各自在文件内唯一。每个节点至少有一条 `positive`；反向覆盖采用至少一条 `negative` 或非空的 `negative_exempt`。`priority` 使用非空字符串，如 `P0`；`verify` 填已声明的入口名。`initial_state`、`steps`、`expected` 为非空字符串数组，`forbidden_effects` 为可空的字符串数组。

`negative_type` 的取值为：`empty-input`、`over-length`、`not-found`、`permission`、`cross-tenant`、`duplicate`、`concurrency`、`disconnect`、`timeout`、`archived`、`invalid-input`、`incomplete-input`、`interrupted`、`stale-input`、`tampered-input`、`other`。

`regression` 从下列三种结构选择一种：

| 结构 | 含义与要求 |
| --- | --- |
| `{check: unit, cases: [TestRefund::test_empty]}` | 已有自动检查；`check` 为非空字符串，`cases` 至少一项 |
| `{manual: 核对终端提示, owner: 验收负责人, trigger: 发布前}` | 人工回归方法、负责人、触发时机，均为非空字符串 |
| `{pending: Q-AUTO-1}` | 待建设回归的跟进事项，值为非空字符串 |

示例 `docs/sop/refund-demo.yaml`：

```yaml
metadata:
  requirement: REFUND-DEMO
  batch: refund-demo
  version: 1
  owner: 业务负责人
  sources:
  - ref: docs/退款SOP.md
    version: '1'
    confirmed_by: 业务负责人
sops:
- id: N1
  title: 提交人民币退款
  actor: 客服
  entry: 命令行提交退款
  scenarios:
  - id: N1-P01
    polarity: positive
    title: 合格订单退款成功
    actor: 客服
    priority: P0
    verify: cli
    initial_state: [订单 O1 允许退款]
    steps: [通过入口为 O1 提交退款]
    expected: [返回成功并生成一笔退款记录]
    forbidden_effects: [生成重复退款记录]
  - id: N1-N01
    polarity: negative
    negative_type: empty-input
    title: 订单编号为空
    actor: 客服
    priority: P0
    verify: cli
    initial_state: [订单 O1 允许退款]
    steps: [通过入口提交空订单编号]
    expected: [返回订单编号必填]
    forbidden_effects: [新增退款记录]
```

### 内容指纹

从单条场景取 `initial_state`、`steps`、`expected`、`forbidden_effects`。把每个字符串的 CRLF 与 CR 换成 LF，按键排序，以紧凑 JSON 保留 Unicode，计算 UTF-8 字节的 SHA-256 十六进制值。以下 `scenario` 是已解析的单条场景对象：

```python
import hashlib
import json

fields = ("initial_state", "steps", "expected", "forbidden_effects")
normalized = {
    key: [value.replace("\r\n", "\n").replace("\r", "\n")
          for value in scenario[key]]
    for key in fields
}
payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"))
fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

## 入口声明

`entries.yaml` 顶层的 `entries` 把入口名映射到入口对象：

| 字段 | 要求 |
| --- | --- |
| `surface` | 非空字符串，说明入口形式，如 `cli`、`browser` |
| `operate` | 非空字符串，说明实际操作 |
| `observe`、`evidence` | 非空字符串数组，分别写观察点与证据要求 |
| `isolation` | 非空字符串，说明隔离方式 |
| `address_env` | 可选，保存入口地址的环境变量名 |

来源优先级为 `check --entries` 指定的文件、场景同目录的 `entries.yaml`、仓库 `.tw/config.json` 的 `acceptance_entries`。从配置读取时只取表中六个字段。两处同时存在时采用 `entries.yaml`，同名且内容不同的入口作为提示列出。

示例 `docs/sop/entries.yaml`：

```yaml
entries:
  cli:
    surface: cli
    operate: 在隔离目录中运行项目声明的退款命令
    observe: [标准输出, 退出码, 退款记录]
    evidence: [完整命令记录, 前后数据与文件清单]
    isolation: 临时 HOME、工作目录与演示数据
```

## 结果文件

JSON Lines 文件至少填写一条结果，每行一个对象，同一文件每个场景一行。按执行事实填写下表字段：

| 字段 | 要求 |
| --- | --- |
| `scenario` | 场景文件中的编号 |
| `status` | `pass`、`fail`、`blocked` 或 `skip` |
| `actual` | 实际观察到的结果，非空字符串 |
| `evidence` | 相对结果文件目录的文件路径数组；文件实际位于该目录内，单个文件最多 64 MiB；`pass`、`fail` 至少一项 |
| `executed_at` | 执行时间，带时区且不晚于当前时间的 ISO 8601 字符串 |
| `executor` | 执行会话标识，非空字符串 |
| `session` | 可选，会话标识补充 |
| `finding` | `blocked`、`skip` 必填非空问题说明；其他状态可选 |
| `note` | 可选，补充说明 |

结果对象采用表中字段。将结果文件与证据保存在仓库外的同一结果目录，命令参数使用该文件的绝对路径；`evidence` 字段保持相对路径。下面演示文件结构，执行时将时间、身份、实际结果与证据替换为本轮事实：

```jsonl
{"scenario":"N1-P01","status":"pass","actual":"返回成功，核对到一笔退款记录","evidence":["cli-positive.txt"],"executed_at":"2020-01-01T12:00:00+08:00","executor":"session-demo-01"}
{"scenario":"N1-N01","status":"pass","actual":"返回订单编号必填，退款记录数量保持不变","evidence":["cli-negative.txt"],"executed_at":"2020-01-01T12:00:01+08:00","executor":"session-demo-01"}
```

## 测试同事的用例文件

采用 JSON 或 YAML，顶层为 `test_cases` 或 `cases` 数组。每项必填非空字符串 `id`、`title`，其余字段原样保存；同一文件编号唯一。多次导入按编号取最后一次的完整内容，覆盖要求针对历次导入的并集。

```yaml
metadata: {owner: 测试同事}
test_cases:
- id: TC_001
  title: 正常退款
  priority: P0
  steps: [提交合格订单]
  expected_results: [生成一笔退款记录]
  tags: ["退款", '正常']
- id: TC_002
  title: 空订单编号
  expected_results: [提示必填且记录数量不变]
- id: TC_003
  title: 外币退款
  tags: [范围核对]
```

## 配对文件

采用 JSON，包含 `covered`、`conflict`、`disposed` 三个数组。每条导入用例恰好归入一类：

| 数组 | 每项字段 |
| --- | --- |
| `covered` | `case` 用例编号、非空 `scenarios` 场景编号数组、`note` 配对依据 |
| `conflict` | 与 `covered` 相同，`note` 写语义冲突 |
| `disposed` | `case`、`state`（`blocked`、`deferred`、`out-of-scope`）、非空 `reason`、非空 `confirmed_by` |

`scenarios` 引用当前场景文件的编号。冲突、遗漏、重复归类和不存在的引用会分别列出编号。下例假定业务负责人已确认本批次只覆盖人民币退款：

```json
{
  "covered": [
    {"case":"TC_001","scenarios":["N1-P01"],"note":"合格订单生成一笔退款记录"},
    {"case":"TC_002","scenarios":["N1-N01"],"note":"空编号提示与无新增记录一致"}
  ],
  "conflict": [],
  "disposed": [
    {"case":"TC_003","state":"out-of-scope","reason":"本批次只覆盖人民币退款","confirmed_by":"业务负责人"}
  ]
}
```

## YAML 子集

支持对象、数组、字符串、整数、浮点数、布尔与空值，支持块样式、流样式、注释、单引号的 `''` 转义、双引号及普通标量和引号标量的跨行折叠，兼容 PyYAML 使用 `allow_unicode=True, default_flow_style=False` 写出的文件。用这些结构直接展开内容；锚点、别名、标签、块标量 `|`、`>` 与多文档会报所在行。

## 本机记录与报告

状态目录采用 `SOP_VERIFY_STATE`，默认 `${XDG_STATE_HOME:-~/.local/state}/sop-verify`，放在仓库外。每个检出目录按“根目录名-根目录绝对路径 SHA-256 前 12 位”区分，再按批次保存：

- `batch.json`：场景文件的仓内路径。
- `rounds/<轮次>/round.json` 与证据副本：执行历史。
- `cases/`：每次导入的快照与当前并集。
- `coverage/`：配对快照与结论。

脚本的所有子命令保持业务仓库文件不变。产品指纹覆盖 Git 跟踪文件与未被忽略的未跟踪文件，排除 `docs/sop/`、当前场景文件和所用入口文件；按路径排序后汇总内容哈希，已删除的跟踪文件记为删除。轮次同时记录 HEAD 与工作区的 `dirty` 状态。

轮次记录包含 `data_version: 1`、`kind: sop-round`、批次、场景路径与 SHA-256、轮次、产品指纹、提交号、`dirty`、`implementer`、`submitted_at`、结果及统计。每条结果附内容指纹、独立性、证据路径与 SHA-256。

独立性按 `executor` 与 `--implementer` 比较：折叠大小写、去首尾空白并合并连续空白后相同记 `self-check`，不同记 `independent`；省略实现者记 `undeclared`。三种情况都照常登记。

报告输出到标准输出，默认 Markdown，也可选 JSON，包含七个区块：头部、场景表、轮次表、一次通过率、回归声明、待确认预期、未验证范围。头部列来源、确认人、产品提交号和指纹；场景表列当前状态、最新结果、执行者、独立性、实际结果、证据文件名及哈希前 12 位、`finding`。

每轮通过率为 `pass` 数除以执行数；一次通过率取各场景当前内容指纹的首次结果，以其中 `pass` 数除以 `pass + fail` 数。JSON 比率为 `{numerator, denominator, rate}`，分母为零时 `rate` 为 `null`；Markdown 写“分子/分母”，分母为零写“无数据”。尚无轮次时说明“尚无执行记录”。回归声明按 `check`、`manual`、`pending`（含未声明）计数并列明细；待确认预期取场景注释；未验证范围列受阻与跳过场景及其 `finding`。
