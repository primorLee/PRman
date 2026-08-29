---
name: prman
description: Evaluate and refine Codex code changes with deterministic evidence gates and an optional PRman scorer. Use for issue-to-patch work, candidate comparison, or pre-PR readiness decisions; do not use for general code questions without a proposed change.
---

# PRman

Treat Codex as the execution and orchestration layer. Do not create a second coding-agent,
worktree, sandbox, or candidate-generation harness for this workflow.

## Workflow

1. Establish the requested outcome and current authorization. A request to assess or review does not
   authorize code edits or an external GitHub write.
2. Inspect the repository instructions and the task. Let Codex perform repository exploration,
   editing, command execution, and any native candidate work.
3. Collect observable evidence for the proposed change. Bind it to the exact UTF-8 diff/candidate
   digest, shared repository identity, full base commit, and exact task digest. Never infer a passing
   gate from scorer output or from the absence of an error.
4. Before preparing an assessment, read
   [references/assessment-contract.md](references/assessment-contract.md). Create the assessment in a
   temporary location unless the user asks to retain it.
5. Run the deterministic helper from this skill directory:

   ```bash
   python3.11 scripts/assess.py --input <assessment.json> [--scorer-config <scorer.json>]
   ```

   Use an available Python 3.11+ interpreter. Resolve `scripts/assess.py` relative to this
   `SKILL.md`, not relative to the user's repository.
   The helper validates content bindings and evaluates supplied evidence only; it does not attest or
   run tests, edit code, or call GitHub.
6. Interpret the result strictly:
   - `ready`: eligible to present for human review; it is not permission to publish or merge.
   - `revise`: use only the returned evidence and actionable critique for the next Codex-native edit.
   - `abstain`: stop claiming readiness and explain the missing evidence, uncertainty, or hard stop.
7. For change requests, perform at most two PRman-guided revision rounds unless the user explicitly
   chooses a different budget. For review-only requests, report revisions without applying them.
8. Before any GitHub mutation, read [references/safety.md](references/safety.md) and obtain explicit
   confirmation for the exact repository and write. PRman permits Draft PR preparation only.

## Scorers

The scorer is optional and replaceable. Without an authenticated production scorer, an exact
matching binding in the decision profile, and a trusted-executor evidence attestation, passing hard
gates still results in `abstain`; never substitute a fixture or static scorer. Test scorers always
force `abstain`. Read
[references/scorer-contract.md](references/scorer-contract.md) only when configuring, implementing,
or diagnosing a scorer provider.

Treat external Python entry-point scorers as fully trusted in-process code. Do not pass
`--allow-trusted-python-scorer` unless the user has explicitly placed that provider code within the
trusted execution boundary; prefer the authenticated local HTTP boundary for deployed scorers.

Do not train a scorer, download weights or datasets, or add training dependencies unless the user
separately requests that work.
