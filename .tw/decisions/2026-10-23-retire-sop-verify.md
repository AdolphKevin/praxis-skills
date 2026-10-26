---
title: "退役 sop-verify，改由 Flow Board 承接"
scope: ["self:README.md", "self:.tw/config.json", "self:docs/verification.md", "self:docs/designs/SOP-VERIFY-*.md", "self:docs/sop/sop-verify*.yaml", "self:verify-backend-sop-db/**"]
source: ["https://github.com/AdolphKevin/sop-board/blob/main/docs/proposals/2026-10-22-integrated-rework.md", "self:README.md", "self:.tw/decisions/2026-10-19-sop-verify-local-mode.md"]
status: "accepted"
tags: ["sop-verify", "退役", "Flow Board", "sop-board", "SOP 验证", "迁移"]
---
# 退役 sop-verify，改由 Flow Board 承接

已退役（2026-10-23）：sop-verify 并入 Flow Board，见 [README](../../README.md#已退役sop-verify)。

## 背景与决定

用户于 2026-10-22 确认 Flow Board 整合方案的 D82：将 `sop-verify` 的会话交接、按入口执行和先报告待处理事项的能力并入随包的 `sop-board` 技能。本仓于 2026-10-23 退役旧技能，删除 `sop-verify/` 以及安装清单、检查命令和覆盖入口中的对应配置。

使用者改为安装 Flow Board（`sop-board`），运行 `sop-board skills install`，在开发会话中用“验证这份 SOP”“为这份 SOP 生成验收场景”等自然语言触发。已安装的旧技能由成员按客户端实际位置移除，操作见 README。

`verify-backend-sop-db`、`build-scenario-validation-loop`、`business-flow-mapper`、`git-commit` 保留原有行为；不用看板的成员仍可单独安装 `verify-backend-sop-db`。

## 备选

- 两边继续提供 SOP 验证入口：用户已决定统一由 Flow Board 承接，因此不保留旧技能作为兼容入口。
- 删除旧设计、场景、决定与教训：会失去历史依据，因此保留原文，并在文首注明退役。

## 放弃过的做法

- 在本仓独立维护 `sop-verify`，以仓库外本机状态目录保存轮次、证据和覆盖快照。
  放弃原因：用户决定将能力并入 Flow Board，避免继续维护两个入口；旧本机状态与旧接口、脚本不迁入 Flow Board。
  来源：`decisions/2026-10-19-sop-verify-local-mode.md`；Flow Board 整合方案 D82。
  关键词：sop-verify、本机模式、独立 SOP 验证、仓库外轮次。

## 后果

本仓不再提供旧技能的安装与执行入口。历史设计、SOP、决定与教训中的旧路径和回归记录仅用于追溯，不再代表当前可运行的入口；其他技能的检查继续保留。移除旧技能和安装 Flow Board 的操作由成员在各自客户端执行。
