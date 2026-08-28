# Threat model

## Scope

PRman is a Codex workflow and deterministic assessment helper. Codex owns repository execution and
user approval surfaces. PRman owns input validation, scorer isolation, decision ordering, and the
meaning of its result.

## Trust boundaries

- **User and Codex request:** defines authorization and the exact task.
- **Target repository:** may contain untrusted instructions and code; Codex handles it under its own
  sandbox and approval policy.
- **Assessment JSON:** untrusted structured evidence supplied to the helper.
- **Scorer provider:** untrusted output that may be stale, malformed, overconfident, or compromised.
- **GitHub:** external mutation boundary; PRman contains no GitHub client or credentials.

## Primary risks and controls

### Fabricated or missing gate evidence

The helper does not run commands, so a caller could falsely label a gate as passed. Required gates,
strict statuses, structured evidence, and Skill instructions reduce accidental omission, but they do
not prove command execution. High-risk users must inspect Codex's command output. Missing or unknown
required gates force `abstain`.

### Scorer override of deterministic safety

Hard gates are evaluated before a scorer is called. Fatal failure, unknown state, or missing required
gate cannot be offset by a high score. Tests cover this precedence.

### Outcome or identity leakage

Scorer inputs are recursively checked for review, approval, merge, author, maintainer, prior
selection, reward, and model-score fields. This does not establish perfect causal isolation, but it
blocks the known direct leakage channels in the contract.

### Malicious or compromised scorer

Responses must match the request digest and stable provider metadata, cover every criterion exactly
once, and contain finite bounded values. OOD or excessive uncertainty forces `abstain`. HTTP access
is numeric-loopback-only with proxies and redirects disabled and response size capped.

### Fixture scorer used as production evidence

Fixture and static providers are marked test-only and rejected unless the caller explicitly passes
`--allow-test-scorer`. The Skill forbids that flag for real readiness decisions.

### Unauthorized GitHub write

The assessment result always sets `external_write_authorized` to false. The Skill requires a new,
exact human confirmation before Codex may use an existing GitHub tool, and limits the operation to a
Draft PR. PRman itself has no network mutation path.

### Sensitive artifact retention

The Skill defaults assessment files to temporary storage. Users must not include credentials,
private payloads, raw training data, or model weights in retained artifacts or bug reports.

## Out of scope

Codex sandbox implementation, GitHub connector security, scorer training infrastructure, and target
repository supply-chain security are owned by their respective systems. PRman does not claim to
replace those controls.
