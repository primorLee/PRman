from __future__ import annotations

import copy
import json
import re
import tomllib
import unittest

import yaml
from helpers import ROOT, decision_config, score_bundle, scorer_request
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

from prman.assessment import Assessment, AssessmentEngine
from prman.decision import DecisionConfig
from prman.models import GateResult, ScoreBundle
from prman.validation import ContractError
from prman.workflow import ConfirmationPacket, WorkflowRun, authorize_confirmation


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
        self.assertEqual(manifest["version"], "0.6.0")
        self.assertIn("Write", manifest["interface"]["capabilities"])
        self.assertLessEqual(len(manifest["interface"]["shortDescription"]), 30)
        prompts = manifest["interface"]["defaultPrompt"]
        self.assertIsInstance(prompts, list)
        self.assertLessEqual(len(prompts), 3)
        self.assertTrue(all(isinstance(prompt, str) and len(prompt) <= 128 for prompt in prompts))
        self.assertTrue((ROOT / "skills" / "prman" / "SKILL.md").is_file())

    def test_skill_declares_connected_github_dependency(self) -> None:
        metadata = yaml.safe_load(
            (ROOT / "skills" / "prman" / "agents" / "openai.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            metadata["dependencies"]["tools"],
            [
                {
                    "type": "mcp",
                    "value": "github",
                    "description": "GitHub MCP server",
                    "transport": "streamable_http",
                    "url": "https://api.githubcopilot.com/mcp/",
                }
            ],
        )
        self.assertTrue(metadata["policy"]["allow_implicit_invocation"])
        self.assertIn("$prman", metadata["interface"]["default_prompt"])

    def test_python_distribution_has_a_non_conflicting_name(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["name"], "prman-codex")
        self.assertEqual(list(project["project"]["scripts"]), ["prman-codex"])
        self.assertEqual(project["tool"]["setuptools"]["packages"], ["prman", "prman.scorers"])
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["version"], manifest["version"])

    def test_default_decision_requires_adversarial_review(self) -> None:
        self.assertEqual(
            decision_config().required_gates,
            ("scope", "secrets", "tests", "adversarial_review"),
        )

    def test_skill_has_no_scaffold_placeholders(self) -> None:
        skill = (ROOT / "skills" / "prman" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: prman", skill)
        self.assertNotIn("[TODO:", skill)
        self.assertIn("how many PRs they want", skill)
        self.assertIn("Multiple-PR sessions", skill)
        self.assertIn("references/goal-mode.md", skill)

        linked_references = set(re.findall(r"\]\((references/[^)]+)\)", skill))
        required_references = {
            "references/assessment-contract.md",
            "references/adversarial-review.md",
            "references/github-workflow.md",
            "references/goal-mode.md",
            "references/orchestration.md",
            "references/safety.md",
            "references/scorer-contract.md",
        }
        self.assertLessEqual(required_references, linked_references)
        for reference in linked_references:
            with self.subTest(reference=reference):
                self.assertTrue((ROOT / "skills" / "prman" / reference).is_file())

    def test_goal_mode_keeps_persistence_separate_from_write_authority(self) -> None:
        goal_mode = (ROOT / "skills" / "prman" / "references" / "goal-mode.md").read_text(
            encoding="utf-8"
        )
        for tool_name in ("get_goal", "create_goal", "update_goal"):
            with self.subTest(tool_name=tool_name):
                self.assertIn(f"`{tool_name}`", goal_mode)
        self.assertIn("Do not set `token_budget`", goal_mode)
        self.assertIn("A Goal provides persistence, not permission.", goal_mode)
        self.assertIn("CREATE DRAFT PR OWNER/REPO", goal_mode)

    def test_confirmation_packet_contract_is_draft_only_and_bounded(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "confirmation_packet.schema.json").read_text(encoding="utf-8")
        )
        packet = json.loads(
            (ROOT / "examples" / "confirmation-packet.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        validator.validate(packet)

        ready_packet = copy.deepcopy(packet)
        ready_packet["assessment"] = {
            "decision": "ready",
            "reason": "All bound gates and production readiness requirements passed.",
            "scorer": "production.example",
            "test_only": False,
            "attestation_verified": True,
            "override_acknowledgement_required": False,
        }
        ready_packet["approval"] = {
            "status": "pending",
            "prompt": "Reply exactly ‘CREATE DRAFT PR octo-org/widget’ to create this Draft PR.",
            "confirmation_phrase": "CREATE DRAFT PR octo-org/widget",
        }
        validator.validate(ready_packet)

        invalid_packets = []
        normal_pr = copy.deepcopy(packet)
        normal_pr["pull_request"]["draft"] = False
        invalid_packets.append(normal_pr)

        merge_write = copy.deepcopy(packet)
        merge_write["external_writes"].append("merge")
        invalid_packets.append(merge_write)

        excessive_ci_budget = copy.deepcopy(packet)
        excessive_ci_budget["ci_followup"]["max_fix_rounds"] = 3
        invalid_packets.append(excessive_ci_budget)

        hidden_abstention = copy.deepcopy(packet)
        hidden_abstention["assessment"]["override_acknowledgement_required"] = False
        invalid_packets.append(hidden_abstention)

        false_ready = copy.deepcopy(ready_packet)
        false_ready["assessment"]["scorer"] = None
        false_ready["assessment"]["attestation_verified"] = False
        invalid_packets.append(false_ready)

        test_only_ready = copy.deepcopy(ready_packet)
        test_only_ready["assessment"]["test_only"] = True
        invalid_packets.append(test_only_ready)

        missing_exact_diff = copy.deepcopy(packet)
        del missing_exact_diff["diff"]["patch"]
        invalid_packets.append(missing_exact_diff)

        missing_initial_write = copy.deepcopy(packet)
        missing_initial_write["external_writes"].remove("push_commits")
        invalid_packets.append(missing_initial_write)

        mismatched_ci_budget = copy.deepcopy(packet)
        mismatched_ci_budget["ci_followup"]["max_fix_rounds"] = 0
        invalid_packets.append(mismatched_ci_budget)

        inexact_confirmation = copy.deepcopy(packet)
        inexact_confirmation["approval"]["confirmation_phrase"] = "yes"
        invalid_packets.append(inexact_confirmation)

        verbose_confirmation = copy.deepcopy(packet)
        verbose_confirmation["approval"]["confirmation_phrase"] = (
            "CONFIRM DRAFT PR octo-org/widget codex/handle-empty-config ACKNOWLEDGE ABSTAIN"
        )
        invalid_packets.append(verbose_confirmation)

        for invalid_packet in invalid_packets:
            with self.subTest(invalid_packet=invalid_packet), self.assertRaises(ValidationError):
                validator.validate(invalid_packet)

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
        confirmation_value = json.loads(
            (ROOT / "examples" / "confirmation-packet.json").read_text(encoding="utf-8")
        )
        packet = ConfirmationPacket.from_dict(confirmation_value)
        authorization = authorize_confirmation(
            packet,
            expected_packet_digest=packet.packet_digest,
            response=packet.confirmation_phrase,
        )
        values = {
            "assessment.schema.json": assessment_value,
            "decision_config.schema.json": decision_config().as_dict(),
            "scorer_request.schema.json": scorer_request().as_dict(),
            "score_bundle.schema.json": score_bundle().as_dict(),
            "assessment_result.schema.json": AssessmentEngine(decision_config())
            .run(Assessment.from_dict(assessment_value))
            .as_dict(),
            "confirmation_packet.schema.json": confirmation_value,
            "confirmation_check.schema.json": packet.preparation(),
            "write_authorization.schema.json": authorization.as_dict(),
            "workflow_run.schema.json": WorkflowRun.start(authorization).as_dict(),
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

    def test_schema_and_runtime_both_reject_invalid_adversarial_review_pass(self) -> None:
        value = json.loads((ROOT / "examples" / "assessment.json").read_text(encoding="utf-8"))
        review_index, review = next(
            (index, gate)
            for index, gate in enumerate(value["candidates"][0]["gates"])
            if gate["name"] == "adversarial_review"
        )
        schemas = _schemas()
        validator = Draft202012Validator(
            schemas["assessment.schema.json"],
            registry=_registry(schemas),
            format_checker=FormatChecker(),
        )

        invalid_reviews = []
        wrong_code = copy.deepcopy(review)
        wrong_code["code"] = "PASS"
        invalid_reviews.append(wrong_code)

        command_only = copy.deepcopy(review)
        command_only["evidence"].update(
            {"source": "command", "command": ["review-script"], "exit_code": 0}
        )
        invalid_reviews.append(command_only)

        for invalid_review in invalid_reviews:
            invalid_assessment = copy.deepcopy(value)
            invalid_assessment["candidates"][0]["gates"][review_index] = invalid_review
            with self.subTest(code=invalid_review["code"]), self.assertRaises(ValidationError):
                validator.validate(invalid_assessment)
            with self.assertRaises(ContractError):
                Assessment.from_dict(invalid_assessment)

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
        milestones = yaml.safe_load((ROOT / "milestones.yaml").read_text(encoding="utf-8"))
        milestone_names = {
            f"{milestone['id']} {milestone['title']}" for milestone in milestones["milestones"]
        }
        identifiers = [issue["external_id"] for issue in issues]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        known = set(identifiers)
        for issue in issues:
            self.assertLessEqual(set(issue["depends_on"]), known)
            self.assertIn(issue["milestone"], milestone_names)


if __name__ == "__main__":
    unittest.main()
