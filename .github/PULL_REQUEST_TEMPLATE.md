## Summary

## Verification

- [ ] `make check` passes
- [ ] `make demo` passes when packaging or CLI behavior changed
- [ ] New behavior has focused coverage under `tests/core/`
- [ ] No secrets, private data, model weights, or training data are included
- [ ] Scorer inputs contain no future outcome or identity fields
- [ ] Hard gates remain impossible to override with model scores
- [ ] `ready` still requires a separate human confirmation for a Draft PR

## Codex-native boundary

Describe any effect on the Skill, scorer contract, evidence integrity, authorization, or threat
model. Confirm that this change does not introduce a second coding or execution harness.
