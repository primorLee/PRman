---
name: prman
description: "Help ordinary developers contribute to well-known open-source projects with Codex: clarify the repository and issue or ask for a technical direction and minimum Star count, ask how many PRs are wanted, automatically keep the session moving with a Codex Goal, then complete meaningful contributions sequentially with implementation, tests, skeptical maintainer-style review, a simple preview, human-confirmed Draft PR creation, and CI follow-up. Use when the user wants to find open-source contributions or complete and send PRs; do not use for generic code questions, review-only requests, low-value drive-by changes, or unreviewed bulk outreach."
---

# PRman

PRman helps a developer complete one or more useful open-source contributions, one at a time. Codex
performs the search, coding, tests, and connected GitHub operations; PRman keeps the steps safe and
understandable. Use Codex's existing repository, shell, and GitHub tools. Do not create a second
coding agent, credential store, GitHub client, worktree manager, or command sandbox.

After required intake is complete, automatically start or reuse a Codex Goal for the whole session
when Goal tools are available. Do not ask whether to enable Goal mode. The Goal keeps work moving
between genuine user checkpoints; it does not grant permissions or replace per-PR confirmation.

Keep the default user experience simple. Do not expose JSON packets, digests, state-machine names,
scorer terminology, or attestation details unless the user asks. Store those internal artifacts in
temporary files. Speak in plain language about what was selected, changed, tested, and still
uncertain.

## End-to-end workflow

1. Read [references/orchestration.md](references/orchestration.md). Before searching, determine
   whether the developer already has a repository and issue, and how many PRs they want in this
   session. Ask only for missing information. If no target is specified, also ask for the technical
   direction and minimum acceptable GitHub Star count, then stop and wait for the answer. Do not
   silently choose these preferences or the PR count.
2. Once intake is complete, read [references/goal-mode.md](references/goal-mode.md). Automatically
   create or reuse one Goal covering the complete requested session. Continue autonomously between
   checkpoints instead of asking whether to search, edit, test, review, or proceed to the next
   contribution. Goal mode must preserve the same sandbox, approval policy, quality bar, and exact
   per-PR GitHub confirmation boundary.
3. Search GitHub read-only only after intake is complete. Choose one meaningful target, verify that
   the issue is open and not already being handled, and inspect the repository instructions before
   editing. Reject scanner-generated trivia and changes whose only purpose is to create a PR. The
   initial request authorizes discovery and local work, not a GitHub write.
4. Let Codex make the smallest task-complete local change and run the target repository's own
   relevant tests, lint, type checks, or builds. Preserve exact command results and the final diff.
5. Read [references/adversarial-review.md](references/adversarial-review.md). After tests, review the
   complete final diff again as a skeptical maintainer looking for a reason to reject it. Fix every
   credible finding, rerun affected checks, and repeat the review. An incomplete or failed review is
   a blocking gate; small diff size alone is not a failure when the change fixes a real problem and
   includes convincing verification.
6. Read [references/assessment-contract.md](references/assessment-contract.md), prepare a bound
   assessment in temporary storage, and run the helper from this skill directory:

   ```bash
   python3.11 scripts/assess.py --input <assessment.json> [--scorer-config <scorer.json>]
   ```

   Use any available Python 3.11+ interpreter. Resolve the script relative to this `SKILL.md`.
   The helper evaluates supplied evidence; it does not run commands or call GitHub.
7. Treat assessment as an internal quality check. Fix actionable problems and reassess, for at most
   two rounds by default. Do not offer a Draft PR with a known required-check failure. If repository
   tests pass but optional production scoring is unavailable, say only that the automatic quality
   score is unavailable; do not ask the user to understand `abstain`, scorers, or attestations.
8. Keep the exact diff, evidence, adversarial-review record, assessment, and planned GitHub writes
   bound in temporary internal artifacts. Any edit after the review requires fresh verification,
   adversarial review, and assessment.
9. Read [references/github-workflow.md](references/github-workflow.md) and
   [references/safety.md](references/safety.md). Build and validate the complete internal packet,
   then show a short contribution preview: repository and issue, why it was selected, what changed,
   test results, risks or unknowns, Draft PR title, and an accessible full diff. State that PRman
   will create a Draft PR and follow CI. Show the helper's short target-specific confirmation phrase
   and stop. Do not display the packet JSON or digest unless asked. Create scoped write authorization
   only from the user's exact response to that unchanged preview; a plain yes is invalid.
10. After authorization, use Codex's GitHub tools to perform only the listed writes: create or use
   the confirmed contribution branch, publish the exact assessed change, and open a Draft PR. Record
   the returned Draft PR in the helper state. Never merge, enable auto-merge, force-push, or write
   the default branch.
11. Follow the Draft PR's CI. Within the confirmed budget, diagnose failures, make only in-scope
   repairs, rerun verification and adversarial review, reassess, and update the same Draft PR without
   force-pushing. Advance the helper state for each CI result and repair round. A material scope
   change requires a refreshed packet and new confirmation.
12. Return the Draft PR URL, CI result, any repairs made, and any remaining human action in plain
    language. Keep internal decision labels out of the default report. If the requested count has
    not been reached, start the next contribution at step 3 with a new target and repeat the entire
    per-PR workflow. Never reuse confirmation from an earlier PR.

## Multiple-PR sessions

Treat the requested PR count as a maximum workflow goal, not a quota that weakens selection. Work
sequentially: discover, implement, verify, adversarially review, preview, confirm, publish, and
follow CI for one contribution before beginning the next. Keep temporary session progress with the
requested count, completed Draft PRs, current target, and stop reason. Each PR needs its own exact
packet, diff, preview, and fresh repository-bound confirmation, even when several PRs target the
same repository. Do not parallelize outreach or open speculative PRs to reach the count. If there
are not enough convincing targets, stop early and report how many were completed and why no filler
PR was created. Keep the Goal active while waiting for a per-PR confirmation and resume it from the
same state after the user responds. Do not mark the Goal complete after a preview or after the first
PR when more requested contributions remain.

## Internal scorer boundary

The scorer is optional and replaceable. Without an authenticated production scorer, an exact
decision-profile binding, and a trusted-executor evidence attestation, passing hard gates still
results internally in `abstain`. Test scorers always force `abstain`; never use a fixture or static
scorer to claim readiness. Translate this state into a short user-facing uncertainty note.

Read [references/scorer-contract.md](references/scorer-contract.md) only when configuring,
implementing, or diagnosing a scorer. Treat Python entry-point scorers as fully trusted in-process
code and prefer the authenticated loopback HTTP boundary for deployed scorers. Do not train or
download a scorer unless the user separately asks for that work.
