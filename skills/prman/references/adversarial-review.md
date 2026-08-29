# Adversarial maintainer review

Read this reference after the final local edit and repository checks, and again after every repair.
This is a deliberate second pass in which Codex acts like a skeptical project maintainer looking for
a concrete reason to reject the proposed PR. It is not a claim that an independent human reviewed
the change.

## Review inputs

Review the selected issue and linked discussion, applicable repository instructions, complete diff,
changed-file list, working-tree status, verification commands and logs, and any public API,
dependency, security, performance, compatibility, generated-file, or documentation impact. Use the
exact final candidate diff rather than a summary or an earlier revision.

## Try to reject the change

Answer each question with evidence:

1. Does the diff solve the actual issue, including important edge cases, or only the easiest visible
   example?
2. Could it regress existing behavior, compatibility, security, performance, accessibility, or data
   handling?
3. Do the tests fail before the fix when practical, pass after it, and exercise the changed behavior
   rather than merely executing nearby code?
4. Does the change follow repository instructions, architecture, naming, style, generated-file,
   changelog, sign-off, and PR-template requirements?
5. Are there accidental files, secrets, debug output, broad refactors, new dependencies, unrelated
   cleanup, or claims not supported by the diff and test results?
6. Is the issue still open and available, with no competing PR, and is the contribution useful
   enough that a maintainer would reasonably spend time reviewing it?
7. What is the strongest likely maintainer objection? Is it resolved by evidence, or does it require
   another edit, a narrower target, abandonment, or explicit user input?

Do not pass the review merely because tests are green or the diff is small. Do not fail a small diff
merely for being small: a focused one-line bug fix with real impact and a regression test can be
exactly right.

## Resolve findings and record the gate

Keep a concise review note in temporary internal storage. Bind it to the current candidate ID and
record the checklist conclusions, strongest objection, resolution, and retained-note SHA-256.

- Use `status: pass` and code `ADVERSARIAL_REVIEW_PASSED` only when no credible objection remains.
  Passing evidence must use source `inspection` or `service`.
- Use a recoverable failure and code `REVIEW_CHANGES_REQUIRED` when a focused edit can resolve the
  finding. Include concrete actionable advice.
- Use a non-recoverable failure such as `LOW_VALUE_CONTRIBUTION`, `DUPLICATE_OR_UNWANTED_WORK`, or
  `ISSUE_NO_LONGER_AVAILABLE` when the target itself should be abandoned.
- Use `status: unknown` and code `REVIEW_INCOMPLETE` when required context or evidence is missing.

For a recoverable finding, edit the change, rerun affected repository checks, recompute the candidate
ID, and perform the entire adversarial review again. Never reuse a review record across different
diffs. A missing, failed, or incomplete `adversarial_review` gate blocks the normal Draft PR path.
