# Praxis Skills

Praxis Skills 收录从真实软件项目中沉淀的可复用工程 Skill。每个 Skill 都可以独立安装，用于帮助智能编程工具完成业务流程梳理、质量验证、数据库集成测试和代码提交等工作。

本仓库不绑定某一种智能编程工具。可以通过 [`skills`](https://skills.sh/) 命令行工具，将这些 Skill 安装到 Codex、Claude Code 等受支持的工具中。

## 收录的 Skills

| Skill | 作用 | 适合场景 |
| --- | --- | --- |
| [`build-scenario-validation-loop`](#build-scenario-validation-loop) | 为人工智能服务建立基于场景、证据和独立审核的质量验证闭环 | 智能代理、带状态的人工智能服务、方案对比评测 |
| [`business-flow-mapper`](#business-flow-mapper) | 从代码和文档中还原业务处理流程，生成中文 Mermaid 流程图 | 梳理业务链路、解释系统行为、定位流程分支 |
| [`git-commit`](#git-commit) | 根据暂存区中的实际改动生成规范提交 | 整理提交说明、评估改动风险、创建 Git 提交 |
| [`verify-backend-sop-db`](#verify-backend-sop-db) | 通过真实后端入口和真实数据库验证业务操作规则 | 数据库集成测试、业务规则验收、持久化结果验证 |

### `build-scenario-validation-loop`

为智能代理或人工智能服务建立可追溯的场景验证体系。它把业务规则、可执行场景、接近生产环境的运行、完整证据、独立审核和长期回归测试连接成一个闭环。

它可以用于：

- 在项目中建立或调整场景验证基础设施；
- 把已经确认的业务规则转换成可执行场景；
- 运行局部或完整场景，并保存不可覆盖的证据；
- 根据完整对话、调用记录、状态变化和运行日志进行独立审核；
- 检查证据与审核结果是否对应，防止用不完整结果宣称验证通过；
- 诊断“程序运行完成，但业务含义仍未得到证明”的情况。

示例：

```text
使用 build-scenario-validation-loop，为当前智能客服项目建立场景验证闭环。
```

### `business-flow-mapper`

从代码、文档、测试、运行记录或产品说明中还原一条业务流程，并生成精确的中文 Mermaid 流程图。

它会重点呈现：

- 流程的真实触发点和最终结果；
- 读取和写入的业务数据；
- 权限、状态、策略等判断条件；
- 重试、轮询、人工审核和多轮处理；
- 失败、中止、信息不足和转人工等分支；
- 外部接口调用及其业务影响。

示例：

```text
使用 business-flow-mapper，梳理退款申请从收到请求到退款完成的业务流程。
```

### `git-commit`

读取 Git 暂存区中的实际改动，判断提交类型和范围，生成包含变更摘要、关键内容与风险说明的规范提交。

这个 Skill 只处理已经进入暂存区的文件。使用前需要先明确选择要提交的文件：

```bash
git add <文件路径>
```

它不会自动提交未暂存文件，也不会在提交信息中加入共同作者或签署信息。

示例：

```text
使用 git-commit，提交当前暂存区中的改动。
```

### `verify-backend-sop-db`

把标准操作流程（SOP）或业务规则转换成可长期保留的后端数据库集成测试。测试需要经过真实的应用程序接口、gRPC 接口或服务入口，并使用与生产环境兼容的数据库验证结果。

它会检查明确、可重复的结果，包括：

- 接口返回的数据、原因和被选中的记录；
- 数据库中新增、更新或保持不变的记录；
- 租户、客户或资源不匹配等隔离场景；
- 无可用记录、重复处理和可重试状态；
- 先读取后执行期间发生状态变化时的最终校验；
- 测试结束后的临时数据库和容器清理。

仓库内提供了 PostgreSQL 测试运行脚本，可在项目没有现成测试数据库时启动隔离的 PostgreSQL 容器。

示例：

```text
使用 verify-backend-sop-db，通过真实接口和 PostgreSQL 验证订单自动关闭规则。
```

## 安装

安装前需要准备 Node.js 和 npm。`npx` 会运行当前版本的 `skills` 命令行工具，无需预先进行全局安装。

### 查看可安装的 Skills

```bash
npx skills add https://github.com/AdolphKevin/praxis-skills --list
```

### 交互式安装

运行以下命令后，可以选择要安装的 Skill、安装范围和目标工具：

```bash
npx skills add https://github.com/AdolphKevin/praxis-skills
```

### 安装全部 Skills

下面的命令会跳过确认，并把仓库中的全部 Skill 安装到所有已识别的目标工具：

```bash
npx skills add https://github.com/AdolphKevin/praxis-skills --all
```

### 按需安装

只安装一个 Skill：

```bash
npx skills add https://github.com/AdolphKevin/praxis-skills \
  --skill business-flow-mapper
```

一次安装多个 Skill：

```bash
npx skills add https://github.com/AdolphKevin/praxis-skills \
  --skill business-flow-mapper git-commit
```

### 安装到指定工具

例如，只安装到 Claude Code：

```bash
npx skills add https://github.com/AdolphKevin/praxis-skills \
  --agent claude-code
```

也可以同时指定 Skill 和目标工具：

```bash
npx skills add https://github.com/AdolphKevin/praxis-skills \
  --skill verify-backend-sop-db \
  --agent claude-code
```

### 全局安装

默认情况下，Skill 安装在当前项目范围内。添加 `--global` 或 `-g` 可以安装到用户范围，供多个项目使用：

```bash
npx skills add https://github.com/AdolphKevin/praxis-skills --global
```

## 更新

更新当前项目中已经安装的 Skill：

```bash
npx skills update
```

更新全局安装的 Skill：

```bash
npx skills update --global
```

## 设计原则

- **来自真实项目**：优先沉淀已经解决过实际问题的工程方法。
- **独立可用**：每个 Skill 都有清晰边界，可以单独安装和使用。
- **保留证据**：重要结论应当能够回到代码、测试、运行结果或持久化状态进行核对。
- **尊重项目约定**：进入目标项目后，优先复用已有命令、结构、术语和验证方式。
- **面向长期复用**：产出应能留在项目中，成为后续开发和回归验证的一部分。
