# 项目验收方案：praxis-skills

填写依据：team-workflow 技能的 `references/test-capability.md` 第 2 节；本方案同时是本仓的真实验证操作手册，登记在 `.tw/config.json` 的 `context`。
状态：草稿，待 AdolphKevin 确认。

## 项目事实

| 类别 | 内容 | 来源路径 |
| --- | --- | --- |
| 用户实际入口及所属仓库 | 使用者用 skills 命令行工具安装技能目录；代理读取 `SKILL.md` 与 `references/` 照做；技能附带的脚本由代理或成员用 `python3` 或 `bash` 运行 | README.md；各技能的 `SKILL.md` |
| 认证方式与测试身份来源 | 无。脚本不连接需要凭据的服务；`verify-backend-sop-db` 的数据库连接由使用者的环境变量提供 | `verify-backend-sop-db/SKILL.md` |
| 存储 | 无服务端存储；脚本读写使用者指定的文件，`sop-verify` 的本机状态在仓库外的状态目录 | `docs/designs/SOP-VERIFY-1.md` 数据 D2 |
| 消息与通知通道及实际接收端 | 无 | — |
| 外部依赖及可否在测试中运行 | Python 3.10 以上与 `git`，测试中可运行；`run_postgres_test.sh` 需要 Docker，本仓测试不运行它 | 各技能 `scripts/` |
| 配置来源与获取方式 | 环境变量：`SOP_VERIFY_STATE`、`XDG_STATE_HOME`、`TEST_POSTGRES_DSN`、`SOP_DB_ENV` | 各技能 `SKILL.md` |
| 已有测试、运行方式、环境、副作用、断言与跳过行为 | `build-scenario-validation-loop/scripts/test_evidence_utilities.py`：`unittest`，在临时目录调用两个脚本，断言输出与退出码，没有外部副作用，不跳过 | 该文件 |
| CI 平台、任务与产物保存 | 未建设 | 仓库没有 CI 配置 |
| 可用环境及隔离方式 | 本机；每次测试用临时目录与临时 Git 仓库 | — |

## 关键业务保证与验证方式

| 编号 | 需要长期成立的业务结果 | 业务依据 | 风险类型 | 回归层次及理由 | 最终观察点 | 当前能力 |
| --- | --- | --- | --- | --- | --- | --- |
| G1 | `sop.py` 各子命令按格式核对输入、登记结果、给出待执行清单与报告，且不在业务仓库内写文件 | `docs/designs/SOP-VERIFY-1.md` 的 I1、D1、D2 | 公开契约 | E2E：经命令行入口在临时仓库中运行，脚本即产品入口 | 退出码、输出、仓库与状态目录的文件 | 待建设（SOP-VERIFY-1） |
| G2 | 代理按 `sop-verify` 技能从 SOP 写场景、请负责人确认、派新会话执行、登记并报告 | 同上，任务 T2 | 公开契约 | 仅人工：由只装候选技能的新会话执行技能场景 | 会话记录、提出的问题、仓库与状态目录 | 仅人工 |
| G3 | 证据哈希与审核绑定核对拒绝越界、缺失与被改动的文件 | `build-scenario-validation-loop/references/core-contract.md` | 公开契约 | E2E：经脚本入口在临时目录运行 | 退出码与输出 | 已有 |

## 入口与运行方式

### 入口：unit（E2E）

- 覆盖的业务保证：G1、G3
- 起点、终点与经过的真实关键环节：测试以子进程运行脚本，终点是退出码、输出与文件；经过真实的 `git` 与文件系统
- 依赖启动、版本与就绪核对：无外部服务；`uv --version` 与 `python3 --version` 记入执行记录
- 隔离数据：每个测试新建临时目录与临时 Git 仓库，`XDG_STATE_HOME` 指向临时目录；重复与并发运行互不影响
- 本机命令：`uvx --from pytest==8.4.2 pytest -q -p no:cacheprovider build-scenario-validation-loop/scripts sop-verify/scripts`
- CI 任务、参数来源与结果位置：未建设
- 只运行指定场景的方法：追加 `-k <用例名>`
- 失败证据：pytest 输出与 JUnit 报告，由 `tw team run` 保存在 `.tw/local/` 的运行目录
- 清理：测试结束时删除临时目录；清理失败时 pytest 报错并保留路径
- 替代依赖与未覆盖范围：无替代依赖；代理照技能对话的部分不在此入口
- `.tw/config.json` 检查编号与覆盖层次：`unit`，`journey`，`stateless`
- 入口验证证据：待建设
- 维护人：AdolphKevin

### 入口：场景验收 cli 与 skill

- `cli`：执行者在未接入 tw 的临时 Git 仓库中运行候选版 `sop.py`，`XDG_STATE_HOME` 指向临时目录，保存命令、完整输出与前后文件清单
- `skill`：执行者新开会话，只装候选 `sop-verify` 技能，在临时业务仓库中按场景给出任务原话，保存会话记录、命令记录与文件差异
- 结果按 tw 结果契约写入仓库外的目录，用 `tw team scenarios submit` 登记

## 仍需手动的场景

| 场景 | 无法自动化的原因 | 执行责任人 | 触发时机 | 步骤 | 证据位置 |
| --- | --- | --- | --- | --- | --- |
| `docs/sop/sop-verify.yaml` 的 SOP-06 | 判断代理是否照技能对话需要读完整会话 | 验收负责人指派的新会话 | 技能文本变化时 | 按场景给出原话，保存会话 | 仓库外的结果目录 |

## 能力缺口与建设任务

| 缺少的入口 | 影响的业务保证 | 优先级依据 | 建设任务 | 负责人 | 期限 |
| --- | --- | --- | --- | --- | --- |
| CI | G1、G3 | 公开仓库，多人安装 | 待登记 | AdolphKevin | 待定 |

## 确认与维护

- 方案设计者：Claude
- 开发与测试确认人、时间：待 AdolphKevin 确认
- 仍有分歧的事项：无
- 需要同步更新本方案的变化：新增技能脚本、测试入口或外部依赖时
