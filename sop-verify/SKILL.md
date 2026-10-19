---
name: sop-verify
description: Verify business SOPs in a Git repository by drafting confirmed positive and negative scenarios, checking test-case coverage, recording execution evidence, and reporting local verification rounds. Use when users request SOP verification, SOP acceptance, business scenario validation, or test-case coverage, including 验证 SOP、SOP 验收、业务场景验证、测试用例覆盖.
---

# SOP 业务场景验证

1. **找到依据。** 读取 SOP 原文和项目事实，查清实际入口、认证方式、存储、已有测试与实现者身份，按[会话标识](references/drivers.md#会话标识)记录身份。原文缺失时，说明已查位置并询问来源；取得原文后进入场景编写。

2. **形成场景。** 按[文件格式](references/formats.md)编写 `docs/sop/<批次>.yaml` 与 `docs/sop/entries.yaml`。业务仓库中的维护文件放在这两处，过程产物放在[仓库外目录](references/drivers.md#命令与路径)。每个节点覆盖正向与反向业务结果。逐项核对可观察结果是否足以判定通过与否，`expected` 只收录已有依据且可据证据判定的结果。推断出的预期，以及原文中仅写“给出提示”“显示错误”“通知用户”而缺少必要内容、对象或数值的部分，统一写成 `# 待确认 <编号>：<内容>` 注释，向负责人提出具体问题。例如“拒绝退款并给出提示”中，拒绝退款可独立核对，提示内容作为待确认项，询问应出现的文字或错误码。

3. **确认预期。** 向 SOP 负责人呈报来源、场景与待确认项，逐项取得可核对的具体结果；这是唯一必停点。沿用当前批次已经明确给出的有效确认。收到符合第 2 步判定要求的答案后，将已明确的结果转入 `expected`，清理对应注释，将确认人写入 `sources.confirmed_by`；新增待确认预期时回到此步。

4. **核对场景与覆盖。** 按[命令顺序](references/drivers.md#命令与路径)运行 `check`，通过后继续。有测试同事用例时，运行 `import-cases`，按用例含义编写配对文件，再运行 `coverage`；逐项处理列出的遗漏、重复与冲突，取得覆盖完整的结论。

5. **交给执行者。** 运行 `pending`；清单为空时进入第 7 步，有待执行项时按[独立会话交接](references/drivers.md#独立会话交接)配置权限并默认新开执行会话，交给它待执行清单、入口与仓库外的证据目录，按交接规则记录执行身份。使用者要求在当前会话执行时，由当前会话执行并沿用其身份记录。

6. **登记与复测。** 执行者按所选[驱动](references/drivers.md#按入口执行)核对业务结果，写出结果文件并交回证据。接收后运行 `submit --implementer <实现者>`，如实填写第 1 步记录的实现者身份。将失败场景及证据交回成员自己的开发流程，修复后按新的 `pending` 清单复测。

7. **报告事实。** 运行 `report`，依据[报告口径](references/formats.md#本机记录与报告)说明通过、失败、受阻、跳过、待确认预期与回归声明。报告中的结论对应实际结果与证据，待执行清单和未验证范围分别呈报。
