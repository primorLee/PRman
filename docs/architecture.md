# Codex-native architecture

## Decision

PRman is a contribution workflow Skill distributed as a Plugin for ordinary developers who want to
make one or more useful pull requests to well-known open-source projects. Codex remains the only
coding and tool-execution harness.

The product boundary is “PRman directs; Codex acts.” PRman defines repository selection, workflow
state, Goal completion criteria, evidence requirements, human confirmation, allowed GitHub writes,
and CI stopping rules. Codex owns Goal state, searches GitHub, reads and edits repositories, runs
commands, and invokes its connected GitHub tools. PRman does not duplicate the model, shell,
sandbox, Git client, GitHub client, credential store, or background worker.

## Components

### User goal and authorization

Intake first determines the requested positive PR count and whether the developer supplied a
repository and Issue. If no target is supplied, PRman asks for a technical direction and minimum
Star count instead of silently choosing them or requiring GitHub search syntax. This intake
authorizes read-only discovery and local implementation, but neither the initial request nor the PR
count serves as GitHub-write approval. Publication authority is granted separately for each PR only
after the user sees and confirms its post-implementation contribution preview.

### Codex Goal lifecycle

After intake is complete, the Skill checks the current task's Goal state. If no unfinished Goal
exists and Goal tools are available, it creates one automatically from the exact PR count, fixed
targets or discovery preferences, quality constraints, per-PR confirmation boundary, verification
requirements, CI follow-up, and early-stop rule. It reuses an existing Goal that already covers the
same session and does not replace an unrelated unfinished Goal. No token budget is inferred.

The Goal keeps safe in-scope work moving across discovery, implementation, tests, challenge review,
assessment, CI follow-up, and later contributions. Status updates do not stop it. A contribution
preview is a waiting checkpoint, not Goal completion; the same Goal resumes after the exact user
response. The requested count, qualifying Draft PRs with reported CI, user cancellation, and an
exhausted high-quality search define completion.

Goal state is owned by Codex rather than the Python package or PRman JSON contracts. Starting a Goal
does not broaden the sandbox, tool access, approval policy, repository scope, or GitHub authority.
It cannot infer a confirmation response or turn the requested count into batch write permission.

### Sequential contribution session

The requested count is a maximum session goal. PRman holds only one active contribution cycle at a
time and records temporary progress: requested count, completed Draft PRs, current target, and stop
reason. After CI follow-up for one PR, it searches for the next target and repeats the full workflow.
It stops early when no suitable target remains rather than generating filler work. There is no batch
confirmation: every PR has a new exact packet, preview, and user response.

### Read-only discovery

The Skill directs Codex to search for a small number of relevant repositories and issues for the
next contribution, reject unsuitable or duplicate work, and select one contribution-friendly
target. By default it prefers a recognised, actively maintained project with evidence that outside
PRs are reviewed. It checks
activity, issue clarity, assignment and existing-PR state, contribution rules, security policy,
licensing, verification feasibility, default branch, and full base commit.

Discovery uses the GitHub MCP dependency declared in skills/prman/agents/openai.yaml. No fork,
branch, comment, assignment, or other GitHub mutation occurs in this stage.

### Codex execution layer

Codex obtains a working copy, follows applicable AGENTS and repository instructions, makes the
smallest task-complete edit, and runs the target repository's relevant checks. PRman does not wrap or
reimplement those native capabilities.

### Adversarial maintainer review

After repository checks, Codex makes a distinct second pass over the exact final diff as a skeptical
maintainer trying to reject it. The pass checks issue coverage, edge cases, regressions, test
strength, repository conventions, accidental scope, duplicate work, low-value drive-by behavior,
and the strongest likely maintainer objection. Credible findings cause another edit, verification,
and complete review. The retained review evidence is bound to the candidate digest. This is
structured self-review by Codex, not independent human approval.

### Deterministic quality core

The existing Python helper validates JSON, binds repository/base/task context, recomputes each
candidate ID from the supplied UTF-8 diff, enforces typed evidence, generates a strict scorer
request, calls a configured scorer, and aggregates the result. It has no repository command runner
and no GitHub client. Its runtime uses only the Python standard library.

Required gates are evaluated before scoring and cannot be overridden by a high model score. The
default required gates are scope, secrets, tests, and adversarial review. Passing adversarial review
requires inspection or service evidence bound to the final candidate. Extra gates are advisory.
Eligible production readiness requires criterion minima, raw and lower-confidence-bound thresholds,
acceptable uncertainty and truncation, exact scorer metadata binding, and a verified canonical
evidence HMAC.

### Contribution preview and internal confirmation packet

