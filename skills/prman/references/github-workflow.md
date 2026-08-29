# Confirmation, Draft PR, and CI workflow

Read this reference before presenting a GitHub confirmation packet and again after the user
confirms it.

## Confirmation packet

Before any GitHub mutation, create one self-contained packet matching the
[confirmation-packet schema](../../../schemas/confirmation_packet.schema.json). It must identify:

- exact `OWNER/REPO`, repository URL, selected issue/task, and why it was chosen;
- full base commit, base branch, head repository, head branch, and whether a fork is required;
- the exact embedded final diff, its SHA-256 digest, and changed files;
- every relevant verification command and whether it passed, failed, or could not run;
- PRman decision (`ready`, `revise`, or `abstain`), reason, scorer/test-only state, and evidence
  attestation state;
- proposed Draft PR title and full body;
- every planned external write, including fork, branch, push, Draft PR creation, and later updates;
- whether CI will be monitored and the maximum number of in-scope repair rounds (default: two).

Embed the exact UTF-8 patch in the packet. Set its SHA-256 to the digest of those exact bytes. The
approval object must show a short, target-specific `confirmation_phrase` verbatim inside its prompt.

Validate and bind the packet from the skill directory, using temporary output paths:

```bash
python3.11 scripts/workflow.py confirmation prepare \
  --input <confirmation-packet.json> \
  --output <confirmation-check.json>
```

Show the complete packet plus the returned packet digest and confirmation phrase. The check output
must still say `external_write_authorized: false`.

Ask for confirmation only after displaying these fields. The response must exactly match the shown
confirmation phrase. Confirmation expires if the target, base commit, initial diff, branch route, PR
text, planned writes, or CI budget changes before initial publication. After the Draft PR exists,
only the explicitly confirmed CI repair envelope may change the diff without a new packet.

`ready` is never write authorization. If the decision is `abstain` only because a production scorer
or trusted attestation is unavailable, the packet may still offer a Draft PR, but it must say that
quality readiness is unknown and ask the user to acknowledge that uncertainty. Do not present a
known required-gate failure as this missing-scorer exception. A remaining `revise` or failed required
gate needs a separate explicit override naming the failure.

If confirmation is denied, ambiguous, or absent, stop with the local diff and test results. Do not
retry the prompt or perform a smaller write.

After an exact response, create the scoped authorization using the digest returned by `prepare`:

```bash
python3.11 scripts/workflow.py confirmation authorize \
  --input <confirmation-packet.json> \
  --expected-packet-digest <sha256-from-prepare> \
  --response '<exact-user-response>' \
  --output <write-authorization.json>

python3.11 scripts/workflow.py workflow begin \
  --authorization <write-authorization.json> \
  --output <workflow-run.json>
```

The helper rejects a changed packet, an inexact response, a normal PR, inconsistent branches, a
`ready` claim missing its required production-scorer or attestation fields, unsupported writes, and
mismatched CI repair authority. The exact phrase names the repository and head branch; non-ready
phrases also acknowledge the decision and the prompt must show its exact reason. It records
user-derived authorization but cannot prove the response actually came from the user or that the
packet was displayed; Codex must never invent or reuse it.

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

Record the exact returned Draft PR before following CI:

```bash
python3.11 scripts/workflow.py workflow record-draft \
  --input <workflow-run.json> \
  --url <draft-pr-url> \
  --number <draft-pr-number> \
  --base-branch <observed-base-branch> \
  --base-commit <observed-full-base-commit> \
  --head-repository <observed-head-owner/repo> \
  --head-branch <observed-head-branch> \
  --diff-sha256 <observed-full-diff-digest> \
  --head-commit <full-head-commit> \
  --draft \
  --output <workflow-run.json>
```

Do not merge, approve, enable auto-merge, mark ready for review, assign reviewers, add labels, post
comments, close issues, or change repository settings unless the user later authorizes that exact
operation. Never store or request a GitHub token for PRman; use the connection already managed by
Codex.

## Follow CI within the confirmed scope

Monitoring checks and reading logs are read-only. When CI fails:

1. Identify the failing check and distinguish a change-caused failure from infrastructure or an
   unrelated base-branch failure.
2. Record the exact CI status and current head commit with `workflow record-ci`.
3. Make a repair only when it is directly required by the confirmed task and fits the packet's CI
   budget.
4. Before editing, consume one repair round with `workflow begin-repair`.
5. Rerun relevant local verification, recompute the diff digest, and run PRman assessment again.
6. Add a normal commit to the same head branch and verify the Draft PR updated. Never rewrite
   history or force-push.
7. Record the newly assessed digest and head commit with `workflow record-update --in-scope`.
8. Stop after two repair rounds by default, or earlier if the same failure repeats without new
   evidence.

Each workflow command reads and emits `prman-workflow-run/1.0`. It rejects CI from the wrong commit,
updates outside the repair state, unchanged diffs or commits, and repair rounds beyond the confirmed
budget. It also rejects a PR URL or number outside the authorized repository. A passing `record-ci`
transition ends in `complete`.

The helper validates the structured state it receives. It cannot independently prove that GitHub or
CI returned those facts, that the assessment summary is truthful, that the user authored the
response, or that `--in-scope` is semantically correct. Locally writable state is not a hostile-host
security boundary. Codex must verify observations with its connected tools and must not use the
flags to launder an unauthorized change.

Adding dependencies, changing public APIs, broad refactoring, altering security posture, switching
the issue or repository, or expanding beyond the stated task is a material scope change. Present a
new packet and wait for new confirmation before publishing it. Review-comment fixes and any GitHub
comment or review response are outside the CI authorization unless explicitly included.

## Final report

Return the Draft PR URL and number, exact head commit, current CI status, final PRman decision,
verification summary, number of repair rounds, and any action still required from the user or
maintainer. Never describe a Draft PR as merged or production-ready.
