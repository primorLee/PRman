# Goal-backed execution

Read this reference after PRman intake is complete and before repository discovery. Goal mode is the
default for a PRman contribution session when the current Codex surface exposes Goal tools.

## Start or reuse the session Goal

Do not ask the developer whether PRman should use Goal mode.

1. Call `get_goal` before creating anything.
2. If there is no unfinished Goal, call `create_goal` exactly once. Do not set `token_budget` unless
   the developer explicitly requested a token budget.
3. If the current unfinished Goal already covers this PRman session, reuse it without creating a
   duplicate.
4. If an unrelated unfinished Goal exists, do not replace it, complete it, or mark it blocked.
   Mention the conflict once and continue the PRman workflow normally in the current task.
5. If Goal tools are unavailable, continue the same workflow normally and do not claim that a Goal
   was created.

Build the Goal from the completed intake. It must state:

- **Outcome:** complete up to the requested number of meaningful Draft PR contributions for the
  supplied repository and issues, or for the supplied technical direction and minimum Star count.
- **Constraints:** handle one contribution at a time; reject low-value or duplicate work; never
  lower the quality bar to reach the count; never treat the Goal or PR count as GitHub-write
  authority; require a fresh exact repository-bound confirmation for every Draft PR; never merge,
  enable auto-merge, force-push, or write the default branch.
- **Verification:** inspect repository rules, run relevant project checks, complete the skeptical
  maintainer review and PRman assessment, show the full preview and diff, then follow the confirmed
  Draft PR's CI within the repair budget.
- **Completion:** finish when the requested number of qualifying Draft PRs have been created and
  their current CI state reported, the developer stops the session, or reasonable safe discovery
  alternatives are exhausted and PRman reports why it stopped rather than creating filler PRs.

Use the exact intake values in the objective instead of leaving placeholders. A suitable shape is:

```text
Complete up to <count> meaningful open-source Draft PR contributions sequentially for <targets or
preferences>. For each contribution, select an open unclaimed task with real maintainer value,
inspect repository rules, implement and test the smallest complete fix, challenge-review and assess
the final diff, show a reviewable preview, require exact repository-bound confirmation before any
GitHub write, create only the confirmed Draft PR, and follow its CI within the approved repair
budget. Do not lower the quality bar to reach the count. Finish at the requested count or after safe
discovery alternatives are exhausted and the stop reason is reported.
```

## Continue without unnecessary questions

Once the Goal exists, continue through all safe, in-scope work. Send concise progress updates, but
do not turn them into requests for permission to continue. In particular:

- choose the clear best target automatically and try another candidate when one fails suitability
  checks;
- continue from discovery through local implementation, verification, challenge review,
  assessment, and preview without asking “continue?” between stages;
- after a completed PR, begin the next read-only discovery cycle automatically while the requested
  count remains;
- ask only for missing mandatory intake, the exact per-PR publication confirmation, or a genuinely
  user-only decision such as credentials, a CLA, materially different scope, or an approval the
  platform itself requires;
- keep the Goal active while waiting at a confirmation checkpoint, and resume after the developer's
  response without restarting completed work;
- treat a request for status as a status update, not as an instruction to stop the Goal.

Use `update_goal` with `complete` only when the Goal's completion criteria are actually met and no
required work remains. Do not complete it merely because one turn, one target, or one PR ended. Use
`blocked` only under the platform's genuine-blocker rules; waiting for the current per-PR answer is
an expected checkpoint, not permission to weaken or bypass confirmation.

## Authority remains separate

A Goal provides persistence, not permission. It does not expand the sandbox, tool access, approval
policy, repository scope, or GitHub authority. The initial request and requested count authorize
read-only discovery and local work only. Every GitHub mutation still requires the unchanged packet,
preview, and exact `CREATE DRAFT PR OWNER/REPO` response defined by `github-workflow.md` and
`safety.md`.

This follows the official OpenAI guidance for
[long-running work](https://learn.chatgpt.com/docs/long-running-work): a Goal carries an outcome,
constraints, and verification criteria while retaining the same sandbox and approval boundaries.
