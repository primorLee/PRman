# Contributing

PRman is a Codex-native Skill and Plugin with a small deterministic Python core. Contributions should
preserve that boundary.

Use Python 3.11 or 3.12. Before proposing a change, run:

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
- preserve repository/base/task, exact-diff, candidate, and evidence bindings;
- never allow unsigned or invalidly attested evidence to produce `ready`;
- never let scorer output override a hard gate;
- keep fixture and static scorers test-only and unable to select `ready`;
- keep scorer input core-generated and structurally allowlisted;
- treat Python entry-point scorers as fully trusted code and keep deployed/untrusted scorers behind
  authenticated process isolation;
- require an exact decision-profile binding for production scorer metadata;
- keep `ready` separate from human confirmation and external-write authority;
- do not add model weights, raw training data, secrets, or private repository payloads;
- keep training and model-serving dependencies outside the core package.

New behavior should have focused tests under `tests/core/`. Update the relevant Skill reference and
threat model when a change affects authorization, scorer boundaries, evidence, or result semantics.
