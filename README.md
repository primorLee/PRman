# PRman

PRman is a Codex-native plugin for evidence-backed code-change decisions. Codex performs the coding
work; PRman supplies a reusable workflow, an optional replaceable scorer boundary, and deterministic
`ready / revise / abstain` aggregation.

PRman does **not** implement a second coding agent, candidate generator, worktree manager, command
sandbox, or GitHub client. Those responsibilities stay with Codex and its existing tools.

## Shape of the project

```text
Issue or current change
        |
        v
Codex: inspect, edit, run project commands, collect evidence
        |
        v
$prman skill: prepare a strict assessment
        |
        +--> optional scorer provider: six calibrated criteria
        |
        v
Deterministic core: hard gates + geometric score + uncertainty LCB
        |
        v
ready / revise / abstain
        |
        v
Human confirmation before any Draft PR write
```

The Skill is the workflow authoring format. The Plugin manifest makes that workflow installable and
shareable. This follows the official OpenAI documentation for
[building skills](https://learn.chatgpt.com/docs/build-skills) and
[building plugins](https://learn.chatgpt.com/docs/build-plugins).

## What is implemented

- Installable plugin manifest at `.codex-plugin/plugin.json`.
- Focused `prman` Skill with progressive assessment, scorer, and safety references.
- Strict JSON contracts for assessments, scorer requests, score bundles, and results.
- Required evidence gates that cannot be overridden by a scorer.
- Six-dimensional weighted geometric aggregation with uncertainty lower confidence bounds.
- Single-change readiness and optional comparison-margin decisions.
- Replaceable Python entry-point scorers and a loopback-only local HTTP adapter.
- Test-only fixture/static scorers that require an explicit CLI opt-in.
- Fixed output policy: human confirmation required, Draft-only, no external write authorized.

No scorer has been trained or downloaded. PRman itself does not create a GitHub issue, branch, or
pull request as part of an assessment.

## Development

PRman requires Python 3.11 or newer and has no runtime dependencies.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make check PYTHON=python
make demo PYTHON=python
```

The demo uses an explicitly marked fixture scorer, emits `"test_only": true`, and must not be used
as a real readiness claim.
For a fail-closed run without any scorer:

```bash
python skills/prman/scripts/assess.py \
  --input examples/assessment.json
```

That run returns `abstain` with `scorer_unavailable` after the supplied hard gates pass.

## Using the Skill

After installing the plugin through a supported Codex plugin source, invoke it explicitly:

```text
Use $prman to implement this issue, verify the change, and assess whether it is ready for a Draft PR.
```

Codex may also select the Skill implicitly when a request matches its description. During local
plugin development, follow the official [plugin usage guide](https://learn.chatgpt.com/docs/plugins).

The Skill prepares an assessment in temporary storage and calls its bundled helper. The helper only
consumes supplied evidence. It never runs project commands or modifies the target repository.

## Scorer boundary

The production scorer is intentionally replaceable. An external Python distribution may register a
factory under the `prman.scorers` entry-point group, or a separately deployed scorer may use
`builtin.local-http` on a numeric loopback address. Both implement
`prman-scorer-plugin/1.0`.

Without a configured production scorer, PRman abstains. `builtin.static` and
`builtin.fixture-json` are only for contract and smoke tests. See
[docs/scorer-protocol.md](docs/scorer-protocol.md).

## Safety meaning

`ready` means only that supplied gates, configured thresholds, and scorer checks passed. It is not a
correctness proof, merge recommendation, or write authorization. PRman requires an exact human
confirmation before Codex uses an existing GitHub tool, and only a Draft PR is in scope.

See [docs/architecture.md](docs/architecture.md),
[docs/threat-model.md](docs/threat-model.md), and
[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

## Repository map

- `.codex-plugin/`: installable plugin metadata.
- `skills/prman/`: Codex workflow, references, and bundled helper.
- `src/prman/`: deterministic assessment library and scorer adapters.
- `configs/`: decision thresholds and scorer configuration examples.
- `schemas/`: public JSON contracts.
- `examples/`: fixture-only smoke input and scorer output.
- `tests/core/`: unit, safety, distribution, CLI, and Skill-wrapper tests.

## License and repository

PRman is available under the [Apache License 2.0](LICENSE). The canonical repository is
[`primorLee/PRman`](https://github.com/primorLee/PRman).