After the final diff is verified and assessed, the Skill prepares a packet containing:

- exact repository, selected task, base commit, base and head branches, and fork route;
- exact embedded patch, digest, changed files, and summary;
- every relevant command result;
- the candidate-bound adversarial-review result, strongest objection, resolution, and note digest;
- ready, revise, or abstain plus scorer and attestation state;
- Draft PR title and body;
- the complete external-write list and bounded CI repair policy.

schemas/confirmation_packet.schema.json defines the machine-readable contract. Initial publication
is valid only for the unchanged packet; later diff updates are limited to its explicit CI repair
envelope. The assessment result itself always denies external-write authority. The local workflow
helper validates the packet, returns its canonical digest and the short phrase
`CREATE DRAFT PR OWNER/REPO`, and creates a scoped authorization only when the response matches that
phrase byte-for-byte.

The packet and digest stay internal by default. The user sees a contribution preview containing the
repository and task, selection reason, change summary and files, test results, risks or unknowns,
Draft PR title, and a reviewable full diff. Internal non-ready states are translated into plain
language; a known required-check failure is not offered for publication in the default flow.

The authorization artifact and run state have separate schemas. Their parsers recheck the target,
base, branch and fork route, allowed writes, Draft-only policy, confirmation-scope digest, and CI
budget instead of trusting serialized state. That internal digest combines the short user phrase
with the complete packet-bound authorization scope, so shortening the phrase does not drop the
branch, diff, assessment, or repair-budget binding.

### GitHub publication and CI follow-up

After confirmation, Codex may use only the listed GitHub operations. It creates the confirmed branch
or fork route, publishes the assessed commits, and creates a Draft PR. It never writes the default
branch, force-pushes, merges, enables auto-merge, or marks the PR ready for review.

CI inspection is read-only. The default confirmation may authorize at most two same-task repair
rounds on the same Draft PR. Every repair is retested and reassessed against a new diff digest.
Dependency changes, public API changes, broad refactors, security-posture changes, repository or
issue changes, and review responses require a new packet and confirmation.

The executable local run states are `authorized`, `draft_open`, `ci_failed`, `repairing`, and
`complete`. A Draft record must use the canonical GitHub PR URL and number for the authorized
repository and repeat the observed base branch and commit, head repository and branch, and diff
digest. CI must refer to the current PR head commit. Starting a repair consumes one confirmed round;
recording an update requires a new diff, a new commit, and an explicit in-scope assertion. Only
passing CI reaches complete.

## State flow

1. Intake: collect target or direction, minimum Stars, and requested PR count.
2. Goal: automatically create or reuse the session Goal without treating it as authorization.
3. Discover: search GitHub read-only for the next suitable contribution.
4. Select: choose one high-value target and record why.
5. Inspect: load repository rules, task context, base commit, and CI expectations.
6. Implement: let Codex edit locally and collect observed verification evidence.
7. Challenge-review: try to reject the final diff and resolve credible findings.
8. Assess: run deterministic gates and optional scoring; revise at most twice by default.
9. Confirm: display the simple contribution preview and wait for a fresh short answer.
10. Publish: perform only the confirmed fork, branch, push, and Draft PR operations.
11. Follow CI: inspect checks and perform bounded in-scope repairs.
12. Report or repeat: report progress and, if the requested count remains, return to discovery.

Any edit after review or assessment returns to Verify, Challenge-review, and Assess. Any material
scope or publication-plan change returns to Confirm. A denied confirmation terminates with a local
handoff; a pending confirmation leaves the Goal active at that checkpoint. Confirmation and state
from one PR never carry into the next cycle.

## Abstention behavior

Without a production scorer or trusted evidence attestation, required gates can pass while the final
internal result remains abstain. PRman translates that into a plain note that the optional extra
quality score is unavailable. The user may still explicitly confirm a Draft PR when repository
checks passed and this is the only uncertainty. A known failed required gate is not equivalent and
is not offered in the default flow.

## Package boundary

The Plugin contains the full Skill workflow and declares its GitHub MCP dependency. The Python
distribution contains only prman and prman.scorers: the deterministic assessment, confirmation,
authorization, run-state, CLI, and scorer code. Search, editing, command execution, credentials, and
GitHub mutation remain Codex capabilities directed by the Skill rather than Python package modules.

The helper is an acceptance and sequencing layer, not a cryptographic user-identity or remote-state
attestation system. It cannot prove who typed the confirmation, whether Codex displayed the packet,
whether reported assessment, GitHub, and CI facts are true, or whether a claimed repair is
semantically in scope. Its locally stored JSON can be replaced by a process with filesystem write
access, so it is not a hostile-host enforcement boundary.
