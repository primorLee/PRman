---
name: prman
description: "Help ordinary developers contribute to well-known open-source projects with Codex: find one suitable repository issue, implement and test a focused change, show a simple contribution preview, create a human-confirmed Draft PR, and follow CI. Use when the user wants to find an open-source contribution or complete and send a PR; do not use for generic code questions, review-only requests, or bulk outreach."
---

# PRman

PRman helps a developer complete one useful open-source contribution. Codex performs the search,
coding, tests, and connected GitHub operations; PRman keeps the steps safe and understandable. Use
Codex's existing repository, shell, and GitHub tools. Do not create a second coding agent,
credential store, GitHub client, worktree manager, or command sandbox.

Keep the default user experience simple. Do not expose JSON packets, digests, state-machine names,
scorer terminology, or attestation details unless the user asks. Store those internal artifacts in
temporary files. Speak in plain language about what was selected, changed, tested, and still
uncertain.

## End-to-end workflow

1. Understand what the developer wants to contribute. If the request is broad, default to one
   small, well-defined issue in a well-known, active, contribution-friendly project; do not make the
   user design search filters. The initial request authorizes read-only discovery and local work,
   not a GitHub write. Even if the user asks to send a PR automatically, require step 7.
2. Read [references/orchestration.md](references/orchestration.md). Search GitHub read-only, choose
   one target, and inspect its instructions before editing. If the user names a repository or issue,
   start there but still verify that an outside contribution is suitable.
3. Let Codex make the smallest task-complete local change and run the target repository's own
   relevant tests, lint, type checks, or builds. Preserve exact command results and the final diff.
4. Read [references/assessment-contract.md](references/assessment-contract.md), prepare a bound
   assessment in temporary storage, and run the helper from this skill directory:

   ```bash
   python3.11 scripts/assess.py --input <assessment.json> [--scorer-config <scorer.json>]
   ```

   Use any available Python 3.11+ interpreter. Resolve the script relative to this `SKILL.md`.
   The helper evaluates supplied evidence; it does not run commands or call GitHub.
5. Treat assessment as an internal quality check. Fix actionable problems and reassess, for at most
   two rounds by default. Do not offer a Draft PR with a known required-check failure. If repository
   tests pass but optional production scoring is unavailable, say only that the automatic quality
   score is unavailable; do not ask the user to understand `abstain`, scorers, or attestations.
6. Keep the exact diff, evidence, assessment, and planned GitHub writes bound in temporary internal
   artifacts. Any edit after assessment requires fresh verification and assessment.
7. Read [references/github-workflow.md](references/github-workflow.md) and
   [references/safety.md](references/safety.md). Build and validate the complete internal packet,
   then show a short contribution preview: repository and issue, why it was selected, what changed,
   test results, risks or unknowns, Draft PR title, and an accessible full diff. State that PRman
   will create a Draft PR and follow CI. Show the helper's short target-specific confirmation phrase
   and stop. Do not display the packet JSON or digest unless asked. Create scoped write authorization
   only from the user's exact response to that unchanged preview; a plain yes is invalid.
8. After authorization, use Codex's GitHub tools to perform only the listed writes: create or use
   the confirmed contribution branch, publish the exact assessed change, and open a Draft PR. Record
   the returned Draft PR in the helper state. Never merge, enable auto-merge, force-push, or write
   the default branch.
9. Follow the Draft PR's CI. Within the confirmed budget, diagnose failures, make only in-scope
   repairs, rerun verification and assessment, and update the same Draft PR without force-pushing.
   Advance the helper state for each CI result and repair round. A material scope change requires a
   refreshed packet and new confirmation.
10. Return the Draft PR URL, CI result, any repairs made, and any remaining human action in plain
    language. Keep internal decision labels out of the default report.

## Internal scorer boundary

The scorer is optional and replaceable. Without an authenticated production scorer, an exact
decision-profile binding, and a trusted-executor evidence attestation, passing hard gates still
results internally in `abstain`. Test scorers always force `abstain`; never use a fixture or static
scorer to claim readiness. Translate this state into a short user-facing uncertainty note.

Read [references/scorer-contract.md](references/scorer-contract.md) only when configuring,
implementing, or diagnosing a scorer. Treat Python entry-point scorers as fully trusted in-process
code and prefer the authenticated loopback HTTP boundary for deployed scorers. Do not train or
download a scorer unless the user separately asks for that work.
