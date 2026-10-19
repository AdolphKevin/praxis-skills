---
title: "sop-verify 在仓库外保存轮次，格式与 team-workflow 同义、各自实现"
scope: ["self:sop-verify/**"]
source: ["self:docs/designs/SOP-VERIFY-1.md", "AdolphKevin/sop-board:docs/proposals/2026-10-19-standalone-sop-verification.md"]
status: "accepted"
tags: ["sop-verify", "SOP 验证", "场景验收", "本机状态", "错误代码", "独立执行", "会话标识"]
---
# sop-verify 在仓库外保存轮次，格式与 team-workflow 同义、各自实现

使用者不接入 tw 也能验证业务 SOP：业务仓库只保存 `docs/sop/` 下的场景文件与入口声明；轮次、证据副本、用例并集与配对快照保存在仓库外的状态目录（`SOP_VERIFY_STATE`，缺省 `${XDG_STATE_HOME:-~/.local/state}/sop-verify`），按检出目录分开。所有子命令都不在业务仓库内写文件。

场景文件、入口声明、结果文件、用例文件与配对文件的字段与 team-workflow 现行格式同义，内容指纹算法相同；两个仓库各自实现，不共享代码，格式只加字段。

错误代码各有一个含义：`source-stale` 只表示登记前后场景文件或产品指纹变化；状态目录位于仓库内、含符号链接、不可读写、记录损坏或 git 读取失败为 `state-invalid`；无法归类的异常照常抛出。

执行者默认是新开的会话，身份优先取工具返回的真实会话编号；使用者要求不派新会话时由当前会话执行，实现者照实填写，报告按独立性标注。SOP 中写得不足以判定的结果与推断的预期一样作为待确认问题。

## 备选

- 轮次写进业务仓库：仓库随轮次变重，多人并行时同目录冲突。
- 复用 team-workflow 的运行时：使用者需要接入 tw，与零前置的目标冲突；AdolphKevin 决定两边各自维护。
- 所有读写与 git 故障都报 `source-stale`：使用者会按"源码已变"重跑，而实际要修配置；方案修订 2 新增 `state-invalid`。

## 后果

团队流程可直接用 `tw team scenarios submit` 登记 sop-verify 执行者写出的结果文件。技能场景依赖新开的无头会话执行，Claude Code 下需为执行会话加入仓库外目录（`--add-dir`）。
