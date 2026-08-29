# Security policy

PRman is pre-alpha software. It does not contain GitHub credentials or a network mutation path, and
it must not be treated as an autonomous merge, deployment system, production PR gate, or execution
attestation service.

Do not report secrets, private repository content, raw scorer payloads, model weights, or training
data in a public issue. Report suspected leakage, scorer-contract bypass, hard-gate bypass, or
unauthorized write behavior through GitHub private vulnerability reporting once the repository
enables it. Until then, contact the maintainer privately.

A `ready` result is not a correctness proof or permission to write. The exact Draft PR mutation must
be confirmed by a human through Codex after the final diff and evidence are available.

External Python scorer entry points execute as fully trusted in-process code. The authenticated HTTP
adapter is the intended process boundary. Keep scorer-service and trusted-executor HMAC secrets in
their configured environment variables and never in repository JSON.

See [docs/threat-model.md](docs/threat-model.md) for boundaries and known limitations.
