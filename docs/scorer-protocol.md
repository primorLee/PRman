# Scorer provider protocol

PRman protocol `prman-scorer-plugin/1.1` keeps scoring separate from the Codex workflow and
deterministic decision code. Training, datasets, model weights, and inference dependencies do not
belong in the core package.

## Request contract

The core generates `prman-scorer-request/1.1`; an assessment caller cannot supply arbitrary scorer
payloads. The request contains exactly:

- a candidate ID that hashes the included UTF-8 diff;
- one shared repository ID, base commit, task text/digest, and repository-rules list;
- a strict projection of gate name, status, code, source, summary, and log digest;
- the six canonical criteria in order.

No other structured fields are accepted. Raw task, rule, diff, and summary strings must come from
pre-review sources; the core cannot semantically sanitize text disguised inside an allowed string.

## Criteria and score bundle

Every response covers these criteria exactly once and in this order:

1. `correctness`
2. `task_alignment`
3. `scope`
4. `repository_conventions`
5. `maintainability`
6. `reviewer_effort`

Each response item contains a calibrated probability, uncertainty, non-empty evidence strings,
optional actionable critique, and an out-of-distribution flag. The score bundle repeats the
candidate ID, request digest, and provider metadata.

## Authenticated local HTTP provider

`builtin.local-http` is the recommended process boundary. It accepts only `http://` endpoints whose
host is a numeric loopback address, disables environment proxies and redirects, caps timeouts at 300
seconds, and limits requests and responses to 4 MiB.

Its config contains `hmac_secret_env`, the name of an environment variable holding at least 32 UTF-8
bytes. Never put the secret itself in JSON. The decision profile must also set `scorer_binding` to
the exact protocol, provider, provider version, model revision, and calibrator version expected from
the signed response. This scorer signature is separate from the trusted-executor evidence
attestation required for final readiness.

The request envelope is:

```json
{
  "schema_version": "prman-scorer-service-request/1.1",
  "request_digest": "<sha256>",
  "nonce": "<64 random lowercase hex characters>",
  "provider": {"protocol_version": "prman-scorer-plugin/1.1"},
  "request": {"schema_version": "prman-scorer-request/1.1"}
}
```

The client sends header `X-PRman-Signature` as lowercase-hex HMAC-SHA256 over:

```text
"prman-request-v1\0" || exact_request_body_bytes
```

The response envelope is:

```json
{
  "schema_version": "prman-scorer-service-response/1.1",
  "request_digest": "<same sha256>",
  "nonce": "<same nonce>",
  "provider": {"protocol_version": "prman-scorer-plugin/1.1"},
  "scores": []
}
```

The service signs the exact response body in `X-PRman-Signature` as:

```text
HMAC-SHA256(secret, "prman-response-v1\0" || exact_response_body_bytes)
```

PRman compares signatures in constant time before parsing the response, then checks the nonce,
request digest, signed identity, decision-profile binding, and score contract. HMAC authenticates the
service key; it does not prove that a particular model actually produced the scores.

## Trusted Python providers

An independently packaged provider may register a factory:

```toml
[project.entry-points."prman.scorers"]
"acme.prman-rm" = "acme_prman_scorer:create_provider"
```

The factory receives the scorer config `options` and returns an object with:

```python
@property
def metadata(self) -> ProviderMetadata: ...

def score(self, request: ScorerRequest) -> ScoreBundle: ...
```

The metadata's `provider_id` must exactly match the entry-point name and the decision profile's
binding. Python entry points execute factories and scoring methods inside the PRman process with its
full environment, filesystem, network, and process privileges. PRman cannot stop a blocking call or
undo monkey-patching. The CLI therefore requires `--allow-trusted-python-scorer` before loading one.
Use a separately restricted service for any scorer that is not fully trusted.

## Failure and comparison behavior

Provider metadata is pinned before the first candidate and checked before and after every request.
Ordinary exceptions, malformed return types, stale digests, metadata changes, invalid signatures,
and invalid values produce structured `scorer_unavailable:*` abstentions without exposing exception
messages. `KeyboardInterrupt` and other `BaseException` subclasses are not swallowed.

OOD, over-uncertain, and over-truncated candidates are marked non-comparable. Compare mode requires
at least two comparable candidates scored under the same assessment context and pinned metadata.

## Test providers

`builtin.static` and `builtin.fixture-json` exist only for contract and packaging tests. The CLI
requires `--allow-test-scorer`, the result is marked `test_only`, and the final selection is always
`abstain`, even when all fixture scores exceed the thresholds.
