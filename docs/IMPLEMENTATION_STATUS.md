# Implementation status

PRman `0.2.0` is a pre-alpha assessment-contract framework. The repository is public at
`primorLee/PRman` and licensed under Apache-2.0. It is not approved for production PR gating.

## Implemented

- Codex Plugin and focused `prman` Skill with progressive references.
- Duplicate-safe JSON parsing with a 4 MiB input limit.
- Assessment `1.1` bindings for repository ID, base commit, task text/digest, supplied diff, candidate
  digest, and candidate-specific typed evidence.
- Passing test evidence requires command, zero exit code, candidate ID, timestamp, producer/version,
  and log digest.
- Readiness requires a canonical assessment HMAC from the executor key fixed by the decision profile;
  missing or invalid evidence attestations cannot produce `ready`.
- Core-generated allowlisted scorer requests; arbitrary caller-provided criterion payloads were
  removed.
- Required blocking gates and non-blocking advisory gates, with actionable recoverable failures.
- Six-criterion canonical score order, geometric aggregation, absolute readiness LCB floor, minima,
  uncertainty/truncation limits, and comparison margin.
- OOD, excessively uncertain, and excessively truncated candidates excluded from comparison.
- Provider/model/calibrator metadata pinned for the whole assessment and bound to the decision
  profile.
- HMAC-authenticated numeric-loopback HTTP scoring with nonces, signed identity, proxy/redirect
  disabling, timeout, and request/response size caps.
- External Python scorer entry points classified as fully trusted in-process code and gated by an
  explicit CLI opt-in.
- Test-only provider identity derived in the core; fixture/static selections always force `abstain`.
- Scorer exceptions and malformed output converted to structured fail-closed results.
- Runtime/JSON-Schema consistency tests, schema positive and negative cases, type checking, branch
  coverage threshold, HTTP signature tests, and wheel/sdist CI checks.
- Fixed output policy: human confirmation required, Draft-only, no external write authorized.

The archived review that motivated this hardening is
[`security-review-2026-08-29.md`](security-review-2026-08-29.md).

## Deliberately not implemented

- Coding-agent or candidate-generation abstraction.
- Git worktree orchestration.
- Podman or other command sandbox.
- Repository test, lint, type-check, or security command runner.
- Scorer training, dataset ingestion, model downloads, or model loading.
- GitHub credentials, GitHub App, branch push, issue mutation, or pull-request creation.
- MCP server or custom UI.

Codex provides repository execution and existing GitHub tools. An MCP scorer should be added only if
a future deployed scorer requires a shared tool interface.

## Known limitations and remaining release work

- No production scorer or trusted evidence executor is configured or shipped. The checked-in research
  decision profile has both `scorer_binding: null` and `evidence_attestation: null`, so it cannot
  produce a production readiness claim.
- Thresholds are research defaults and are not calibrated for production use.
- Evidence attestation authenticates possession of the configured executor key, not whether the
  executor truthfully ran a command or observed the claimed repository state.
- HMAC authenticates the local scorer service key, not model execution or host integrity.
- Trusted Python scorers have full in-process privileges and no enforceable timeout; untrusted
  scorers require an externally restricted service/container.
- Adversarial false-ready evaluation, scorer conformance certification, external calibration,
  representative clean-task plugin installation, and end-to-end Draft PR confirmation testing remain
  required before any production-gate claim.
- Action dependencies are exactly pinned and the supported Python range matches CI, but the project
  still lacks a hash-locked, platform-specific dependency lockfile and reproducible runner image.
