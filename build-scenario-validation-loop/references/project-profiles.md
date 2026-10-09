# Known Project Profiles

Use these profiles to locate current authority. Always re-read the checked-out repository because
commands and schemas evolve.

## memory-gateway

Validation shape: stateful AI service with separated Worker, Oracle, frozen evidence, and an
acceptance-only isolated Codex reviewer.

Locate:

- `acceptance/quality_standard.md`
- `acceptance/reviewer_policy.md`
- `acceptance/reviewer_output.schema.json`
- `acceptance/scenarios.yaml` and the active Oracle
- `scripts/run_dev_acceptance.py` and active harness runner
- `scripts/review_dev_acceptance.py`
- `.agents/skills/memory-gateway-quality-evaluator/SKILL.md`

For a frozen accepted run, prefer the project Skill. Its launcher command is currently shaped as:

```bash
uv run python scripts/review_dev_acceptance.py \
  --run-dir <run-directory> \
  --mode <daily|full>
```

Do not copy historical V6/V7/V8 diagnostic commands into a new run without reading current docs and
candidate gates. Preserve `pass` / `fail` / `needs_review`, per-case citations, Worker/Oracle
isolation, PostgreSQL/runtime proof, and fail-closed macOS reviewer confinement.

## memory-eval

Validation shape: paired comparative experiment with runner-owned objective metrics, a sealed
Evidence Pack, and a separate review step.

Locate:

- `README.md`
- `docs/real-agent-v0.2.md`
- `docs/reviewer-boundary.md`
- `src/cw2_memory_eval/contracts/schemas/codex-review.*.schema.json`
- `src/cw2_memory_eval/real_runtime/review.py`
- `src/cw2_memory_eval_review/`

Core run flow is currently shaped as:

```bash
uv run memory-eval validate --input <input-pack>
uv run memory-eval run --input <private-input-pack> --output <new-evidence-pack>
uv run memory-eval verify-pack <evidence-pack> --require-complete
uv run memory-eval verify-review --pack <evidence-pack> --review <codex-review.json>
```

If the isolated reviewer package is active in the checkout, discover its current CLI before use; a
source invocation is currently shaped as:

```bash
uv run python -m cw2_memory_eval_review review \
  --pack <evidence-pack> --output <new-review-pack> --model <explicit-model>
uv run python -m cw2_memory_eval_review verify-review <review-pack>
```

Never let the reviewer replace paired objective metrics or issue a Memory-only Gate/release ticket.
Preserve complete pair coverage, exact pack hashes, blocking-finding consistency, explicit model
identity, sealed provenance, and reviewer-unavailable behavior.

## cw2-live-chat-agent

Validation shape: dialogue Agent driven through the Go CLI production assembly, with JSONL traces
and a project-local Codex semantic-audit Skill.

Locate:

- `cmd/cli/scenario/**/*.yaml`
- `cmd/cli/scenariorunner/`
- `.agents/skills/scenario-trace-audit/SKILL.md`
- current architecture and acceptance notes
- `artifacts/**/trace.jsonl` and `run.meta.json`

The current basic flow is shaped as:

```bash
go build -o bin/cli ./cmd/cli
./bin/cli -conf ./configs -interactive \
  -scenario ./cmd/cli/scenario/<path>.yaml \
  -case <all|case_id|case_id,case_id>
python3 .agents/skills/scenario-trace-audit/scripts/analyze_scenario_trace.py \
  --scenario ./cmd/cli/scenario/<path>.yaml
```

Read the local Skill before reviewing. Its extractor must only condense evidence; Codex owns
language judgment. Preserve the local `turns[].note` contract and PASS/PARTIAL vocabulary unless an
accepted project change deliberately introduces a full review envelope. Do not infer pass from
trace path events alone.

## cw2-live-chat-agent-py

Validation shape: dialogue Agent with production-shaped service execution, complete directory-level
artifacts, and development-only Codex review.

Locate:

- `AGENTS.md` Scenario review boundary
- `docs/dev/customer-agent-scenarios.md`
- `apps/scenario/`
- `apps/scenario/scenarios/**/*.yaml`
- the simulated-integration launcher under `tests/support/`

Current commands are shaped as:

```bash
uv run python -m apps.scenario <suite.yaml> --env dev
uv run python -m tests.support.simulated_integration_grpc \
  apps/scenario/scenarios --env dev --max-workers <n> \
  --artifact-dir <new-artifact-root>
```

Review the full expected/actual transcript, sanitized trace evidence, business actions, typed
metrics, manifest, triage, and relevant debug logs. Write `<artifact-root>/codex-review.json` with
`PASS` / `FAIL` / `BLOCKED` and artifact hashes. The runner's status is execution evidence only;
application runtimes must never invoke or consume the review.
