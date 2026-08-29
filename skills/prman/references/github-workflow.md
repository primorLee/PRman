# Confirmation, Draft PR, and CI workflow

Read this reference before presenting a GitHub confirmation packet and again after the user
confirms it.

## Confirmation packet

Before any GitHub mutation, show the user one self-contained packet matching the
[confirmation-packet schema](../../../schemas/confirmation_packet.schema.json) in substance. It
must identify:

- exact `OWNER/REPO`, repository URL, selected issue/task, and why it was chosen;
- full base commit, base branch, head repository, head branch, and whether a fork is required;
- the exact final diff, or a user-accessible exact diff artifact, plus its SHA-256 digest and changed
  files;
- every relevant verification command and whether it passed, failed, or could not run;
- PRman decision (`ready`, `revise`, or `abstain`), reason, scorer/test-only state, and evidence
  attestation state;
- proposed Draft PR title and full body;
- every planned external write, including fork, branch, push, Draft PR creation, and later updates;
- whether CI will be monitored and the maximum number of in-scope repair rounds (default: two).

Ask for confirmation only after displaying these fields. A brief reply such as “确认” or “yes” is
valid only when it clearly responds to the latest unchanged packet. Confirmation expires if the
target, base commit, initial diff, branch route, PR text, planned writes, or CI budget changes before
initial publication. After the Draft PR exists, only the explicitly confirmed CI repair envelope may
change the diff without a new packet.

`ready` is never write authorization. If the decision is `abstain` only because a production scorer
or trusted attestation is unavailable, the packet may still offer a Draft PR, but it must say that
quality readiness is unknown and ask the user to acknowledge that uncertainty. Do not present a
known required-gate failure as this missing-scorer exception. A remaining `revise` or failed required
gate needs a separate explicit override naming the failure.

If confirmation is denied, ambiguous, or absent, stop with the local diff and test results. Do not
retry the prompt or perform a smaller write.

## Publish only what was confirmed

After confirmation, recheck that the base and local diff still match the packet, then use Codex's
existing GitHub tools and credentials. Choose the confirmed route:

1. Create the named head branch from the exact base commit. If upstream push permission is absent,
   create or use the explicitly listed fork; do not silently change repositories.
2. Publish commits containing the assessed diff. Never push to the default branch and never force
   push.
3. Create a Draft PR with the confirmed base, head, title, and body. If the available tool cannot
   guarantee Draft state, stop instead of creating a normal PR.
4. Verify the returned repository, branch pair, Draft state, commit, and URL. Report any mismatch
   immediately and do not compound it with more writes.

Do not merge, approve, enable auto-merge, mark ready for review, assign reviewers, add labels, post
comments, close issues, or change repository settings unless the user later authorizes that exact
operation. Never store or request a GitHub token for PRman; use the connection already managed by
Codex.

## Follow CI within the confirmed scope

Monitoring checks and reading logs are read-only. When CI fails:

1. Identify the failing check and distinguish a change-caused failure from infrastructure or an
   unrelated base-branch failure.
2. Make a repair only when it is directly required by the confirmed task and fits the packet's CI
   budget.
3. Rerun relevant local verification, recompute the diff digest, and run PRman assessment again.
4. Add a normal commit to the same head branch and verify the Draft PR updated. Never rewrite
   history or force-push.
5. Stop after two repair rounds by default, or earlier if the same failure repeats without new
   evidence.

Adding dependencies, changing public APIs, broad refactoring, altering security posture, switching
the issue or repository, or expanding beyond the stated task is a material scope change. Present a
new packet and wait for new confirmation before publishing it. Review-comment fixes and any GitHub
comment or review response are outside the CI authorization unless explicitly included.

## Final report

Return the Draft PR URL and number, exact head commit, current CI status, final PRman decision,
verification summary, number of repair rounds, and any action still required from the user or
maintainer. Never describe a Draft PR as merged or production-ready.
