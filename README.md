# PRman

![PRman social cover](docs/assets/prman-social-preview.png)

PRman helps ordinary developers make useful pull requests to well-known open-source projects.

You tell Codex what kind of project you want to contribute to. PRman finds one suitable issue,
Codex makes and tests the change, and you review a simple preview. Nothing is sent to GitHub until
you confirm it.

## What it does

~~~text
You: “Help me contribute to a well-known Python project.”
                         |
                         v
PRman finds one active project and a small, unclaimed issue
                         |
                         v
Codex reads the project rules, makes the change, and runs the tests
                         |
                         v
PRman shows a simple contribution preview and the full diff
                         |
                         v
You confirm: CREATE DRAFT PR owner/repo
                         |
                         v
PRman creates a Draft PR, follows CI, and reports the result
~~~

You do not need to understand GitHub search syntax, scoring systems, JSON packets, or PR workflow
states. PRman keeps those details in the background.

## What you can ask

~~~text
Help me find a small issue in a well-known Python project and make a PR.
~~~

~~~text
I want to contribute to the React ecosystem. Find something useful that is small enough to finish.
~~~

~~~text
Help me fix this GitHub issue and prepare the PR.
~~~

If the request is broad, PRman chooses one good target automatically. It prefers a recognised,
active project with a contribution guide, an open and unclaimed issue, no competing PR, a manageable
scope, and tests that can verify the change. It avoids abandoned projects, public security fixes,
bulk PRs, and cosmetic changes with little value.

## What you see before anything is sent

PRman shows a short contribution preview:

~~~text
Repository: owner/project
Task: Fix empty configuration handling (#42)
Why this one: Active project, clear unclaimed issue, and a focused testable fix.
Changed: 2 files — handle empty input and add a regression test.
Tests: 12 passed.
Risk: No known failing checks. Extra automatic quality score is unavailable.
Draft PR: Fix empty configuration handling

Review the full diff, then reply:
CREATE DRAFT PR owner/project
~~~

That short phrase authorizes only the previewed Draft PR. Internally, PRman binds it to the exact
repository, base commit, branch, diff, PR text, and CI repair limit. If any of those materially
changes before publication, PRman asks again.

## What version 0.5.0 implements

- A Codex Skill and installable Plugin for one end-to-end open-source contribution.
- Read-only discovery of one well-known, active, contribution-friendly project and suitable issue.
- Inspection of project instructions, contribution and security policies, duplicate work, CI rules,
  and the exact base commit.
- Codex-native implementation and execution of the project's own tests and checks.
- Internal diff, evidence, and quality binding without exposing technical packet details by default.
- A simple user-facing preview with the selected task, changes, tests, risks, Draft PR title, and
  reviewable diff.
- The short repository-bound confirmation phrase `CREATE DRAFT PR owner/repo`.
- Draft-only publication. PRman never merges, enables auto-merge, force-pushes, or writes directly
  to the default branch.
- CI monitoring and at most two same-task repair rounds by default.
- Executable local contracts that reject stale confirmation, changed targets, unsafe writes,
  out-of-scope repairs, and CI results from the wrong commit.

PRman uses Codex's existing coding, shell, repository, and connected GitHub tools. It does not store
a GitHub token or create a second coding agent.

## Current limits

- Version 0.5.0 is pre-alpha. The Skill, local safety contracts, and automated tests work, but this
  simplified flow still needs a fresh installed-Plugin test and a complete contribution run against
  a controlled real repository.
- PRman runs inside the active Codex task; it is not a hosted service or background bot.
- It handles one contribution at a time, not bulk outreach or mass PR creation.
- It does not assign reviewers, post comments, approve, merge, change repository settings, or make a
  private security report public.
- No production quality scorer is bundled. Repository checks still run, and the preview plainly says
  when the optional extra quality score is unavailable.
- A maintainer may still request changes, reject the PR, or require a CLA or other human action.

## How safety works in the background

PRman keeps an internal packet containing the exact target, base commit, diff, test results, Draft PR
text, planned GitHub writes, and CI repair budget. A local helper hashes and validates that packet.
The user sees a plain-language preview, while the helper ensures the later GitHub write still matches
what was previewed.

The assessment core checks required gates such as scope, secrets, and tests before optional scoring.
A test scorer can never claim production readiness, and a missing production scorer is reported as
an uncertainty rather than silently treated as a pass. See [architecture](docs/architecture.md),
[threat model](docs/threat-model.md), and [implementation status](docs/IMPLEMENTATION_STATUS.md) for
the technical boundary.

## Skill and Plugin

The Skill contains the contribution workflow. The Plugin makes the Skill installable and declares
the connected GitHub tool it needs. The Python distribution and command are named `prman-codex` to
avoid the unrelated existing PyPI project named `prman`.

PRman follows the official OpenAI documentation for
[building skills](https://learn.chatgpt.com/docs/build-skills),
[building plugins](https://learn.chatgpt.com/docs/build-plugins), and
[agent approvals](https://learn.chatgpt.com/docs/agent-approvals-security).

## Development

PRman supports Python 3.11 and 3.12 and has no runtime dependencies.

~~~bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make check PYTHON=python
make demo PYTHON=python
~~~

The demo uses a test-only scorer and cannot claim production readiness:

~~~bash
python skills/prman/scripts/assess.py \
  --input examples/assessment.json \
  --scorer-config configs/scorer/fixture.example.json \
  --allow-test-scorer
~~~

To validate an internal confirmation packet:

~~~bash
python skills/prman/scripts/workflow.py confirmation prepare \
  --input examples/confirmation-packet.json
~~~

Visual assets and their intended use are listed in
[docs/visual-assets.md](docs/visual-assets.md).

## Repository map

- `.codex-plugin/`: installable Plugin metadata.
- `skills/prman/`: contribution workflow, safety rules, and bundled helpers.
- `src/prman/`: deterministic assessment, authorization, and workflow-state code.
- `schemas/`: machine-readable assessment and workflow contracts.
- `configs/`: quality-decision and scorer examples.
- `examples/`: assessment and internal confirmation examples.
- `docs/assets/`: public diagrams, brand assets, and separated mockups.
- `tests/core/`: unit, safety, distribution, CLI, Schema, and Skill tests.

## License

PRman is available under the [Apache License 2.0](LICENSE). The canonical repository is
[primorLee/PRman](https://github.com/primorLee/PRman).
