# 项目验收方案：praxis-skills

原按 team-workflow 0.x 的 `references/test-capability.md` 填写，该文件已随团队流程移除；现行要求见 [Flow Board 业务验收与质量改进标准](https://github.com/AdolphKevin/sop-board/blob/main/docs/standard.md)第 2、3 节。本方案同时是本仓的真实验证操作手册，登记在 `.tw/config.json` 的 `context`。
状态：草稿，待 AdolphKevin 确认。

sop-verify 已于 2026-10-23 退役，见 [README](../README.md#已退役sop-verify)。下文仅说明保留技能的验证方式。

## 项目事实

| 类别 | 内容 | 来源路径 |
| --- | --- | --- |
| 用户实际入口及所属仓库 | 使用者用 skills 命令行工具安装技能目录；代理读取 `SKILL.md` 与 `references/` 照做；技能附带的脚本由代理或成员用 `python3` 或 `bash` 运行 | README.md；各技能的 `SKILL.md` |
| 认证方式与测试身份来源 | 无。脚本不连接需要凭据的服务；`verify-backend-sop-db` 的数据库连接由使用者的环境变量提供 | `verify-backend-sop-db/SKILL.md` |
| 存储 | 无服务端存储；脚本读写使用者指定的文件 | 各技能 `scripts/` |
| 消息与通知通道及实际接收端 | 无 | — |
| 外部依赖及可否在测试中运行 | Python 3.10 以上与 `git`，测试中可运行；`run_postgres_test.sh` 需要 Docker，本仓测试不运行它 | 各技能 `scripts/` |
| 配置来源与获取方式 | 环境变量：`TEST_POSTGRES_DSN`、`SOP_DB_ENV` | `verify-backend-sop-db/SKILL.md` |
| 已有测试、运行方式、环境、副作用、断言与跳过行为 | `build-scenario-validation-loop/scripts/test_evidence_utilities.py`：`unittest`，在临时目录调用两个脚本，断言输出与退出码，没有外部副作用，不跳过 | 该文件 |
| CI 平台、任务与产物保存 | 未建设 | 仓库没有 CI 配置 |
| 可用环境及隔离方式 | 本机；每次测试用临时目录 | — |

## 关键业务保证与验证方式

| 编号 | 需要长期成立的业务结果 | 业务依据 | 风险类型 | 回归层次及理由 | 最终观察点 | 当前能力 |
| --- | --- | --- | --- | --- | --- | --- |
| G3 | 证据哈希与审核绑定核对拒绝越界、缺失与被改动的文件 | `build-scenario-validation-loop/references/core-contract.md` | 公开契约 | E2E：经脚本入口在临时目录运行 | 退出码与输出 | 已有 |

## 入口与运行方式

### 入口：unit（E2E）

- 覆盖的业务保证：G3
- 起点、终点与经过的真实关键环节：测试以子进程运行脚本，终点是退出码、输出与文件；经过真实的文件系统
- 依赖启动、版本与就绪核对：无外部服务；`uv --version` 与 `python3 --version` 记入执行记录
- 隔离数据：每个测试新建临时目录；重复与并发运行互不影响
- 本机命令：`uvx --from pytest==8.4.2 pytest -q -p no:cacheprovider build-scenario-validation-loop/scripts`
- CI 任务、参数来源与结果位置：未建设
- 只运行指定场景的方法：追加 `-k <用例名>`
- 失败证据：pytest 输出；需要 JUnit 报告时追加 `--junitxml <证据目录>/results.xml`，证据目录放在仓库外或被忽略的 `.tw/local/`
- 清理：测试结束时删除临时目录；清理失败时 pytest 报错并保留路径
- 替代依赖与未覆盖范围：无替代依赖；代理照技能对话的部分不在此入口
- 覆盖层次与运行时机：经 `hash_artifacts.py`、`verify_review_bindings.py` 脚本入口的完整流程，无状态；改动代码或公开契约时必须运行并通过
- 入口验证证据：待建设
- 维护人：AdolphKevin

## 仍需手动的场景

原有手动场景随旧技能退役，仅保留为历史资料；其他技能的手动场景尚未登记。

## 能力缺口与建设任务

| 缺少的入口 | 影响的业务保证 | 优先级依据 | 建设任务 | 负责人 | 期限 |
| --- | --- | --- | --- | --- | --- |
| CI | G3 | 公开仓库，多人安装 | 待登记 | AdolphKevin | 待定 |

## 确认与维护

- 方案设计者：Claude
- 开发与测试确认人、时间：待 AdolphKevin 确认
- 仍有分歧的事项：无
- 需要同步更新本方案的变化：新增技能脚本、测试入口或外部依赖时
