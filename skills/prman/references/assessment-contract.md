# Assessment contract

Use this reference when preparing an input for `scripts/assess.py`.

## Boundary

Codex gathers evidence and, when authorized, edits the repository. The helper validates an
assessment, generates an allowlisted scorer request, calls an explicitly configured scorer, and
applies deterministic aggregation. It never executes repository commands or creates candidates.

The binding checks catch stale or cross-candidate content, but do not attest execution. Construct
records only from the current Codex task, repository state, exact diff, and observed command output.

## Input

The input uses `prman-assessment/1.1`:

```json
{
  "schema_version": "prman-assessment/1.1",
  "mode": "single",
  "context": {
    "repository_id": "<sha256-of-normalized-repository-identity>",
    "base_commit": "<full-lowercase-40-or-64-character-git-commit>",
    "task": "Implement the requested behavior",
    "task_digest": "<sha256-of-exact-UTF-8-task-text>",
    "repository_rules": ["Relevant repository instruction"]
  },
  "attestation": null,
  "candidates": [
    {
      "candidate_id": "<sha256-of-exact-UTF-8-diff>",
      "diff": "diff --git ...\n",
      "truncation_ratio": 0.0,
      "gates": [
        {
          "name": "tests",
          "status": "pass",
          "recoverable": false,
          "code": "PASS",
          "evidence": {
            "source": "command",
            "candidate_id": "<same-candidate-sha256>",
            "observed_at": "2026-08-29T12:00:00Z",
            "producer": "python-unittest",
            "producer_version": "3.12.11",
            "summary": "All relevant unit tests passed.",
            "log_digest": "<sha256-of-retained-or-observed-command-log>",
            "command": ["python", "-m", "unittest"],
            "exit_code": 0
          },
          "actionable": null
        }
      ]
    }
  ]
}
```

Use `single` for exactly one current change and `compare` only when Codex already has two or more
real candidates. Repository identity, base commit, task, and rules live once at assessment level, so
every compared candidate shares the same context. Do not generate placeholders to satisfy compare
mode.

Write the exact UTF-8 unified diff into `diff`, then compute its candidate ID:

```bash
python3.11 scripts/assess.py candidate-id --diff <diff-file>
```

The helper recomputes the digest from the JSON string. Preserve the exact line endings and terminal
newline used by the diff file. Compute `task_digest` from the exact UTF-8 bytes of `task`. Use a
stable, privacy-preserving SHA-256 of the normalized repository identity for `repository_id` and the
full base commit, not a moving branch name.

## Evidence

Every gate evidence record must contain:

- `source`: `command`, `inspection`, or `service`;
- the same `candidate_id` as the candidate;
- an offset-aware RFC 3339 `observed_at` time;
- the producer/tool name and exact version;
- a short pre-review summary and SHA-256 log/artifact digest;
- a non-empty argument array plus integer exit code for command evidence, otherwise nulls.

A passing command gate requires exit code zero. A passing `tests` gate specifically requires command
evidence. A recoverable failure requires non-empty actionable advice.

The default decision profile makes `scope`, `secrets`, and `tests` blocking. Missing or unknown
required gates force `abstain`; fatal required failures force `abstain`; recoverable required
failures may return `revise`. Other supplied gates are advisory and do not block selection.

Never mark an unavailable or skipped command as `pass`. Use `unknown` and explain the missing
evidence. Recompute the diff and rerun applicable evidence after every edit; old evidence will fail
the candidate binding once the diff changes.

Do not add a `scorer_request` to the assessment. The helper generates one from a strict projection of
the shared context, candidate diff, and evidence records.

## Trusted-executor attestation

Content bindings alone do not prove the caller ran a command. A production decision profile must set:

```json
"evidence_attestation": {
  "scheme": "hmac-sha256",
  "key_id": "trusted-codex-executor-v1",
  "hmac_secret_env": "PRMAN_EVIDENCE_HMAC_SECRET"
}
```

The trusted execution layer signs the canonical JSON bytes of the assessment's `schema_version`,
`mode`, `context`, and `candidates` fields (the `attestation` field is excluded) using:

```text
HMAC-SHA256(secret, "prman-evidence-v1\0" || canonical_assessment_bytes)
```

It then supplies:

```json
"attestation": {
  "scheme": "hmac-sha256",
  "key_id": "trusted-codex-executor-v1",
  "signature": "<lowercase-hex-hmac>"
}
```

The secret must contain at least 32 UTF-8 bytes and remain outside JSON. The decision config must be
fixed by the deployment rather than supplied by an untrusted assessment caller. Without a matching
configured key and valid signature, PRman may still return useful `revise` information but will force
an otherwise-ready selection to `abstain`.

## Output

The helper emits `prman-assessment-result/1.1`, repeats the repository/base/task bindings, and records
per-candidate score and aggregate details. Preserve it when an auditable handoff is requested.

Fixture/static runs are marked `test_only` and always select `abstain`. A result always states that
human confirmation is required, only a Draft PR is eligible, and no external write has been
authorized. The checked-in decision profile binds neither a production scorer nor an executor key,
so it abstains until exact calibrated and attestation bindings are explicitly configured.

Copy the exact decision, reason, test-only state, scorer identity, and attestation state into the
confirmation packet. Do not treat the assessment result as publication authority. When the result
abstains only because production scoring or attestation is unavailable, follow the plain-language
uncertainty disclosure in `github-workflow.md`; keep the internal labels out of the default preview.
