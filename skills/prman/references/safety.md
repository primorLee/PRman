# Safety and authorization

Read this reference immediately before any proposed GitHub mutation.

- Discovery, cloning, local edits, tests, and assessment do not authorize an external write.
- Prepare the exact internal packet defined in `github-workflow.md`, present its simple contribution
  preview, then wait. Confirmation applies only to that repository, base, branch route, initial
  diff, PR text, write list, and the explicitly bounded CI repair envelope.
- A requested PR count authorizes no GitHub write and is never a batch confirmation. Every PR in a
  multi-PR session requires its own unchanged packet, preview, and fresh exact response.
- An active Codex Goal supplies persistence only. It cannot grant GitHub authority, answer a
  confirmation prompt, broaden tool permissions, or bypass a platform approval.
- Run the bundled confirmation helper before asking and after the exact response. No authorization
  artifact means no GitHub write. A plain yes/confirm is invalid; require only the short phrase
  `CREATE DRAFT PR OWNER/REPO` displayed by the helper. Never invent, normalize, trim, or reuse the
  user's response.
- Only create or update the confirmed Draft PR. Never merge, approve, enable auto-merge, mark ready
  for review, force-push, write the default branch, change repository administration, or expose
  secrets.
- Recompute the exact diff/candidate ID and rerun bound verification after every edit. A `ready`
  result is eligibility to ask, not approval or a correctness proof.
- An internal `abstain` caused only by missing optional production scoring or attestation may be
  published after the preview plainly discloses that limitation. Never hide a known failing gate
  behind `abstain`, and do not make internal assessment vocabulary part of the default interaction.
- CI repair authority is bounded by the confirmed task and round limit. Material scope changes,
  review responses, and new GitHub operations require new confirmation.
- If confirmation is missing, ambiguous, denied, or stale, stop with a local handoff.
- Never place tokens, private payloads, model weights, or raw scorer training data in artifacts.

## Denied, ambiguous, or stale confirmation

Do not run `confirmation authorize` unless the response is the exact short phrase for the unchanged
packet. If an inexact response or stale digest is passed to the helper, it exits unsuccessfully
before emitting a write-authorization artifact. The absence of an artifact is a hard stop, not a
reason to retry with normalized text or a reduced write.

Return a plain-language local-only handoff containing the selected target, change summary, test
results, reviewable diff, and the reason publication stopped. Keep the local branch, commit, digest,
and assessment record available if the user asks. An explicit denial ends the attempt without
another confirmation prompt. A stale packet requires updated verification and assessment, a newly
prepared complete packet, and a fresh exact response before the first GitHub write.

Use Codex's connected GitHub tools and approval surfaces. PRman stores no GitHub credential and
provides no separate network mutation layer.
