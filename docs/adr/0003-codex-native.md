# ADR 0003: Codex is the execution harness

- Status: accepted
- Date: 2026-08-28
- Updated: 2026-08-29

## Context

The initial prototype implemented its own coding-agent protocol, candidate pool, worktrees, command
sandbox, gates, and refinement loop. PRman is intended specifically for Codex, which already owns
repository reasoning, edits, command execution, orchestration, and approval surfaces.

The first published Skill narrowed PRman to assessment only. Product review established that the
useful boundary is broader: PRman should coordinate the whole contribution journey while still
reusing Codex for every action.

## Decision

PRman will be authored as a full pull-request orchestration Skill and distributed as a Plugin. The
Skill directs read-only repository discovery, target selection, local implementation, verification,
assessment, exact human confirmation, Draft PR creation, and bounded CI repair.

Codex remains the execution harness. PRman's Python code stays limited to deterministic assessment,
scorer adapters, aggregation, and fail-closed result policy. The Plugin declares the GitHub MCP
dependency but PRman does not implement or store a GitHub client or credential.

The Python package excludes the standalone agent, search engine, worktree manager, sandbox,
gate-runner, GitHub client, dataset, and training modules. Search and GitHub operations remain Codex
tool calls directed by the Skill rather than package-owned subsystems.

## Consequences

- Codex-native capabilities improve without a parallel PRman runtime falling behind.
- Users receive one coherent flow instead of having to manually connect search, coding, assessment,
  publication, and CI follow-up.
- The executable project remains small and auditable; PRman consumes evidence rather than executing
  repository checks itself.
- An exact post-implementation confirmation packet separates local work from GitHub write authority.
- Publication is Draft-only, CI repair is bounded, and material scope changes require reconfirmation.
- Evidence integrity remains a visible limitation and cannot be presented as cryptographic proof.
- The connected GitHub MCP service is a declared dependency, not a PRman-owned server.
