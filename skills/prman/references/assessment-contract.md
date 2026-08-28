# Assessment contract

Use this reference when preparing an input for `scripts/assess.py`.

## Boundary

Codex gathers evidence and, when authorized, edits the repository. The helper only validates an
assessment, calls an explicitly configured scorer, and applies deterministic aggregation. It never
executes repository commands or creates candidates.

## Input

The input uses `prman-assessment/1.0`:

```json
{
  "schema_version": "prman-assessment/1.0",
  "mode": "single",
  "candidates": [
    {
      "candidate_id": "<sha256-of-diff>",
      "truncation_ratio": 0.0,
      "gates": [
        {
          "name": "tests",
          "status": "pass",
          "recoverable": false,
          "code": "PASS",
          "evidence": {"command": ["make", "test"], "exit_code": 0},
          "actionable": null
        }
      ],
      "scorer_request": null
    }
  ]
}
```

Use `single` for one current change and `compare` only when Codex already has two or more real
candidates. Do not generate placeholder candidates to satisfy comparison mode.

Compute the candidate ID from the exact unified diff:

```bash
python3.11 scripts/assess.py candidate-id --diff <diff-file>
```

The default decision profile requires `scope`, `secrets`, and `tests` gates. Add applicable evidence
for lint, type checking, security, licensing, and CI. Gate states mean:

- `pass`: the named check ran or was deterministically inspected and passed.
- `fail`: the check failed; set `recoverable` only when a code revision can address it.
- `unknown`: evidence is missing or inconclusive; it always forces `abstain`.

Never mark an unavailable or skipped command as `pass`. Use `unknown` and describe why in `evidence`.
Any non-recoverable failure, unknown required gate, or missing required gate dominates scorer output.

When a production scorer is configured, `scorer_request` must use `prman-scorer-request/1.0`, repeat
the same `candidate_id`, and contain exactly one payload for each of the six criteria listed in
`references/scorer-contract.md`. Each payload must identify its `criterion` and may include task,
repository, diff, and observed evidence available before review or merge.

## Output

The helper emits `prman-assessment-result/1.0` with per-candidate aggregates and one selection.
Preserve the result when an auditable handoff is requested. Fixture/static runs are visibly marked
`test_only`. A result always states that human confirmation is required, only a Draft PR is eligible,
and no external write has been authorized.
