---
design: "D-sop-verify-3"
task: "SOP-VERIFY-3"
revision: 1
assessment: {"complexity":"medium","risks":["public-contract"],"effort":"约半个工作日","drivers":["sop-verify status 列出看板上本仓库待开发者处理的事项","技能在开发者下次使用 sop-verify 时先报告这些事项"],"uncertainties":[],"required_skills":["Python 标准库","HTTP","技能写作"]}
roles: {"design_owner":"Claude","implementation_owner":"Codex","acceptance_owner":"AdolphKevin"}
---

# SOP-VERIFY-3：待开发者处理事项

> 本文件是 tw 任务 SOP-VERIFY-3 的方案原文。总体设计见 sop-board 仓库的 `docs/proposals/2026-10-19-standalone-sop-verification.md`（v8），本需求对应其第 8 节 SOP-VERIFY-3 一行与 D28；看板接口以 sop-board 仓库 `docs/designs/SOP-BOARD-5.md` 的 I8（待开发者处理的事项）为准。验收场景见 [docs/sop/sop-verify-3.yaml](../sop/sop-verify-3.yaml)。
>
> 状态：修订 1，2026-10-20 经 AdolphKevin 授权由 Claude 代批。

## 全局范围
<!-- tw-section id=scope-global type=global-scope -->
新增 `sop-verify status`：配置了看板时列出当前仓库在看板上待开发者处理的事项，每项附看板链接、原因与接续会话的命令；技能要求代理在开发者使用 sop-verify 时先运行 `status` 并报告这些事项。看板不向会话推送消息。

非目标：看板侧的事项计算（SOP-BOARD-5、6）；没有看板时的事项（没有看板就没有自动任务，`status` 只说明未配置看板）。

- 需求级验收：A1、A2

| 仓库 | 入口 | 操作 | 产生方 | 使用方 | 提交负责方 | 验收 |
| --- | --- | --- | --- | --- | --- | --- |
| self | sop-verify/scripts/sop.py status | 读取看板事项并输出 | 看板 | 开发者与代理 | praxis-skills | A1 |
| self | sop-verify/SKILL.md | 先报告待开发者处理的事项 | 维护者 | 使用 sop-verify 的代理 | praxis-skills | A2 |

## status 子命令
<!-- tw-section id=I1 type=interface depends=scope-global -->
`sop.py status [--format text|json]`，在 Git 仓库内运行（仓库外报 `not-a-git-repository`），不需要场景文件参数。未设置 `SOP_BOARD_URL` 时退出码 0，text 输出"未配置看板（SOP_BOARD_URL），没有看板上的待处理事项"，json 输出 `{ok: true, board: null, items: []}`。设置时按 SOP-VERIFY-2 I1 计算项目身份与键，读取 `GET /api/v1/projects/<项目键>/attention`：

- 项目在看板上不存在（404 `project-not-found`）时退出码 0，说明看板上还没有该项目，`items` 为空。
- 看板不可达等错误沿用 SOP-VERIFY-2 I1 的错误代码与退出码 1。
- 成功时 text 按种类分组逐项输出，组的先后依次为待开发者处理、待开发者合入、待提交、待补充、待同步、Jira 状态待人工更新、已中断（未知种类排在最后，以原值作组名），组内保持看板返回的顺序；每项写批次（没有批次的写"项目级"）、任务编号、原因、看板链接，以及有会话时"接续：<命令>"；没有事项时输出"看板上没有待开发者处理的事项"。json 输出 `{ok: true, board: <地址>, project: <项目键>, items: [...]}`，`items` 为看板返回的原样各项。

`status` 不写任何文件，不需要写入令牌。

## 技能文本
<!-- tw-section id=D1 type=data depends=scope-global,I1 -->
sop-verify 的 SKILL.md 在对话流程开头增加一步：设置了 `SOP_BOARD_URL` 时先运行 `status`，有事项时先向开发者逐项报告（种类、原因、链接、接续命令），询问是否先处理，再继续本次请求；没有事项时不报告；`status` 失败（如看板不可达）时用一句话说明未能读取待处理事项及原因，然后继续本次请求。命令表增加 `status`。篇幅保持精简。

## 验收 A1：status 子命令
<!-- tw-section id=A1 type=acceptance depends=scope-global,I1 -->
SOP-31 节点全部场景通过。

- 场景：docs/sop/sop-verify-3.yaml#SOP-31
- 依据：位置 sop-board 仓库 docs/proposals/2026-10-19-standalone-sop-verification.md 的 D28 与第 4 节 S1；版本 v8（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-3.md 的 I1 节；版本 修订 1；确认人 AdolphKevin
- 检查：unit
- 验证：自动

## 验收 A2：先报告待处理事项
<!-- tw-section id=A2 type=acceptance depends=scope-global,D1 -->
SOP-32 节点全部场景通过。

- 场景：docs/sop/sop-verify-3.yaml#SOP-32
- 依据：位置 sop-board 仓库 docs/proposals/2026-10-19-standalone-sop-verification.md 的 D28；版本 v8（2026-10-19）；确认人 AdolphKevin / 位置 docs/designs/SOP-VERIFY-3.md 的 D1 节；版本 修订 1；确认人 AdolphKevin
- 检查：无

## 任务 T1：status 与技能文本
<!-- tw-section id=T1 type=task depends=scope-global,I1,D1 -->
实现 I1 与 D1。测试用以标准库 http.server 启动的模拟看板返回各种事项与错误；技能文本的效果由验收执行者以只装候选技能的新会话检验。先写失败测试再实现。

- 验收：A1、A2
- 范围：sop-verify
- 前置任务：无
