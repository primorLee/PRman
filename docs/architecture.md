# Codex-native architecture

## Decision

PRman is a Skill-first Codex extension distributed as a Plugin. Codex remains the only coding and
execution harness.

This boundary removes the former need for PRman-owned coding-agent protocols, candidate-generation
loops, Git worktrees, command sandboxes, or GitHub credentials. It also lets PRman evolve with Codex
instead of duplicating its runtime.

## Components

### Codex execution layer

Codex interprets the request, reads repository instructions, edits code when authorized, runs the
project's commands, and gathers exact evidence. Native Codex features may be used for alternative
approaches when appropriate, but PRman does not wrap or reimplement them.

### PRman Skill

`skills/prman/SKILL.md` defines the non-obvious workflow:

- distinguish review, implementation, and external-write authority;
- collect observed hard-gate evidence;
- prepare bound assessment context from pre-review sources for a core-generated scorer request;
- apply bounded revision;
- interpret `ready`, `revise`, and `abstain` conservatively;
- require explicit confirmation for the exact Draft PR write.

Conditional details live in Skill references so ordinary Codex context remains small.

### Deterministic assessment core

The Python helper validates JSON, binds the shared repository/base/task context, recomputes each
candidate ID from the supplied diff, enforces typed gate evidence, generates a strict scorer request,
calls a configured scorer, validates the response, and aggregates it. It deliberately has no
repository command runner and no GitHub client. Its runtime uses only the Python standard library.

The default required gates are `scope`, `secrets`, and `tests`. A missing or unknown required gate
forces `abstain`. A non-recoverable failure forces `abstain`; a recoverable failure with actionable
advice may produce `revise`. Extra gates are advisory. Scorer output is considered only after every
required gate passes.

### Scorer provider

The preferred scorer boundary is an HMAC-authenticated local HTTP service. Provider identity, model
revision, calibrator revision, nonce, request digest, criteria order, probabilities, uncertainty, and
out-of-distribution state are validated, and the decision profile independently binds exact provider
metadata. A Python entry point is also supported only as fully trusted in-process code with an
explicit CLI opt-in; it is not an isolation boundary.

No MCP server is bundled today because PRman has no shared external service or account connection.
An MCP tool can be added later if a deployed scorer genuinely benefits from that interface; it is
not required merely to make PRman a Codex plugin.

## Data flow

1. Codex obtains the exact UTF-8 diff, computes its SHA-256 candidate ID, and records one shared
   repository ID, base commit, and task digest.
2. Codex records typed gate evidence containing the candidate ID, time, producer/version, log digest,
   and command/exit code when applicable.
3. The helper recomputes content bindings and rejects malformed or cross-candidate evidence.
4. Required hard gates run logically before scoring; additional gates are advisory.
5. The helper generates an allowlisted scorer request from the shared context, diff, and evidence
   projection.
6. Scores are combined with a weighted geometric mean and uncertainty LCB. Eligibility requires the
   raw score and an absolute LCB floor.
7. Single mode may return `ready` for one eligible production-scored change. Compare mode requires a
   top-candidate margin over a second non-OOD comparable candidate under pinned metadata.
8. Final readiness requires a canonical assessment HMAC from the executor key fixed by the decision
   profile. Missing or invalid attestation forces `abstain` without blocking useful revision advice.
9. Test-only scorers always force `abstain`; provider failures produce structured abstentions.
10. The result always denies implicit external-write authority.

## Package boundary

Only `prman` and `prman.scorers` are included in the Python distribution. The pre-Codex standalone
prototype is retained locally for provenance but excluded from the package and future Git commit.
This makes the published code path unambiguous without irreversibly deleting an uncommitted archive.
