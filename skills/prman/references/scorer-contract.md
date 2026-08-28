# Scorer contract

Read this reference only when configuring, implementing, or diagnosing a scorer.

PRman uses protocol `prman-scorer-plugin/1.0` and six ordered criteria:

1. `correctness`
2. `task_alignment`
3. `scope`
4. `repository_conventions`
5. `maintainability`
6. `reviewer_effort`

Every score contains a calibrated probability in `[0, 1]`, uncertainty in `[0, 1]`, evidence,
optional actionable critique, and an out-of-distribution flag. Responses must echo the request
digest. PRman rejects duplicate or missing criteria, stale digests, changing provider metadata,
non-finite numbers, and future outcome or identity fields in requests.

Provider configuration uses `prman-scorer-config/1.0`. `builtin.local-http` accepts only numeric
loopback HTTP endpoints, disables proxy use and redirects, limits timeouts, and caps response size.
Third-party Python packages may register factories under the `prman.scorers` entry-point group.

`builtin.static` and `builtin.fixture-json` are test-only. The CLI refuses them unless the caller
passes `--allow-test-scorer`; the PRman skill must never use that flag for a real readiness claim.

Scorer requests must not contain review decisions, approval or merge outcomes, author or maintainer
identity, prior selection, reward, or model-score fields. A scorer never overrides a hard gate and
never grants permission for an external write.
