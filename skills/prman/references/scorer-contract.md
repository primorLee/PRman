# Scorer contract

Read this reference only when configuring, implementing, or diagnosing a scorer.

PRman uses protocol `prman-scorer-plugin/1.1`. The core generates an allowlisted request containing
one bound repository/base/task context, the exact candidate diff, a narrow observed-evidence
projection, and these canonical criteria:

1. `correctness`
2. `task_alignment`
3. `scope`
4. `repository_conventions`
5. `maintainability`
6. `reviewer_effort`

Every score contains a probability and uncertainty in `[0, 1]`, non-empty evidence strings, optional
actionable critique, and an out-of-distribution flag. Responses repeat the candidate and request
digests and must return each criterion exactly once in canonical order. Metadata is pinned across the
whole assessment.

## Production configuration

Prefer `builtin.local-http`. It accepts numeric loopback HTTP only, disables proxies and redirects,
limits time and body sizes, and requires `hmac_secret_env` naming an environment variable containing
at least 32 secret bytes. The request and response use separate domain-separated HMAC-SHA256
signatures; the response repeats a random nonce, request digest, and signed provider metadata.

Set the decision config's `scorer_binding` to the exact provider ID/version, model revision,
calibrator version, and `prman-scorer-plugin/1.1` protocol. A missing or mismatched binding produces a
structured abstention. Production readiness separately requires the trusted-executor
`evidence_attestation` described in `references/assessment-contract.md`. Never put either HMAC secret
itself in a JSON config or artifact. See
`docs/scorer-protocol.md` in the plugin root for the exact wire envelope and signing bytes.

## Trusted Python entry points

Third-party packages may register factories under `prman.scorers`, but they run inside PRman with
full process privileges and no enforced timeout. They are not an untrusted boundary. The CLI refuses
to load one unless `--allow-trusted-python-scorer` is supplied. Use this only when the package is
trusted as much as PRman; otherwise place the scorer in a restricted external service/container.

## Failure behavior

PRman converts ordinary provider exceptions, malformed return types, changed metadata, stale
digests, invalid signatures, and invalid score data into a structured `scorer_unavailable:*`
abstention without returning exception messages. OOD, excessive uncertainty, and excessive context
truncation force abstention and make a candidate ineligible as a comparison runner-up.

`builtin.static` and `builtin.fixture-json` are test-only. The CLI requires
`--allow-test-scorer`, and the core always forces their final selection to `abstain` with
`test_only: true`. Never use that flag for a real assessment.
