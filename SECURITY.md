# Security policy

PRman is pre-alpha software. It does not contain GitHub credentials or a network mutation path, and
it must not be treated as an autonomous merge or deployment system.

Do not report secrets, private repository content, raw scorer payloads, model weights, or training
data in a public issue. Report suspected leakage, scorer-contract bypass, hard-gate bypass, or
unauthorized write behavior through GitHub private vulnerability reporting once the repository
enables it. Until then, contact the maintainer privately.

A `ready` result is not a correctness proof or permission to write. The exact Draft PR mutation must
be confirmed by a human through Codex after the final diff and evidence are available.

See [docs/threat-model.md](docs/threat-model.md) for boundaries and known limitations.
