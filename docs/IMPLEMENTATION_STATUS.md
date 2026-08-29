# Implementation status

PRman 0.3.0 is a pre-alpha, end-to-end Draft PR orchestration Skill for Codex. The repository is
public at primorLee/PRman and licensed under Apache-2.0. The workflow is implemented in the Skill and
its contracts; clean-install and live GitHub end-to-end validation are still required before a
release claim.

## Implemented workflow

- Installable Codex Plugin and implicitly discoverable prman Skill.
- GitHub MCP dependency declared in the Skill metadata; no PRman-owned token or credential store.
- Read-only repository and issue discovery, small-target comparison, contribution-fit selection,
  duplicate-work checks, and anti-spam rules.
- Inspection of agent instructions, README, contribution and security policies, license, issue
  context, pull-request template, default branch, full base commit, and CI configuration.
- Codex-native local implementation and execution of repository-prescribed verification.
- Existing deterministic assessment after the final diff, with two revision rounds by default.
- Exact confirmation packet covering repository, task, branch and fork route, base commit, diff,
  verification, assessment, Draft PR text, all writes, and CI repair budget.
- Explicit treatment of ready, revise, and abstain. Missing production scoring can never be
  represented as ready, although a user may acknowledge the uncertainty and still confirm a Draft
  PR.
- Draft-only GitHub publication after confirmation, using Codex's connected GitHub tools.
- Default maximum of two same-scope CI repair rounds, with new verification and assessment after
  each edit.
- New confirmation required for a stale packet or material scope change.
- Hard prohibitions on default-branch writes, force-push, merge, auto-merge, marking ready for
  review, bulk PRs, and public vulnerability disclosure.

The machine-readable confirmation shape is
schemas/confirmation_packet.schema.json, with an example in
examples/confirmation-packet.json.

## Implemented quality core

- Duplicate-safe JSON parsing with a 4 MiB input limit.
- Assessment 1.1 bindings for repository ID, base commit, task text and digest, supplied diff,
  candidate digest, and candidate-specific typed evidence.
- Passing test evidence requires command, zero exit code, candidate ID, timestamp,
  producer/version, and log digest.
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

The archived review that motivated the assessment hardening is
[security-review-2026-08-29.md](security-review-2026-08-29.md).

## Deliberately not implemented

- A second coding model, coding-agent protocol, candidate-generation runtime, or background daemon.
- PRman-owned Git worktrees, command sandbox, shell runner, GitHub client, GitHub App, or secrets.
- Bulk issue outreach, bulk PR creation, reviewer assignment, comments, approval, merge, auto-merge,
  or repository administration.
- Scorer training, dataset ingestion, model downloads, or model loading.
- A custom UI or hosted PRman service.

These actions stay with Codex and its connected tools, or are intentionally outside PRman's allowed
workflow.

## Remaining release work

- Install or update the Plugin in a clean Codex environment and verify explicit and implicit
  invocation.
- Run representative repository-discovery tasks and record target selection quality, duplicate-work
  avoidance, and refusal behavior.
- Exercise the exact confirmation, denial, stale-packet, abstain-acknowledgement, fork, Draft PR, CI
  success, CI failure, repair-budget, and material-scope-change paths against controlled repositories.
- Integrate and calibrate one external production scorer and trusted evidence executor.
- Publish scorer conformance tests and adversarial false-ready and fabricated-evidence evaluation.
- Add a hash-locked, platform-specific dependency lockfile and reproducible runner image.

Until those checks are complete, PRman is a working workflow contract and quality core, not a
validated autonomous production PR service.
