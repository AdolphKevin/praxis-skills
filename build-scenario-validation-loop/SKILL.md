---
name: build-scenario-validation-loop
description: Build, adapt, operate, and audit a Scenario-plus-Codex validation loop for AI agents, stateful AI services, or comparative evals. Use when Codex needs to add Scenario infrastructure to a repository, turn SOPs into executable cases, run focused or full production-shaped scenarios, freeze complete evidence, create or verify an evidence-bound Codex review, standardize this workflow across projects, or diagnose a run that completed mechanically but still needs semantic judgment. Preserve repository-local commands, schemas, reviewer policies, verdict names, and isolation boundaries.
---

# Build Scenario Validation Loop

Create or operate a six-layer quality loop: business truth, executable scenarios, production-shaped
execution, immutable evidence, independent Codex review, and durable regression assets.

## Route the request

Choose one primary mode before acting:

1. **Build**: add the loop to a project that lacks one.
2. **Adapt**: converge an existing runner or reviewer on the common contract without creating a
   second path.
3. **Author**: turn an SOP or acceptance rule into executable scenarios.
4. **Run**: execute focused, affected, or full scenarios and preserve the result.
5. **Review**: inspect a frozen artifact set and write the repository's review output.
6. **Verify**: validate artifact hashes, review bindings, schemas, and final reporting claims.

For a build or adaptation, read [core-contract.md](references/core-contract.md). For one of the four
known projects, also read [project-profiles.md](references/project-profiles.md). For any review, read
[review-checklist.md](references/review-checklist.md).

## Discover local authority first

1. Read the repository's `AGENTS.md` and applicable nested instructions.
2. Find local Scenario, evaluation, evidence, reviewer-policy, review-schema, and validation files
   with `rg --files` and targeted `rg` searches.
3. Read every applicable project Skill completely. In particular, reuse a local Scenario extractor
   or quality-evaluator Skill rather than duplicating it.
4. Resolve the actual CLI from source, `--help`, tests, or current docs. Treat the known-project
   reference as a discovery hint, not as authority over the checked-out revision.
5. Inspect `git status`. Preserve unrelated and in-progress work; do not require a clean tree unless
   the project's formal run contract requires it.

If a local contract exists, preserve its scenario fields, evidence layout, verdict vocabulary,
review topology, and validators. Do not install the generic templates over it.

## Select the validation shape

Use the smallest shape that proves the target result:

- **Dialogue Agent**: express user input and user-observable expected meaning; inspect complete
  transcript, trace, business actions, state/commit evidence, metrics, and logs.
- **Stateful AI service**: separate Worker input from Oracle; inspect API results, before/after state,
  idempotency, timing, and isolation proof.
- **Comparative evaluation**: freeze both arms and runner-owned objective metrics; let the reviewer
  judge only the dimensions delegated by policy and never recompute objective metrics.

Choose the review topology explicitly:

- **Development review**: the runner writes evidence only; Codex reviews afterward and writes the
  review file. Production and test runtimes never invoke or consume the reviewer.
- **Isolated review launcher**: a separate acceptance-only launcher verifies and freezes evidence,
  starts Codex with isolated credentials and a fail-closed filesystem boundary, then seals and
  validates the result. Never add this topology casually or fall back to unconstrained execution.

## Build or adapt the loop

Implement one authoritative path in the repository's language and conventions:

1. Define the business truth source and ownership.
2. Define a strict scenario schema. Keep natural-language outcome expectations separate from
   deterministic protocol, schema, state, and persistence assertions.
3. Execute through the same core service boundary used by the real product. Simulate external
   systems only at explicit provider boundaries; never replace the AI reasoning under test.
4. Generate a unique run ID and a new artifact root. Record source/config/suite identities so drift
   invalidates the run.
5. Persist the complete evidence needed by the selected validation shape. Redact secrets and
   private content before it reaches ordinary logs or reviewer inputs.
6. Keep execution status distinct from semantic quality status.
7. Add a reviewer policy, strict review schema, evidence binding, and deterministic review
   verification. Use the assets in this Skill only when no local equivalent exists.
8. Add focused and full-run commands plus schema, runner, artifact, failure, and tamper tests.
9. Add a concise project rule stating the review boundary and forbidden runtime coupling.
10. Physically remove an obsolete runner or reviewer path after the new path is accepted; do not
    retain compatibility or dual-write tracks.

## Author scenarios

1. Identify which rules are explicitly accepted by the business owner or current user. Confirm the
   allowed actions, confirmation points, success/failure language, and forbidden commitments.
