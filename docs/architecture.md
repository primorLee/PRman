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
- prepare strict scorer payloads without future outcome or identity leakage;
- apply bounded revision;
- interpret `ready`, `revise`, and `abstain` conservatively;
- require explicit confirmation for the exact Draft PR write.

Conditional details live in Skill references so ordinary Codex context remains small.

### Deterministic assessment core

The Python helper validates JSON, enforces required gates, calls a configured scorer, validates the
response, and aggregates it. It deliberately has no repository command runner and no GitHub client.
Its runtime uses only the Python standard library.

The default required gates are `scope`, `secrets`, and `tests`. A missing or unknown required gate
forces `abstain`. A non-recoverable failure forces `abstain`; a recoverable failure may produce
`revise`. Scorer output is considered only after every gate passes.

### Scorer provider

The scorer is an optional replacement boundary. It may be a Python entry point or a local HTTP
service. Provider identity, model revision, calibrator revision, request digest, criteria coverage,
probabilities, uncertainty, and out-of-distribution state are all validated.

No MCP server is bundled today because PRman has no shared external service or account connection.
An MCP tool can be added later if a deployed scorer genuinely benefits from that interface; it is
not required merely to make PRman a Codex plugin.

## Data flow

1. Codex obtains the exact diff and computes its SHA-256 candidate ID.
2. Codex records gate results with observed commands or inspection evidence.
3. If a production scorer exists, Codex builds one criterion-specific payload for each of the six
   criteria.
4. The helper rejects malformed data and any future outcome or identity fields.
5. Hard gates run logically before scoring.
6. Scores are combined with a weighted geometric mean and uncertainty LCB.
7. Single mode may return `ready` for one eligible change. Compare mode also requires a configured
   top-candidate LCB margin.
8. The result always denies implicit external-write authority.

## Package boundary

Only `prman` and `prman.scorers` are included in the Python distribution. The pre-Codex standalone
prototype is retained locally for provenance but excluded from the package and future Git commit.
This makes the published code path unambiguous without irreversibly deleting an uncommitted archive.
