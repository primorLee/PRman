# Safety and authorization

Read this reference immediately before any proposed GitHub mutation.

- Discovery, cloning, local edits, tests, and assessment do not authorize an external write.
- Present the exact confirmation packet defined in `github-workflow.md`, then wait. Confirmation
  applies only to that repository, base, branch route, initial diff, PR text, write list, and the
  explicitly bounded CI repair envelope.
- Only create or update the confirmed Draft PR. Never merge, approve, enable auto-merge, mark ready
  for review, force-push, write the default branch, change repository administration, or expose
  secrets.
- Recompute the exact diff/candidate ID and rerun bound verification after every edit. A `ready`
  result is eligibility to ask, not approval or a correctness proof.
- An `abstain` caused by missing production scoring or attestation may be published only after the
  user acknowledges that uncertainty. Never hide a known failing gate behind `abstain`.
- CI repair authority is bounded by the confirmed task and round limit. Material scope changes,
  review responses, and new GitHub operations require new confirmation.
- If confirmation is missing, ambiguous, denied, or stale, stop with a local handoff.
- Never place tokens, private payloads, model weights, or raw scorer training data in artifacts.

Use Codex's connected GitHub tools and approval surfaces. PRman stores no GitHub credential and
provides no separate network mutation layer.