2. Keep inferred coverage separate from accepted business truth. If the authority does not define
   a behavior, do not invent an accepted Oracle. Omit it, or mark it as proposed using the
   repository's draft mechanism; when no draft mechanism exists, keep it out of the accepted suite
   and report the unresolved decision.
3. Write realistic multilingual and multi-turn user expressions, including independent requests,
   missing information, ambiguity, repeats, external failure, and sensitive-data boundaries.
4. Describe expected user-visible meaning, not one exact phrase. Do not infer intent from keywords
   or locale-specific wording.
5. Put deterministic facts in deterministic tests unless the repository's accepted scenario
   contract explicitly carries structured assertions.
6. Review every generated case for business accuracy before treating it as an Oracle. Record which
   cases are accepted, which remain proposed, and which business decisions are still unresolved.

Use [scenario-suite.example.yaml](assets/scenario-suite.example.yaml) only as a starting point for a
new dialogue-agent contract.

## Run and review

1. Run deterministic tests first when the change affects schemas, effects, state, persistence, or
   evidence generation.
2. Run the smallest affected Scenario set, then the full accepted set when release-level evidence
   is requested.
3. Stop and classify environment, fixture, budget, timeout, cleanup, or artifact failures. Do not
   reinterpret them as semantic success.
4. Freeze or verify the artifact root before review. Never combine green cases from different
   source/config/suite snapshots.
5. Read every artifact required by the local policy. Do not decide from a runner summary or final
   response alone.
6. Write the local review format and bind it to the exact evidence. If the project has no format,
   adapt [reviewer-policy.md](assets/reviewer-policy.md) and
   [codex-review.schema.json](assets/codex-review.schema.json).
7. Run the project's review validator. Use the bundled hash tools as supplementary checks, not as
   replacements for project validators.
8. Report execution and review separately, including limitations and the exact artifact root.

## Evidence utilities

Generate a deterministic review binding map:

```bash
python3 <skill-root>/scripts/hash_artifacts.py <artifact-root> \
  manifest.json triage.json '*-transcript.json' '*-report.md'
```

Add `--format list` when using the generic review schema in this Skill; keep the default mapping
for repositories whose accepted schema uses a path-to-hash object.

Verify bindings recorded by a review:

```bash
python3 <skill-root>/scripts/verify_review_bindings.py \
  --artifact-root <artifact-root> \
  --review <artifact-root>/codex-review.json
```

Resolve `<skill-root>` to the directory containing this `SKILL.md`; do not assume the target
repository has copies of these utilities.

Pass `--allow-no-bindings` only when an authoritative project validator proves binding through a
separate sealed manifest or citation contract.

After changing either bundled evidence utility, run its dependency-free regression suite:

```bash
python3 <skill-root>/scripts/test_evidence_utilities.py
```

## Hard rules

- Never equate runner completion with quality approval.
- Never let the system under evaluation grade itself from its final prose alone.
- Never let a reviewer silently weaken the SOP, Oracle, deterministic metrics, or hard vetoes.
- Never promote inferred or model-generated business behavior into an accepted scenario. Keep it
  proposed until the designated authority explicitly accepts it.
- Never copy secrets, credentials, private identities, or unnecessary raw conversations into the
  review.
- Never claim a full pass from focused evidence or stitch runs across snapshots.
- Never invoke an external reviewer from production runtime code.
- Never overwrite frozen runs, reviews, or evidence packs; create a new output root.
- Never make a generic template compete with an accepted repository-local contract.

## Deliver the result

State which mode and validation shape were used, which local contracts governed the work, what was
created or run, where the immutable evidence and review live, both final statuses, and any remaining
gap. For Author mode, also state the accepted and proposed case counts and list unresolved business
decisions. For setup work, include the focused smoke command that proves the loop end to end.

## 按场景结果输出

调用方给出场景文件与待执行清单时，执行后在调用方指定的仓库外目录写 `results.jsonl`，每条场景一行，覆盖全部待执行项。字段遵循[结果文件格式](../sop-verify/references/formats.md#结果文件)（SOP-VERIFY-1 D1）：按事实填写 `scenario`、`status`、`actual`、`evidence`、`executed_at`、`executor`，会话身份按该格式记录；`blocked`、`skip` 写明非空 `finding`。证据逐个列为相对该结果目录的文件路径，实际文件保存在目录内。交回结果文件与证据，说明可由 `sop-verify submit`（技能内的 `sop.py submit`）或 `tw team scenarios submit` 登记。
