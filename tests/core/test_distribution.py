from __future__ import annotations

import copy
import json
import tomllib
import unittest

from helpers import ROOT, decision_config, score_bundle, scorer_request
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

from prman.assessment import Assessment, AssessmentEngine
from prman.decision import DecisionConfig
from prman.models import GateResult, ScoreBundle
from prman.validation import ContractError


def _schemas() -> dict[str, dict[str, object]]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "schemas").glob("*.schema.json")
    }


def _registry(schemas: dict[str, dict[str, object]]) -> Registry:
    registry = Registry()
    for schema in schemas.values():
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


class DistributionTests(unittest.TestCase):
    def test_plugin_manifest_names_skill_directory(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "prman")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertLessEqual(len(manifest["interface"]["shortDescription"]), 30)
        prompts = manifest["interface"]["defaultPrompt"]
        self.assertIsInstance(prompts, list)
        self.assertLessEqual(len(prompts), 3)
        self.assertTrue(all(isinstance(prompt, str) and len(prompt) <= 128 for prompt in prompts))
        self.assertTrue((ROOT / "skills" / "prman" / "SKILL.md").is_file())

    def test_python_distribution_has_a_non_conflicting_name(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["name"], "prman-codex")
        self.assertEqual(list(project["project"]["scripts"]), ["prman-codex"])
        self.assertEqual(project["tool"]["setuptools"]["packages"], ["prman", "prman.scorers"])
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["version"], manifest["version"])

    def test_skill_has_no_scaffold_placeholders(self) -> None:
        skill = (ROOT / "skills" / "prman" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: prman", skill)
        self.assertNotIn("[TODO:", skill)

    def test_security_review_is_archived(self) -> None:
        review = ROOT / "docs" / "security-review-2026-08-29.md"
        self.assertTrue(review.is_file())
        self.assertIn("严重：计算了 LCB", review.read_text(encoding="utf-8"))

    def test_public_json_schemas_are_valid_and_accept_runtime_outputs(self) -> None:
        schemas = _schemas()
        registry = _registry(schemas)
        for name, schema in schemas.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

        assessment_value = json.loads(
            (ROOT / "examples" / "assessment.json").read_text(encoding="utf-8")
        )
        values = {
            "assessment.schema.json": assessment_value,
            "decision_config.schema.json": decision_config().as_dict(),
            "scorer_request.schema.json": scorer_request().as_dict(),
            "score_bundle.schema.json": score_bundle().as_dict(),
            "assessment_result.schema.json": AssessmentEngine(decision_config())
            .run(Assessment.from_dict(assessment_value))
            .as_dict(),
        }
        for name, value in values.items():
            with self.subTest(instance=name):
                Draft202012Validator(
                    schemas[name], registry=registry, format_checker=FormatChecker()
                ).validate(value)

    def test_schema_and_runtime_both_reject_single_mode_with_two_candidates(self) -> None:
        value = json.loads((ROOT / "examples" / "assessment.json").read_text(encoding="utf-8"))
        value["candidates"].append(copy.deepcopy(value["candidates"][0]))
        schemas = _schemas()
        validator = Draft202012Validator(
            schemas["assessment.schema.json"],
            registry=_registry(schemas),
            format_checker=FormatChecker(),
        )
        with self.assertRaises(ValidationError):
            validator.validate(value)
        with self.assertRaises(ContractError):
            Assessment.from_dict(value)

    def test_schema_and_runtime_both_reject_pass_as_recoverable(self) -> None:
        value = json.loads((ROOT / "examples" / "assessment.json").read_text(encoding="utf-8"))
        gate = value["candidates"][0]["gates"][0]
        gate["recoverable"] = True
        gate["actionable"] = "retry"
        schemas = _schemas()
        validator = Draft202012Validator(
            schemas["assessment.schema.json"],
            registry=_registry(schemas),
            format_checker=FormatChecker(),
        )
        with self.assertRaises(ValidationError):
            validator.validate(value)
        with self.assertRaises(ContractError):
            GateResult.from_dict(gate)

    def test_schema_and_runtime_both_reject_duplicate_score_criteria(self) -> None:
        value = score_bundle().as_dict()
        value["scores"][1]["criterion"] = "correctness"
        schemas = _schemas()
        validator = Draft202012Validator(
            schemas["score_bundle.schema.json"], registry=_registry(schemas)
        )
        with self.assertRaises(ValidationError):
            validator.validate(value)
        with self.assertRaises(ContractError):
            ScoreBundle.from_dict(value)

    def test_schema_and_runtime_both_require_minima_for_every_criterion(self) -> None:
        value = decision_config().as_dict()
        value["critical_min"] = {}
        value["soft_min"] = {}
        schemas = _schemas()
        validator = Draft202012Validator(
            schemas["decision_config.schema.json"], registry=_registry(schemas)
        )
        with self.assertRaises(ValidationError):
            validator.validate(value)
        with self.assertRaises(ContractError):
            DecisionConfig.from_mapping(value)

    def test_result_schema_rejects_ready_without_verified_attestation(self) -> None:
        assessment_value = json.loads(
            (ROOT / "examples" / "assessment.json").read_text(encoding="utf-8")
        )
        value = (
            AssessmentEngine(decision_config())
            .run(Assessment.from_dict(assessment_value))
            .as_dict()
        )
        value["selection"] = {
            "decision": "ready",
            "candidate_id": assessment_value["candidates"][0]["candidate_id"],
            "margin": None,
            "reason": "forged downstream readiness",
        }
        schemas = _schemas()
        validator = Draft202012Validator(
            schemas["assessment_result.schema.json"], registry=_registry(schemas)
        )
        with self.assertRaises(ValidationError):
            validator.validate(value)

    def test_github_roadmap_is_valid_jsonl_with_resolved_dependencies(self) -> None:
        issues = [
            json.loads(line)
            for line in (ROOT / "github_issues.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        identifiers = [issue["external_id"] for issue in issues]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        known = set(identifiers)
        for issue in issues:
            self.assertLessEqual(set(issue["depends_on"]), known)


if __name__ == "__main__":
    unittest.main()
