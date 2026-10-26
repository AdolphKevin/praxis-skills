<!-- team-workflow:guidance:knowledge start -->
## 项目知识

开工前读取 `.tw/` 中与任务相关的现行约束、决策和踩过的坑：
`python3 <team-knowledge 技能目录>/scripts/tw.py brief --task "<任务>" --path <相关路径>`。
完成后按 team-knowledge 技能的规则更新知识（与代码同一个 PR），并运行 `tw.py check`。
<!-- team-workflow:guidance:knowledge end -->

## 需求完成门槛

- 需求完成须由未参与实现的测试同事、用户或 AI 经用户实际使用的入口执行已确认的 SOP 场景、核对数据结果并留证；实现者自检用于交付准备。
- 预期来自已确认的业务要求、SOP、接口约定或独立事实，不把当前实现的输出当作正确答案。
- 保持场景与断言完整，不删断言、不放宽预期、不跳过场景或改成当前输出来通过。
- 缺真实入口证据或缺独立验收时如实报告未完成范围；回归测试的建设与实际运行情况单独如实报告，不作为交付条件。

业务验收、缺陷复验、回归沉淀与每周复盘读取并遵循 [Flow Board 业务验收与质量改进标准](https://github.com/AdolphKevin/sop-board/blob/main/docs/standard.md)。本仓的入口、运行方式与人工范围见[真实验证操作手册](docs/verification.md)。

## 安全边界

- 凭证只通过环境变量传递，不写入文档、任务说明或证据文件。
- 不自行执行破坏性操作；数据清理按真实验证操作手册的规则进行。
