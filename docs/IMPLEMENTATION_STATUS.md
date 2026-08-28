# Implementation status

## Implemented

- Codex Plugin and `prman` Skill scaffolding.
- Official Skill and Plugin structural validation.
- Progressive Skill references for assessment, scorer integration, and write safety.
- Strict duplicate-safe JSON parsing and content digests.
- Required hard gates with fail-closed missing and unknown states.
- Six-criterion score validation, geometric aggregation, uncertainty LCB, minima, and margin.
- `single` and `compare` assessment modes.
- Replaceable Python scorer entry points.
- Loopback-only local HTTP scorer adapter.
- Test-only fixture and static scorer enforcement.
- CLI and bundled Skill wrapper.
- Distribution, CLI, scorer, decision, and safety tests.

## Deliberately not implemented

- Coding-agent or candidate-generation abstraction.
- Git worktree orchestration.
- Podman or other command sandbox.
- Test, lint, type-check, or security command runner.
- Scorer training, dataset ingestion, model downloads, or model loading.
- GitHub credentials, GitHub App, branch push, issue mutation, or pull-request creation.
- MCP server or custom UI.

Codex provides repository execution and existing GitHub tools. An MCP scorer should be added only if
a future deployed scorer requires a shared tool interface.

## Known limitations

- The helper validates supplied gate evidence but cannot prove Codex actually ran a command. Users
  should inspect command output for high-risk changes.
- No production scorer is configured, so ordinary local assessment correctly returns `abstain`.
- Thresholds are research defaults and are not claimed to be calibrated for production use.
- Plugin marketplace installation and representative new-task testing remain to be completed.
- Repository visibility and license are undecided; no Git remote exists.
