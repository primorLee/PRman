# Scorer provider protocol

PRman keeps fine-tuned scoring separate from the Codex workflow and deterministic decision code.
Training, datasets, model weights, and inference dependencies do not belong in the core package.

## Criteria

Every request and response covers exactly these ordered criteria:

1. `correctness`
2. `task_alignment`
3. `scope`
4. `repository_conventions`
5. `maintainability`
6. `reviewer_effort`

Each response item contains a calibrated probability, uncertainty, evidence strings, optional
actionable critique, and an out-of-distribution flag.

## Python providers

An independently packaged provider registers a factory:

```toml
[project.entry-points."prman.scorers"]
"acme.prman-rm" = "acme_prman_scorer:create_provider"
```

The factory receives the `options` object from `prman-scorer-config/1.0` and returns an object with:

```python
@property
def metadata(self) -> ProviderMetadata: ...

def score(self, request: ScorerRequest) -> ScoreBundle: ...
```

The metadata's `provider_id` must exactly match the entry-point name. Provider, model, and calibrator
revisions must be non-empty and stable throughout a request.

## Local HTTP provider

`builtin.local-http` accepts only `http://` endpoints whose host is a numeric loopback address. It
disables environment proxies and redirects, caps timeouts at 300 seconds, and limits responses to
4 MiB.

The request envelope is:

```json
{
  "schema_version": "prman-scorer-service-request/1.0",
  "request_digest": "<sha256>",
  "request": {"schema_version": "prman-scorer-request/1.0"}
}
```

The response envelope echoes that digest and returns six scores:

```json
{
  "schema_version": "prman-scorer-service-response/1.0",
  "request_digest": "<same-sha256>",
  "scores": []
}
```

## Leakage boundary

Scorer payloads may contain task text, repository rules, the exact candidate diff, and observed
pre-review evidence. PRman recursively rejects fields representing review or merge outcomes,
approval, identities, prior selection, rewards, or model scores.

The provider response cannot override hard gates or authorize a write. A malformed, stale, partial,
duplicate, non-finite, or out-of-range response fails closed.

## Test providers

`builtin.static` and `builtin.fixture-json` exist only to test contracts and packaging. The CLI
requires `--allow-test-scorer` before using them and marks the result `test_only`. A real PRman Skill
run must never pass that flag.
