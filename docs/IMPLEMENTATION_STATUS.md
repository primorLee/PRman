# Implementation status

PRman 0.6.0 is a pre-alpha Codex Skill for ordinary developers who want to contribute to well-known
open-source projects. Its default flow is: ask how many PRs are wanted, ask for a repository and
Issue or collect direction and minimum-Star preferences, then complete that many contributions
sequentially. Every contribution gets meaningful-target selection, implementation, tests,
challenge review, a simple preview, separate repository-bound confirmation, Draft PR creation, and
CI follow-up. After intake, the Skill automatically creates or reuses a Codex Goal when available so
the session continues between genuine user checkpoints. Detailed quality and authorization
artifacts remain internal. The repository is public at primorLee/PRman and licensed under
Apache-2.0.

The 0.4.0 Plugin installation and routing checks passed on 2026-08-30. The new 0.6.0 intake,
high-value selection, and adversarial-review experience is implemented in source and local
contracts but still needs fresh installed-Plugin and live GitHub end-to-end validation before a
production claim.

## Implemented workflow

- Installable Codex Plugin and implicitly discoverable prman Skill.
- GitHub MCP dependency declared in the Skill metadata; no PRman-owned token or credential store.
- Intake that uses a supplied repository and Issue when present, asks only for missing target
  information, always collects a positive requested PR count, and otherwise waits for the
  developer's technical direction and minimum-Star answer before searching.
- Automatic Goal lifecycle instructions after completed intake: inspect current Goal state, create
  one session Goal when none exists, reuse a matching Goal, avoid replacing unrelated work, omit an
  unrequested token budget, and fall back cleanly when Goal tools are unavailable.
- A Goal objective that binds the exact intake, meaningful-contribution quality bar, sequential
  workflow, verification, per-PR confirmation, CI follow-up, and honest early-stop condition.
- Autonomous continuation through safe in-scope stages, while preserving stops for mandatory
  intake, exact Draft PR confirmation, platform approvals, and genuinely user-only decisions.
- Sequential session progress for the requested number of PRs. Each contribution completes the
  entire workflow and receives a separate preview and exact confirmation before the next begins;
  the count never acts as batch write authorization.
- Read-only repository and issue discovery focused by default on one recognised, active,
  contribution-friendly project, with automatic selection when there is a clear best target.
- Suitability checks for issue clarity, manageable scope, outside-contributor acceptance,
  duplicate work, verification feasibility, usefulness, and anti-spam behavior.
- An explicit value case for every shortlisted task, rejecting repository-scanner trivia,
  formatting-only changes, incidental spelling and badge churn, unrelated lint cleanup, generated
  bulk edits, and other PR-for-PR's-sake work.
- Inspection of agent instructions, README, contribution and security policies, license, issue
  context, pull-request template, default branch, full base commit, and CI configuration.
- Codex-native local implementation and execution of repository-prescribed verification.
- A mandatory skeptical maintainer-style review of the exact final diff, including issue coverage,
  regressions, test strength, repository conventions, accidental scope, duplicate work, and the
  strongest likely rejection reason. Credible findings trigger edits, retesting, and a fresh review.
- Existing deterministic assessment after the final diff, with two revision rounds by default.
- A simple user-facing preview covering the selected task, why it was chosen, changed files, tests,
  risks or unknowns, Draft PR title, and a reviewable full diff.
- An internal exact packet covering repository, task, branch and fork route, base commit, diff,
  verification, assessment, Draft PR text, all writes, and CI repair budget.
- Runtime validation of the exact patch digest, target and fork route, Draft-only plan, structural
  ready-state prerequisites, allowed writes, confirmation text, and CI budget.
- Short target-specific confirmation phrase: `CREATE DRAFT PR OWNER/REPO`. Plain yes/confirm,
  a different repository, and whitespace-normalized variants are rejected.
- A content-bound write-authorization artifact limited to the confirmed repository, base commit,
  head route, initial diff, Draft PR operations, and repair budget.
- Internal treatment of ready, revise, and abstain. These labels are not shown by default. Missing
  production scoring can never be represented as ready; the preview instead says plainly that the
  optional extra quality score is unavailable.
- Draft-only GitHub publication after confirmation, using Codex's connected GitHub tools.
- Default maximum of two same-scope CI repair rounds, with new verification and assessment after
  each edit.
- Executable run states for authorized, Draft-open, CI-failed, repairing, and complete. The helper
  rejects a mismatched base, head route, diff, PR URL or number, normal PR, stale CI commit,
  exhausted repair budget, unchanged repair diff or commit, and a caller-declared out-of-scope
  update.
- New confirmation required for a stale packet or material scope change.
- Hard prohibitions on default-branch writes, force-push, merge, auto-merge, marking ready for
  review, parallel or unreviewed bulk PRs, and public vulnerability disclosure.

The machine-readable confirmation, preparation check, authorization, and workflow-run shapes are in
schemas/, with an example packet in examples/confirmation-packet.json. The installed Skill wrapper
is skills/prman/scripts/workflow.py.

## Implemented quality core

