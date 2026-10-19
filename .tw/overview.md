---
title: "praxis-skills 项目总览"
source: ["README.md"]
---
# praxis-skills 项目总览

本仓收录从真实项目沉淀的可复用工程技能，每个技能是一个含 `SKILL.md` 的顶层目录，用 skills 命令行工具按需单独安装到 Codex、Claude Code 等工具，不绑定某一种智能编程工具。

| 技能 | 作用 |
| --- | --- |
| `build-scenario-validation-loop` | 为智能代理与有状态 AI 服务建立场景、证据与独立审核的验证闭环；`scripts/` 提供证据哈希与审核绑定核对 |
| `verify-backend-sop-db` | 经真实后端入口与真实数据库验证业务 SOP；`scripts/run_postgres_test.sh` 启动隔离的 PostgreSQL |
| `business-flow-mapper` | 从代码与文档还原业务流程，输出中文 Mermaid 流程图 |
| `git-commit` | 依据暂存区改动生成规范提交 |

技能随安装复制整个目录，`agents/openai.yaml` 是 Codex 的入口描述。技能附带的脚本只用 Python 标准库或系统自带命令，使用者安装后即可运行；测试用 `unittest` 编写，通过 `.tw/config.json` 登记的检查运行。

从 README 开始读，再读要修改的技能的 `SKILL.md` 与其 `references/`。
