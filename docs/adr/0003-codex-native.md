# ADR 0003: Codex is the execution harness

- Status: accepted
- Date: 2026-08-28

## Context

The initial prototype implemented its own coding-agent protocol, candidate pool, worktrees, command
sandbox, gates, and refinement loop. PRman is intended specifically for Codex, which already owns
repository reasoning, edits, command execution, orchestration, and approval surfaces.

## Decision

PRman will be authored as a focused Skill and distributed as a Plugin. Its executable code is limited
to deterministic assessment, scorer adapters, aggregation, and fail-closed result policy.

The published package excludes the standalone agent, search, worktree, sandbox, gate-runner, dataset,
and training modules. The local uncommitted prototype is retained outside the publication set for
provenance until the repository history is established.

## Consequences

- Codex-native capabilities improve without a parallel PRman runtime falling behind.
- The project becomes smaller and easier to install, audit, and test.
- PRman consumes evidence rather than executing repository checks itself.
- Evidence integrity remains a visible limitation and cannot be presented as cryptographic proof.
- A future MCP server is optional and requires a concrete shared-service need.
