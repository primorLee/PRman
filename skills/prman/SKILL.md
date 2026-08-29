---
name: prman
description: "Run a human-confirmed GitHub pull-request workflow with Codex: discover a suitable repository or issue, implement and verify a focused change, assess it with evidence gates, prepare an exact confirmation packet, create a Draft PR, and follow CI. Use when the user asks Codex to find or complete contribution work and prepare or send a PR; do not use for generic code questions, review-only requests, or bulk outreach."
---

# PRman

PRman is the workflow layer; Codex is the coding and tool-execution layer. Use Codex's existing
repository, shell, and GitHub tools. Do not create a second coding agent, credential store, GitHub
client, worktree manager, or command sandbox.

## End-to-end workflow

1. Establish the requested repository criteria, task type, and any fixed target. The initial request
   authorizes read-only discovery and local implementation, not an external GitHub write. Even if
   the user asks to "send a PR automatically," require the confirmation in step 7.
2. Read [references/orchestration.md](references/orchestration.md). Search GitHub read-only, select
   one contribution-friendly target, and inspect its instructions before editing. If the user names
   a repository or issue, start from that target but still verify that the contribution is suitable.
3. Let Codex make the smallest task-complete local change and run the target repository's own
   relevant tests, lint, type checks, or builds. Preserve exact command results and the final diff.
4. Read [references/assessment-contract.md](references/assessment-contract.md), prepare a bound
   assessment in temporary storage, and run the helper from this skill directory:

   ```bash
   python3.11 scripts/assess.py --input <assessment.json> [--scorer-config <scorer.json>]
   ```

   Use any available Python 3.11+ interpreter. Resolve the script relative to this `SKILL.md`.
   The helper evaluates supplied evidence; it does not run commands or call GitHub.
5. Interpret the quality result literally:
   - `ready`: eligible to ask for confirmation, not permission to publish or proof of correctness.
   - `revise`: address the reported, actionable problem and reassess.
   - `abstain`: disclose the uncertainty or missing production scorer/attestation. Never relabel it
     as `ready`. A Draft PR may still be offered only through the explicit acknowledgement path in
     the GitHub workflow reference.
6. Use at most two assessment-guided revision rounds by default. If a required gate still has a
   known failure, stop unless the user separately and explicitly accepts that exact failure.
7. Read [references/github-workflow.md](references/github-workflow.md) and
   [references/safety.md](references/safety.md). Show one exact confirmation packet containing the
   target, branches, base commit, diff, verification, assessment, Draft PR text, planned writes, and
   CI repair budget. Validate it with the bundled workflow helper, show its digest and exact
   target-specific confirmation phrase, then stop and wait. For `revise` or `abstain`, show the
   exact reason and require the helper's acknowledgement phrase. Create a scoped write authorization
   only from the user's byte-for-byte response to that unchanged packet; a plain yes is invalid.
8. After authorization, use Codex's GitHub tools to perform only the listed writes: create or use
   the confirmed contribution branch, publish the exact assessed change, and open a Draft PR. Record
   the returned Draft PR in the helper state. Never merge, enable auto-merge, force-push, or write
   the default branch.
9. Follow the Draft PR's CI. Within the confirmed budget, diagnose failures, make only in-scope
   repairs, rerun verification and assessment, and update the same Draft PR without force-pushing.
   Advance the helper state for each CI result and repair round. A material scope change requires a
   refreshed packet and new confirmation.
10. Return the Draft PR URL, CI state, assessment decision, changes made after confirmation, and any
    remaining human action.

## Scorer boundary

The scorer is optional and replaceable. Without an authenticated production scorer, an exact
decision-profile binding, and a trusted-executor evidence attestation, passing hard gates still
results in `abstain`. Test scorers always force `abstain`; never use a fixture or static scorer to
claim readiness.

Read [references/scorer-contract.md](references/scorer-contract.md) only when configuring,
implementing, or diagnosing a scorer. Treat Python entry-point scorers as fully trusted in-process
code and prefer the authenticated loopback HTTP boundary for deployed scorers. Do not train or
download a scorer unless the user separately asks for that work.
