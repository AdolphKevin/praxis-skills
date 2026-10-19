---
name: sop-verify
description: Verify business SOPs in a Git repository using confirmed test cases and supplementary SOP scenarios, record execution evidence locally or on a board, and guide durable regression tests. Use for SOP verification, SOP acceptance, business scenario validation, or test-case coverage, including 验证 SOP、SOP 验收、业务场景验证、测试用例覆盖.
---

# SOP 业务场景验证

1. **找到依据。** 读取测试同事的用例、SOP 原文和项目事实，查清真实入口、认证、存储、已有测试与实现者，按[会话标识](references/drivers.md#会话标识)记录身份。依据缺失时说明已查位置并询问来源。设置了 `SOP_BOARD_URL` 时按[看板模式](references/board.md)处理：结果推送到看板，`pending`、`report` 读看板；写入缺令牌时请使用者设置 `SOP_BOARD_TOKEN`，保留看板模式。执行、修复与沉淀可交给开发者授权的看板；本会话承接执行时仍按第 5 步交接。

2. **以用例为准形成场景。** 测试同事提供的用例是验收标准，全面覆盖其中的场景，已有 SOP 场景作补充。有看板时上传用例，由看板合并，再用 `pull` 取回；没有看板时按[用例转换与语义去重](references/cases.md)逐条生成同编号场景，按 `section:` 分组并保持节点编号稳定，记录重复的目标用例与理由，再运行 `import-cases`、`coverage`。按[文件格式](references/formats.md)维护 `docs/sop/<批次>.yaml` 和 `entries.yaml`，过程产物放在[仓库外目录](references/drivers.md#命令与路径)。每个节点覆盖正向及反向结果或说明豁免。`expected` 收录有依据且足以据证据判定的结果；推断的预期，以及“给出提示”“显示错误”“通知用户”中缺少的文字、对象或数值，写成 `# 待确认 <编号>：<内容>` 注释并提出具体问题。

3. **确认预期。** 向依据的负责人呈报来源、场景与待确认项，取得可核对的具体结果后继续；沿用本批次已有的有效确认。明确后的结果写入 `expected`，清理对应注释，将确认人写入 `sources.confirmed_by`。新增待确认预期时回到此步。

4. **核对场景与覆盖。** 按[命令顺序](references/drivers.md#命令与路径)运行 `check`。有用例时按[配对格式](references/formats.md#配对文件)核对全部导入用例的并集；看板返回的配对也运行 `coverage`。逐项处理遗漏、重复与冲突，文件与覆盖核对通过后继续。

5. **交给执行者。** 运行 `pending`，有待执行项时按[独立会话交接](references/drivers.md#独立会话交接)配置权限并默认新开会话，交付清单、入口、仓库外证据目录并记录执行身份。使用者明确要求当前会话执行时沿用当前身份。清单为空时核对受阻项和回归检查，再进入第 7 步。

6. **登记与复测。** 执行者按所选[驱动](references/drivers.md#按入口执行)核对结果，交回结果文件与证据。运行 `submit`，`--implementer` 如实填写第 1 步的实现者身份。失败场景及证据交回开发流程，修复后按新 `pending` 清单复测。

7. **沉淀与报告。** 没有看板或仓库未经开发者授权给看板时，执行通过后建议按[测试沉淀与复核](references/distill.md)保留最低成本测试：断言来自场景，新会话一次复核本轮全部测试，丢弃复核临时改动，最多三轮；通过后写回 `regression` 与入口的 `checks`，三轮未通过的场景继续由浏览器执行并说明理由。运行 `report`，按[报告口径](references/formats.md#本机记录与报告)呈报实际证据、通过、失败、受阻、跳过、待确认、回归声明、待执行清单与未验证范围。
