# Threat model

## Scope

PRman is a Codex workflow plus a deterministic assessment helper. It coordinates repository
discovery, local implementation, quality evaluation, exact human confirmation, Draft PR creation,
and bounded CI follow-up. Codex owns execution, sandboxing, approval surfaces, credentials, and the
connected GitHub tools.

PRman is pre-alpha research software. It is not a production PR gate, execution-attestation system,
merge controller, security sandbox, background bot, or credential manager.

## Trust boundaries

- **User request:** defines the goal and local-work scope. It does not authorize a later GitHub write
  until the exact confirmation packet is shown and confirmed.
- **Target repository:** its code, issues, and instructions are untrusted input. Codex handles them
  under its own sandbox and approval policy.
- **Codex execution layer:** reads, edits, runs commands, and calls GitHub tools. PRman relies on
  Codex to enforce its platform boundaries and truthfully report observations.
- **Assessment JSON:** untrusted structured claims. Repository, base commit, task, diff, candidate,
  and evidence bindings are validated. Production ready additionally requires an HMAC from the
  executor key fixed by the trusted decision profile.
- **Scorer boundary:** the preferred scorer is an authenticated loopback service. Its judgment
  remains fallible. A Python entry-point scorer is fully trusted in-process code.
- **Confirmation packet:** the sole PRman workflow boundary that can authorize the listed external
  writes. It is bound to an exact target, base, branch route, diff, verification, PR text, write
  list, and CI budget.
- **Connected GitHub service:** performs external mutations using credentials managed by Codex, not
  by PRman.

## Primary risks and controls

### Malicious repository instructions

Repository content can attempt prompt injection, request secrets, broaden the task, or redirect
writes. PRman tells Codex to apply relevant repository instructions without treating them as user
authority. Repository text cannot waive the confirmation packet, reveal credentials, change the
selected repository, or enable forbidden GitHub operations.

Security-adjacent work must check SECURITY before implementation. A suspected vulnerability is never
turned into a public issue or PR when the project provides a private disclosure route.

### Spam, duplicate work, or unsuitable targets

Automated discovery can create low-value or duplicate contributions. PRman searches read-only,
compares at most three plausible targets, and chooses one. It prefers clear open issues,
maintainer-requested work, recent activity, visible contribution rules, and concrete verification.
It checks assignment and existing pull requests and rejects batch outreach, speculative drive-by
changes, abandoned targets, and cosmetic churn presented as substantive work.

### Fabricated or stale gate evidence

Every assessment shares one hashed repository identity, base commit, and task digest. Each candidate
contains the actual UTF-8 diff, and the helper recomputes its SHA-256 candidate ID. Every gate uses a
strict evidence record containing the candidate ID, timestamp, producer and version, summary, log
digest, and command and exit code when applicable. A passing tests gate requires command evidence
with exit code zero.

These controls prevent accidental cross-candidate reuse and make stale evidence detectable after a
diff change. A production ready additionally requires HMAC-SHA256 evidence attestation over the
canonical shared context, diffs, and full gate records. The decision profile fixes the key ID and
secret environment-variable name; absent, mismatched, weak, or invalid attestations force
abstention.

The HMAC proves possession of the configured executor key and protects the signed content. It does
not prove a command ran, the executor was honest, or the repository identity was observed correctly.

### Scorer override of deterministic safety

Only configured required gates are blocking; extra gates are advisory. Missing, unknown, or fatal
required gates are evaluated before the scorer and cannot be offset by a high score. Recoverable
required-gate failures require actionable advice. Ready also requires raw score, criterion minima,
uncertainty and truncation limits, an absolute lower-confidence-bound floor, pinned provider
metadata, and verified attestation.

### Outcome or identity leakage

The core generates scorer requests from an allowlist: repository, base, task, diff, canonical
criteria, and a small observed-evidence projection. Extra structured fields are rejected by runtime
parsing and JSON Schema.

