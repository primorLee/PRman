# Visual assets

This catalog separates current-release documentation from illustrative design work. A mockup must
not be presented as runtime evidence or as proof that an integration has been validated.

## Public diagrams and brand references

| Asset | Intended use | Accuracy status |
| --- | --- | --- |
| [`prman-pipeline-trust-boundaries.png`](assets/prman-pipeline-trust-boundaries.png) | README quality-gate and trust-boundary overview | Represents the assessment stage inside the larger discovery-to-CI workflow. PRman ships the core and authenticated HTTP client, but not the pictured trusted evidence executor or production scorer service. The no-in-process-production-scorer statement is deployment guidance; trusted Python providers remain available by explicit opt-in. |
| [`prman-social-preview.png`](assets/prman-social-preview.png) | README cover, optional GitHub social-preview upload, and release announcements | Marketing artwork for the pre-alpha quality layer. It is already visible in the README. GitHub's link-card preview is a separate repository setting that still requires an owner to upload this file there. |
| [`prman-brand-board.png`](assets/prman-brand-board.png) | Brand direction and export reference | A composite raster concept board, not a set of production-ready individual logo, icon, favicon, or dark-mode files. |
| [`prman-overview.png`](assets/prman-overview.png) | Archived broad product concept | No longer used as the README architecture source. Scorer labels and ecosystem logos are illustrative, not bundled integrations, calibrated providers, partnerships, or endorsements. |

## Mockups that are not validation evidence

| Asset | Intended future use | Why it is not a current product screenshot |
| --- | --- | --- |
| [`prman-local-run-mockup.png`](assets/mockups/prman-local-run-mockup.png) | Example CLI walkthrough after regeneration | The displayed `1.0` result shape, log lines, gate names, timestamp, output path, and singular `evaluation` object do not match the current `prman-assessment-result/1.1` CLI output. Regenerate it from a captured `0.4.0` run before publishing it as evidence. |
| [`prman-plugin-invocation-mockup.png`](assets/mockups/prman-plugin-invocation-mockup.png) | Historical installation and `$prman` invocation concept | The image explicitly depicts a proposed UI, a mock result, and version `0.1.0`. PRM-008 now has a real text transcript in [`plugin-installation-validation-2026-08-30.md`](plugin-installation-validation-2026-08-30.md), but this old image remains a mockup and must not be presented as its screenshot. |

## Publication rule

Use mockups only in design discussions with their status visible. The PRM-008 text record does not
turn the old invocation artwork into a runtime screenshot; replace it with a real capture if an
image-based installation guide is published.
