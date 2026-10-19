# 看板模式

设置了非空的 `SOP_BOARD_URL` 时先读本页；空字符串按本机模式处理。请求使用去掉末尾斜杠的地址，写入令牌由使用者在环境中设置 `SOP_BOARD_TOKEN`。缺令牌时请使用者设置该变量，设置后重跑原命令，保留看板模式。令牌只经环境传递，命令记录与证据保留变量名。

项目身份来自 Git 的 `origin`，也可用 `SOP_BOARD_PROJECT` 指定。脚本去掉协议、用户信息、端口与末尾 `.git`，将 SSH 冒号写法转为路径并转小写；例如 `git@github.com:Demo-Org/demo-app.git` 对应 `github.com/demo-org/demo-app`。缺两者时先补项目身份。

## 上传与取回

命令变量及完整命令表见[驱动指南](drivers.md#命令与路径)。有测试同事用例时：

1. 准备可通过 `check` 的当前场景与入口。看板尚无本批次或入口时，先按正常执行流程取得真实结果并 `submit`，随结果推送当前场景和入口；已有入口的批次可直接上传用例。
2. 用 `import-cases` 上传用例，以用例为准交给看板合并。该命令同时保存本机快照，供 `coverage` 核对并集。
3. 看板最新合并任务“已完成”后，`pull` 取回场景及仓库外的配对文件，再运行 `check` 与 `coverage`。

已有场景时：

```sh
python3 "$SOP_PY" --root "$REPO" pull "$SCENARIOS" --pairs "$PAIRS"
```

场景文件尚不存在时，先准备对应入口，用 `BATCH` 指定看板批次：

```sh
python3 "$SOP_PY" --root "$REPO" pull "$SCENARIOS" --batch "$BATCH" --pairs "$PAIRS"
```

`pull` 选择种类为 `merge`、状态为“已完成”的最新任务，写回场景文件；`--pairs` 可选，目标须在仓库外。已有文件的批次取 `metadata.batch`，显式 `--batch` 须与其一致。缺文件又缺 `--batch`、批次不一致或配对路径在仓内时，退出码为 2，保持文件原样。

本地场景须等于合并依据的版本，或已经等于合并结果；首次取回时，合并依据须为空。出现 `pull-conflict` 时保留本地修改，先执行并 `submit` 当前场景，再由看板重新合并后取回。写入后场景可直接 `check`。

## 推送、读取与授权

`submit` 在本机核对后，推送场景原文、当前入口与检查声明、可定位的仓内 SOP 原文、证据和本轮结果；登记前后核对版本。成功输出轮次、统计、待执行清单与批次页面地址。本机保留批次路径绑定、用例及配对快照，轮次和证据保存在看板。

`pending` 读看板的当前场景、最新 Agent 与人工结果及待执行队列。批次尚不存在时全部按 `new` 列出；回归检查附看板的通过或待运行状态，失败检查进入 `failed`；Agent 的 `blocked`、`skip` 单列受阻。看板上的人工失败或受阻进入复测清单。本机产品指纹与看板不同会提示判断基于已推送的版本，按提示先推送当前改动。

`report --format markdown` 原样输出看板报告；JSON 输出 `{ok: true, batch: ...}`，其中 `batch` 是看板批次响应。

开发者可授权看板执行、修复与沉淀；本会话承接执行时仍按[独立会话交接](drivers.md#独立会话交接)派新会话。仓库未经开发者授权给看板时，看板只生成草稿，执行通过后由本会话给出[测试沉淀引导](distill.md)。

## 看板错误

以下错误退出码为 1，保留原始输出并按原因处理：

| 错误代码 | 后续动作 |
| --- | --- |
| `board-token-missing` | 请使用者设置 `SOP_BOARD_TOKEN`，再重跑写入 |
| `project-identity-missing` | 配置 `origin` 或 `SOP_BOARD_PROJECT` |
| `board-unavailable` | 按地址及原因恢复连接；请求超时为 30 秒，JSON 接口须返回 JSON |
| `board-rejected` | 按返回的看板错误代码和问题处理权限或输入；报告批次不存在也属此类 |
| `board-not-configured` | `pull` 需要 `SOP_BOARD_URL`，配置后重跑 |
| `merge-not-found` | 等待本批次合并任务完成，核对任务状态与问题 |
| `pull-conflict` | 按上节处理本地版本并重新合并 |

本机输入和状态错误沿用[驱动指南](drivers.md#清单与登记)的处理规则。
