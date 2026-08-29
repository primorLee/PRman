# Threat model

## Scope

PRman is a Codex workflow and deterministic assessment helper. Codex owns repository execution and
user approval surfaces. PRman owns strict input validation, content binding, deterministic decision
ordering, authenticated communication with its loopback scorer, and the meaning of its result.

PRman is pre-alpha research software. It is not a production PR gate, execution-attestation system,
merge controller, or security sandbox.

## Trust boundaries

- **User and Codex request:** defines authorization and the exact task.
- **Target repository:** may contain untrusted instructions and code; Codex handles it under its own
  sandbox and approval policy.
- **Assessment JSON:** untrusted structured claims supplied to the helper. Its repository ID, base
  commit, task, diff, and evidence are content-bound and cross-checked. A readiness claim additionally
  requires an HMAC from the executor key fixed by the trusted decision profile.
- **Authenticated loopback scorer:** runs outside the helper process. Its output remains fallible and
  may be stale, malformed, overconfident, OOD, or compromised. Possession of the configured HMAC key
  authenticates the service response, not the correctness of the underlying model.
- **Python entry-point scorer:** fully trusted code executing inside the PRman process. It is not an
  untrusted boundary and receives no filesystem, environment, network, time, or memory isolation
  from PRman.
- **GitHub:** external mutation boundary; PRman contains no GitHub client or credentials.

## Primary risks and controls

### Fabricated or stale gate evidence

Every assessment shares one hashed repository identity, base commit, and task digest. Each candidate
contains the actual UTF-8 diff, and the helper recomputes its SHA-256 candidate ID. Every gate uses a
strict evidence record containing the candidate ID, timestamp, producer and version, summary, log
digest, and command/exit code when applicable. A passing `tests` gate specifically requires command
evidence with exit code zero.

These controls prevent accidental cross-candidate reuse and make stale evidence detectable when the
diff changes. A production `ready` additionally requires `hmac-sha256` evidence attestation over the
canonical shared context, every diff, and every full gate record. The decision profile fixes the key
ID and secret environment-variable name; absent, mismatched, weak, or invalid attestations force
abstention at the final readiness boundary.

The HMAC proves possession of the configured executor key and protects the signed content. It does
not itself prove a command ran or that the executor observed the correct repository. The key and
decision profile must be controlled by a trusted execution layer rather than the assessment caller.

### Scorer override of deterministic safety

Only configured required gates are blocking; extra gates are advisory. Missing, unknown, or fatal
required gates are evaluated before a scorer is called and cannot be offset by a high score.
Recoverable required-gate failures require actionable advice. `ready` additionally requires the raw
score, criterion minima, uncertainty limit, context limit, and absolute `ready_lcb_min`.

### Outcome or identity leakage

Callers no longer provide arbitrary criterion payloads. The core generates a scorer request from a
strict allowlist: shared repository/base/task fields, the candidate diff, canonical criteria, and a
small observed-evidence projection. Extra structured fields are rejected by both runtime parsing and
JSON Schema.

Task text, repository rules, diff text, and evidence summaries are explicitly sourced raw-text
fields. PRman cannot semantically determine whether a caller embedded review metadata in those
strings. The Skill therefore requires them to come from the pre-review task, repository, diff, and
observations rather than review or merge systems.

### Malicious or compromised scorer

The recommended loopback HTTP provider disables proxies and redirects, requires a numeric loopback
address, imposes a timeout, and limits the input file, service request, and service response to 4
MiB. Each request carries a random nonce and an HMAC-SHA256 signature. A response must carry a valid
domain-separated signature and repeat the nonce, request digest, and exact provider/model/calibrator
metadata. The decision profile must independently bind that exact metadata.

Signed output is still untrusted as a quality judgment. Responses must cover all criteria in
canonical order with finite bounded values. OOD, excessive uncertainty, or excessive truncation
makes a candidate non-comparable and forces abstention. Provider exceptions and malformed output are
converted to structured `scorer_unavailable:*` abstentions without returning exception text.

An external Python entry point is different: loading it grants arbitrary in-process code execution.
The CLI requires `--allow-trusted-python-scorer` before load. Use this only for code already trusted
as much as PRman itself. Put an untrusted or production scorer behind a separately sandboxed service
or container; PRman does not create that sandbox.

### Fixture scorer used as production evidence

Fixture and static providers are identified by their provider IDs in the core and rejected by the
CLI unless the caller explicitly passes `--allow-test-scorer`. Regardless of how the Python API is
called, their final selection is always forced to `abstain` with `test_only: true`.

### Unauthorized GitHub write

The assessment result always sets `external_write_authorized` to false. The Skill requires a new,
exact human confirmation before Codex may use an existing GitHub tool, and limits the operation to a
Draft PR. PRman itself has no network mutation path.

### Sensitive artifact retention

The Skill defaults assessment files to temporary storage. Users must not include credentials,
private payloads, raw training data, or model weights in retained artifacts or bug reports. Both HMAC
configurations contain only environment-variable names; secret values must never enter a checked-in
config or assessment.

## Residual limitations

- No production scorer, trusted evidence executor, or calibrated production decision profile is
  shipped. The default profile has both `scorer_binding: null` and `evidence_attestation: null`, so a
  production readiness result is impossible without explicit matching configuration and signatures.
- Evidence HMAC authenticates the configured executor key, not command truth, sandbox integrity, or
  repository identity. A compromised executor can sign false claims.
- HMAC authenticates possession of a local service key, not model behavior, training provenance, or
  host integrity.
- In-process Python scorers have full process authority and no enforced timeout.
- Codex sandbox implementation, scorer service/container hardening, GitHub connector security,
  scorer training, and target-repository supply-chain security remain owned by their respective
  systems.