Task text, repository rules, diff text, and evidence summaries remain raw-text fields. PRman cannot
prove callers did not embed review outcomes or sensitive content in them. The Skill therefore
requires pre-review sources and forbids credentials, private payloads, or review/merge metadata in
scorer input.

### Malicious or compromised scorer

The recommended HTTP provider disables proxies and redirects, requires a numeric loopback address,
limits request and response size, and imposes a timeout. Each request carries a random nonce and an
HMAC-SHA256 signature. Each response must repeat the nonce, request digest, and exact
provider/model/calibrator metadata under a domain-separated signature. The decision profile
independently binds the same metadata.

Signed output is still an untrusted quality judgment. Responses must cover all criteria in canonical
order with finite bounded values. OOD, excessive uncertainty, or excessive truncation makes a
candidate non-comparable and forces abstention. Provider failures become structured
scorer_unavailable abstentions without exception-text leakage.

External Python scorer entry points run with full PRman-process authority and no enforced timeout.
The CLI requires explicit trusted-provider opt-in. Put untrusted or production scoring behind a
separately restricted service or container.

### Fixture scorer used as production evidence

Fixture and static providers are identified in the core and rejected by the CLI unless the caller
passes the test-only opt-in. Regardless of API path, their final selection is forced to abstain with
test_only true.

### Stale or ambiguous write confirmation

The assessment result always sets external_write_authorized false. Before any GitHub mutation, the
Skill prepares the exact packet, presents a plain-language contribution preview, and stops. A short
affirmative response such as yes or confirm is never sufficient. The response must exactly match
`CREATE DRAFT PR OWNER/REPO`. The unchanged internal packet binds the base, branch route, diff, PR
text, writes, assessment, and CI budget. Any non-ready reason is disclosed in the preview in plain
language. Leading or trailing whitespace is not normalized.

Changing the repository, base commit, branch route, initial diff, PR title or body, operation list,
or CI budget before publication invalidates confirmation. After publication, only a repair within
the confirmed CI envelope may change the diff without a new packet. A missing, denied, ambiguous,
or stale response terminates with a local handoff. The permitted operation is Draft-only; a tool
that cannot guarantee Draft state must not create a normal PR.

### CI repair scope creep

CI authorization is limited to the same task, branch, Draft PR, and default two repair rounds.
Every repair receives a new digest, verification, and assessment. Dependency additions, public API
changes, broad refactors, security-posture changes, issue or repository changes, and review
responses require a new packet and confirmation. History rewriting and force-push are forbidden.

### Sensitive artifact retention

Assessment files default to temporary storage. Users must not include credentials, private
payloads, raw training data, or model weights in retained artifacts or bug reports. HMAC
configuration contains environment-variable names only; secret values must never enter a checked-in
config, packet, or assessment. PRman never asks for or stores a GitHub token.

## Residual limitations

- No production scorer, trusted evidence executor, or calibrated production decision profile is
  shipped. The default profile cannot produce a production readiness claim.
- Evidence HMAC authenticates the configured executor key, not command truth, sandbox integrity, or
  host identity. A compromised executor can sign false claims.
- Scorer HMAC authenticates a service key, not model behavior, training provenance, or host
  integrity.
- Skill instructions and schemas can constrain intended behavior but do not replace Codex platform
  enforcement or a live end-to-end security test.
- The local authorization and workflow artifacts are not signed user-identity attestations. The
  helper cannot prove that the user supplied the response, that the unchanged packet was displayed,
  that reported assessment, GitHub, or CI facts are truthful, or that an `in_scope` claim is
  semantically true. A process with write access to the JSON state can replace it; these artifacts
  are workflow records rather than a hostile-host enforcement boundary.
- GitHub connector security, account permissions, fork policy, CLA enforcement, target-repository
  supply-chain risk, and CI infrastructure remain owned by their respective systems.
- Fresh-task Plugin installation, representative public-repository execution, denial-path testing,
  and full Draft PR plus CI testing remain release requirements.