- Duplicate-safe JSON parsing with a 4 MiB input limit.
- Assessment 1.1 bindings for repository ID, base commit, task text and digest, supplied diff,
  candidate digest, and candidate-specific typed evidence.
- Passing test evidence requires command, zero exit code, candidate ID, timestamp,
  producer/version, and log digest.
- The default blocking gates are scope, secrets, tests, and adversarial review. Passing adversarial
  review requires inspection or service evidence bound to the exact final candidate; missing,
  incomplete, or failed review cannot be overridden by scoring.
- Production readiness requires a canonical assessment HMAC from the executor key fixed by the
  decision profile; missing or invalid evidence attestations cannot produce ready.
- Core-generated allowlisted scorer requests; callers cannot supply arbitrary criterion payloads.
- Required blocking gates and non-blocking advisory gates, with actionable recoverable failures.
- Six-criterion geometric aggregation, criterion minima, absolute lower-confidence-bound floor,
  uncertainty and truncation limits, and comparison margin.
- OOD, excessively uncertain, and excessively truncated candidates excluded from comparison.
- Provider/model/calibrator metadata pinned for the assessment and decision profile.
- HMAC-authenticated numeric-loopback HTTP scoring with nonces, signed identity, proxy and redirect
  disabling, timeout, and request and response size caps.
- Trusted in-process Python entry-point scorers behind explicit CLI opt-in.
- Test-only provider classification; fixture and static selections always force abstain.
- Provider failures and malformed output converted to structured fail-closed results.
- Runtime and JSON-Schema consistency tests, type checking, branch coverage, HTTP signature tests,
  and wheel and sdist checks.
- Every assessment result keeps external_write_authorized false; only the later human packet can
  authorize the listed operations.
- Confirmation and workflow CLIs validate transitions without implementing GitHub access or storing
  credentials.

The archived review that motivated the assessment hardening is
[security-review-2026-08-29.md](security-review-2026-08-29.md).

## Previously validated Codex installation

The PRM-008 acceptance run validated version 0.4.0 from the default local `personal` marketplace and
verified all of the following in ephemeral, read-only Codex tasks started outside this repository:

- Explicit `$prman` invocation loaded version `0.4.0` from the Plugin cache.
- A request to find a repository, implement a bug fix, and send a PR selected PRman implicitly.
- A generic Python question did not invoke or mention PRman.
- The bundled workflow helper resolved from the installed cache and prepared the expected packet.
- Uninstall and reinstall with `0.4.0+codex.validation-20260830` produced a new cache entry, and a
  subsequent fresh task reported that exact installed version.
- Both before and after reinstall, the task rejected a plain yes as write authorization and allowed
  only an explicitly confirmed Draft PR. This confirms the safety boundary, not the new 0.6.0
  wording or preview experience.

The redacted command transcript and exact validation boundary are in
[plugin-installation-validation-2026-08-30.md](plugin-installation-validation-2026-08-30.md).

## Deliberately not implemented

- A second coding model, coding-agent protocol, candidate-generation runtime, or background daemon.
- A PRman-owned Goal scheduler or persistence service; Goal state belongs to the active Codex task.
- PRman-owned Git worktrees, command sandbox, shell runner, GitHub client, GitHub App, or secrets.
- Parallel or unreviewed bulk issue outreach and PR creation, reviewer assignment, comments,
  approval, merge, auto-merge, or repository administration.
- Scorer training, dataset ingestion, model downloads, or model loading.
- A custom UI or hosted PRman service.

These actions stay with Codex and its connected tools, or are intentionally outside PRman's allowed
workflow.

The local helper cannot cryptographically prove who supplied a confirmation response, that Codex
actually displayed the packet unchanged, that GitHub or CI observations are true, or that an
`in_scope` assertion is semantically correct. It fails closed on the structured facts it receives;
Codex and the connected GitHub service remain the execution and observation boundary. The local
JSON artifacts are not signed and can be replaced by a process that already has write access to
them; they are workflow records, not a hostile-host security boundary.

## Remaining release work

- Run representative repository-discovery tasks and record target selection quality, duplicate-work
  avoidance, and refusal behavior.
- Install version 0.6.0 through the Plugin flow and verify the intake pause, PR-count, direction and
  Star questions, automatic Goal creation and resume behavior, sequential repetition, low-value
  refusal, adversarial-review loop, simple preview, hidden internal artifacts, and short
  `CREATE DRAFT PR OWNER/REPO` confirmation in fresh Codex tasks.
- Complete the live Draft PR and CI portion of the controlled
  [confirmation-path validation](confirmation-path-validation-2026-08-30.md). Local denial,
  stale-packet, Draft-only, and prohibited-operation checks now pass; the first GitHub write still
  requires the packet-bound user response.
- Exercise the missing-extra-score disclosure, fork, CI failure, repair-budget, and
  material-scope-change paths against controlled repositories.
- Integrate and calibrate one external production scorer and trusted evidence executor.
- Expand scorer conformance tests and adversarial false-ready and fabricated-evidence evaluation.
- Add a hash-locked, platform-specific dependency lockfile and reproducible runner image.

Until those checks are complete, PRman is a working Skill, workflow contract, and quality core, not
a validated autonomous production PR service.
