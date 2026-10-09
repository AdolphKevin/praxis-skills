---
name: git-commit
description: "Independent utility Skill for creating clean git commits from already staged changes. Use when the user asks to commit staged work, generate a commit message from git diff --cached, or run a scoped commit workflow."
---

# Git Commit

Generates a clean commit with a properly formatted message from staged changes.

## Usage

```bash
/git-commit
```

**Required before running**: Stage your code files with `git add <files>`

## Step 1: Analyze Staged Changes
Run these commands before composing the commit:

```bash
git diff --cached --stat
git diff --cached
```

If nothing is staged, stop and tell the user to stage files first.

## Step 2: Infer Commit Details
**Automatically determine from the diff:**

- **Change type**: Infer from file paths and diff content:
  - `docs/*.md`, `*.md` changes → `Docs`
  - `cmd/`, `internal/`, `pkg/` with new functionality → `Feature`
  - `fix`, `bug`, `hotfix` in messages → `Bugfix` or `Critical-Fix`
  - `refactor`, `rename`, `extract` → `Refactor`
  - `perf`, `optimize`, `faster` → `Perf`
  - Default to `Feature` if ambiguous

- **Scope**: Infer from the most relevant directory, package, module, or feature area. Keep it short and lowercase.

- **Summary**: Generate from the most meaningful changed files/functions. Focus on *what changed* not *how*.

- **Risk Analysis**: Evaluate:
  - Scope of changes (small = low risk, wide = higher risk)
  - Whether critical paths are affected (auth, payment, data)
  - If tests are included
  - Breaking API changes

## Step 3: Create Commit WITHOUT Co-Authored-By or Signed-off-by
Use plain `git commit` (without `-s` or `-a` flags):

```bash
git commit -m "[Type](scope): Subject

Body explaining the changes in detail.

- Specific key point derived from actual diff
- Another specific key point from the changes
- Technical implementation detail from the code

Risk: <risk_analysis from Step 2>"
```

**⚠️ CRITICAL: Replace placeholder bullets with actual content from the diff. Never use literal placeholders like "Key point 1" - extract specific details from what actually changed.**

**Important**: Do NOT use the Co-Authored-By line or Signed-off-by line. The commit should only contain the message body above.

## Available Types

**⚠️ Use EXACTLY these types (case-sensitive):**

| Type | Description |
|------|-------------|
| `Feature` | New feature or functionality |
| `Bugfix` | Bug fix |
| `Refactor` | Code refactoring without changing behavior |
| `Critical-Fix` | Critical/security bug fix |
| `Docs` | Documentation changes |
| `Perf` | Performance improvements |

## Commit Message Format

The generated commit follows this format:
```
[Type](scope): Subject

Body explaining the changes in detail.

- Specific key point from the diff
- Another specific key point from changes
- Concrete technical detail from code

Risk: <risk_analysis from Step 2>
```

**⚠️ Never use literal placeholders. Always extract real content from the diff.**
