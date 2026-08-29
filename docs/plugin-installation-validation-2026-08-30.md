# Local Plugin installation validation — 2026-08-30

## Result

PRM-008 passed for the local personal-marketplace workflow. PRman installed as an enabled Codex
Plugin, resolved its bundled Skill and workflow helper from the installation cache, triggered both
explicitly and implicitly in fresh Codex tasks, stayed out of an unrelated Python question, and was
picked up at a new cache-busted version after uninstall and reinstall.

This validation did not access GitHub or authorize an external write. A controlled real-repository
Draft PR and CI run remains PRM-009.

## Scope and environment

- Repository revision: `fe363ec` (`feat: enforce PR confirmation workflow`)
- Plugin release version: `0.4.0`
- Codex CLI: `0.149.1`
- Marketplace: the default local `personal` marketplace
- Test tasks: ephemeral, read-only Codex tasks started from empty temporary directories outside the
  PRman repository
- Public transcript policy: user-specific home paths and task IDs are omitted; no credentials,
  repository tokens, or GitHub responses were captured

The cache-busted version `0.4.0+codex.validation-20260830` used below is the same `0.4.0` source with
local build metadata added only to prove that Codex discarded the old installation cache. It is not
a new release version.

## Acceptance record

| Check | Evidence | Result |
| --- | --- | --- |
| Install from a local marketplace | `codex plugin add prman@personal --json` returned `version: 0.4.0`; `codex plugin list --json` reported `installed: true` and `enabled: true` | Pass |
| Explicit invocation in a fresh task | A read-only task invoked `$prman`, loaded the installed Skill, reported PRman `0.4.0`, rejected a plain yes, and allowed only Draft PR publication | Pass |
| Implicit invocation for PR work | A task asked to find a mature Python CLI repository, fix a confirmed bug, and send a PR without naming PRman; Codex selected `prman:prman` `0.4.0` and stopped before the first GitHub write | Pass |
| No trigger for a generic code question | A task asking how to sort Python dictionaries answered only the Python question and did not mention PRman | Pass |
| Installed helper path resolution | The workflow wrapper ran from the Plugin cache and prepared the example packet with digest `6adb446856812f62d626c971d1091f629282a2e2795be80d2be2400019daa680` | Pass |
| Cache-busted reinstall | The local source changed from `0.4.0` to `0.4.0+codex.validation-20260830`; uninstall and reinstall created a matching new cache directory | Pass |
| New-task pickup after reinstall | A new read-only task reported the exact installed version `0.4.0+codex.validation-20260830` and retained the Draft-only, exact-confirmation boundary | Pass |

## Redacted representative transcript

Initial local installation:

```text
$ codex plugin add prman@personal --json
{
  "pluginId": "prman@personal",
  "version": "0.4.0",
  "installedPath": "$CODEX_HOME/plugins/cache/personal/prman/0.4.0"
}

$ codex plugin list --json
prman@personal  version=0.4.0  installed=true  enabled=true
```

Explicit fresh-task result:

```text
Workflow: PRman 0.4.0, the human-confirmed pull-request workflow.
Responsibilities: PRman sets gates; Codex executes, verifies, and reports.
Plain yes: No—it does not authorize a GitHub write.
Publication: Draft pull requests only.
```

Implicit fresh-task result:

```text
Installed workflow: prman:prman v0.4.0.
Stages: discover and qualify -> reproduce and scope -> implement and test ->
verify and assess -> prepare the exact confirmation packet -> publish -> follow CI.
Mandatory stop: immediately before the first GitHub write.
Plain yes: No.
Only allowed publication: a Draft pull request.
```

Negative routing result:

```text
Use sorted(items, key=lambda item: item["score"], reverse=True) to return a new
list ordered by score from highest to lowest; use items.sort(...) for an in-place sort.
```

Update and reinstall result:

```text
Updated plugin version: 0.4.0 -> 0.4.0+codex.validation-20260830

$ codex plugin remove prman@personal --json
removed: prman@personal

$ codex plugin add prman@personal --json
version: 0.4.0+codex.validation-20260830
installedPath: $CODEX_HOME/plugins/cache/personal/prman/0.4.0+codex.validation-20260830
```

Post-reinstall fresh-task result:

```text
Installed workflow: prman
Exact version: 0.4.0+codex.validation-20260830
No—a plain "yes" cannot authorize publication.
Only an explicitly confirmed Draft GitHub pull request may be published.
```

## Boundary of this result

This proves local Plugin packaging, discovery, routing, installed path resolution, and update-cache
behavior in fresh Codex tasks. It does not prove target-selection quality, correctness on an
unfamiliar repository, production scorer quality, the authenticity of supplied evidence, GitHub
permission handling, Draft PR creation, or CI repair behavior. Those claims remain open until the
controlled tests listed under PRM-009 and the production-scorer work are complete.
