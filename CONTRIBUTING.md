# Contributing

PRman is a Codex-native Skill and Plugin with a small deterministic Python core. Contributions should
preserve that boundary.

Use Python 3.11 or newer. Before proposing a change, run:

```bash
python -m pip install -e '.[dev]'
make check PYTHON=python
make demo PYTHON=python
```

For Skill or Plugin metadata changes, also run the current official `skill-creator` and
`plugin-creator` validators in Codex.

Keep these invariants:

- do not add a coding-agent, candidate-generation, worktree, command-sandbox, or GitHub harness;
- do not infer a passing gate when evidence is missing or a command was skipped;
- never let scorer output override a hard gate;
- keep fixture and static scorers test-only;
- reject future outcome and identity leakage in scorer input;
- keep `ready` separate from human confirmation and external-write authority;
- do not add model weights, raw training data, secrets, or private repository payloads;
- keep training and model-serving dependencies outside the core package.

New behavior should have focused tests under `tests/core/`. Update the relevant Skill reference and
threat model when a change affects authorization, scorer boundaries, evidence, or result semantics.
