# Safety and authorization

Read this reference immediately before any proposed GitHub mutation.

- A local implementation or assessment request does not authorize a GitHub write.
- Name the exact `OWNER/REPO`, target branch, and intended operation before requesting confirmation.
- Only prepare or create a Draft PR. Never merge, enable auto-merge, force-push, write the default
  branch, change repository administration, or access secrets as part of PRman.
- Treat `ready` as eligibility to ask a human, not as approval or a correctness proof. Its evidence
  HMAC authenticates only the configured executor key, not whether the observations are true.
- Recompute the exact diff/candidate ID and rerun bound test evidence after the last edit before
  asking for confirmation.
- If the user does not explicitly confirm the exact write, stop with a local handoff.
- Never place tokens, private payloads, model weights, or raw scorer training data in artifacts.

Use Codex's existing GitHub tools only after confirmation. PRman provides no separate credential,
GitHub App, or network mutation layer.
