from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

from prman.cli import main
from prman.validation import ContractError, sha256_text
from prman.workflow import (
    ConfirmationPacket,
    WorkflowRun,
    WriteAuthorization,
    authorize_confirmation,
)


def confirmation_value() -> dict[str, object]:
    return json.loads((ROOT / "examples" / "confirmation-packet.json").read_text(encoding="utf-8"))


def authorization() -> WriteAuthorization:
    packet = ConfirmationPacket.from_dict(confirmation_value())
    return authorize_confirmation(
        packet,
        expected_packet_digest=packet.packet_digest,
        response=packet.confirmation_phrase,
    )


class ConfirmationTests(unittest.TestCase):
    def test_packet_is_content_bound_and_starts_unauthorized(self) -> None:
        value = confirmation_value()
        packet = ConfirmationPacket.from_dict(value)
        self.assertEqual(packet.diff_sha256, sha256_text(value["diff"]["patch"]))
        preparation = packet.preparation()
        self.assertEqual(preparation["packet_digest"], packet.packet_digest)
        self.assertEqual(preparation["confirmation_phrase"], packet.confirmation_phrase)
        self.assertFalse(preparation["policy"]["external_write_authorized"])

    def test_exact_response_creates_a_scoped_roundtrippable_authorization(self) -> None:
        grant = authorization()
        self.assertTrue(grant.as_dict()["policy"]["external_write_authorized"])
        self.assertFalse(grant.as_dict()["policy"]["merge_authorized"])
        self.assertEqual(WriteAuthorization.from_dict(grant.as_dict()), grant)
        self.assertTrue(
            grant.allows_initial_write(
                "create_draft_pr",
                repository=grant.repository,
                base_branch=grant.base_branch,
                base_commit=grant.base_commit,
                head_repository=grant.head_repository,
                head_branch=grant.head_branch,
                diff_sha256=grant.initial_diff_sha256,
            )
        )
        self.assertFalse(
            grant.allows_initial_write(
                "merge",
                repository=grant.repository,
                base_branch=grant.base_branch,
                base_commit=grant.base_commit,
                head_repository=grant.head_repository,
                head_branch=grant.head_branch,
                diff_sha256=grant.initial_diff_sha256,
            )
        )

    def test_ready_packet_uses_a_target_phrase_without_an_acknowledgement_suffix(self) -> None:
        value = confirmation_value()
        value["assessment"] = {
            "decision": "ready",
            "reason": "All bound production readiness requirements passed.",
            "scorer": "production.example",
            "test_only": False,
            "attestation_verified": True,
            "override_acknowledgement_required": False,
        }
        phrase = "CONFIRM DRAFT PR octo-org/widget codex/handle-empty-config"
        value["approval"] = {
            "status": "pending",
            "prompt": f"Reply exactly ‘{phrase}’ to create this Draft PR.",
            "confirmation_phrase": phrase,
        }
        packet = ConfirmationPacket.from_dict(value)
        self.assertEqual(packet.confirmation_phrase, phrase)

    def test_upstream_route_without_repairs_is_valid_and_bounded(self) -> None:
        value = confirmation_value()
        value["head"]["repository"] = "octo-org/widget"
        value["head"]["fork_required"] = False
        value["external_writes"] = [
            "create_branch",
            "push_commits",
            "create_draft_pr",
        ]
        value["ci_followup"]["max_fix_rounds"] = 0
        value["ci_followup"]["publish_repairs"] = False
        phrase = value["approval"]["confirmation_phrase"]
        reason = value["assessment"]["reason"]
        value["approval"]["prompt"] = (
            f"Assessment result: {reason} Reply exactly ‘{phrase}’ to acknowledge that result "
            "and create this Draft PR without repair-write authority."
        )
        packet = ConfirmationPacket.from_dict(value)
        grant = authorize_confirmation(
            packet,
            expected_packet_digest=packet.packet_digest,
            response=packet.confirmation_phrase,
        )
        self.assertEqual(WriteAuthorization.from_dict(grant.as_dict()), grant)
        self.assertFalse(
            grant.allows_ci_repair(
                1,
                repository=grant.repository,
                head_repository=grant.head_repository,
                head_branch=grant.head_branch,
            )
        )
        self.assertFalse(
            grant.allows_initial_write(
                "create_draft_pr",
                repository="wrong/repository",
                base_branch=grant.base_branch,
                base_commit=grant.base_commit,
                head_repository=grant.head_repository,
                head_branch=grant.head_branch,
                diff_sha256=grant.initial_diff_sha256,
            )
        )

    def test_changed_packet_and_inexact_response_are_rejected(self) -> None:
        packet = ConfirmationPacket.from_dict(confirmation_value())
        with self.assertRaisesRegex(ContractError, "changed"):
            authorize_confirmation(
                packet,
                expected_packet_digest="0" * 64,
                response=packet.confirmation_phrase,
            )
        for response in (
            "yes",
            f" {packet.confirmation_phrase}",
            f"{packet.confirmation_phrase} ",
        ):
            with self.subTest(response=response), self.assertRaisesRegex(ContractError, "exactly"):
                authorize_confirmation(
                    packet,
                    expected_packet_digest=packet.packet_digest,
                    response=response,
                )

    def test_packet_contract_rejects_unsafe_or_inconsistent_plans(self) -> None:
        invalid_values: list[dict[str, object]] = []

        normal_pr = copy.deepcopy(confirmation_value())
        normal_pr["pull_request"]["draft"] = False
        invalid_values.append(normal_pr)

        stale_diff = copy.deepcopy(confirmation_value())
        stale_diff["diff"]["patch"] += "changed\n"
        invalid_values.append(stale_diff)

        default_branch = copy.deepcopy(confirmation_value())
        default_branch["head"]["branch"] = default_branch["base"]["branch"]
        default_branch["pull_request"]["head_branch"] = default_branch["base"]["branch"]
        invalid_values.append(default_branch)

        for branch in ("@", "codex/.hidden", "codex/topic.lock"):
            invalid_branch = copy.deepcopy(confirmation_value())
            invalid_branch["head"]["branch"] = branch
            invalid_branch["pull_request"]["head_branch"] = branch
            invalid_values.append(invalid_branch)

        missing_fork = copy.deepcopy(confirmation_value())
        missing_fork["external_writes"].remove("create_fork")
        invalid_values.append(missing_fork)

        hidden_update = copy.deepcopy(confirmation_value())
        hidden_update["external_writes"].remove("update_draft_pr")
        invalid_values.append(hidden_update)

        fake_ready = copy.deepcopy(confirmation_value())
        fake_ready["assessment"] = {
            "decision": "ready",
            "reason": "not actually production-ready",
            "scorer": None,
            "test_only": False,
            "attestation_verified": False,
            "override_acknowledgement_required": False,
        }
        invalid_values.append(fake_ready)

        hidden_phrase = copy.deepcopy(confirmation_value())
        hidden_phrase["approval"]["prompt"] = "Confirm this write."
        invalid_values.append(hidden_phrase)

        short_phrase = copy.deepcopy(confirmation_value())
        short_phrase["approval"]["prompt"] = "Reply exactly yes."
        short_phrase["approval"]["confirmation_phrase"] = "yes"
        invalid_values.append(short_phrase)

        hidden_non_ready_reason = copy.deepcopy(confirmation_value())
        hidden_non_ready_reason["approval"]["prompt"] = (
            f"Reply exactly {hidden_non_ready_reason['approval']['confirmation_phrase']}."
        )
        invalid_values.append(hidden_non_ready_reason)

        false_observation = copy.deepcopy(confirmation_value())
        false_observation["verification"][0]["status"] = "not_run"
        invalid_values.append(false_observation)

        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ContractError):
                ConfirmationPacket.from_dict(value)

    def test_tampered_authorization_cross_fields_are_rejected(self) -> None:
        value = authorization().as_dict()
        invalid_values: list[dict[str, object]] = []

        missing_initial_write = copy.deepcopy(value)
        missing_initial_write["external_writes"].remove("push_commits")
        invalid_values.append(missing_initial_write)

        default_branch = copy.deepcopy(value)
        default_branch["head"]["branch"] = default_branch["base"]["branch"]
        invalid_values.append(default_branch)

        missing_fork = copy.deepcopy(value)
        missing_fork["external_writes"].remove("create_fork")
        invalid_values.append(missing_fork)

        mismatched_ci_budget = copy.deepcopy(value)
        mismatched_ci_budget["ci_followup"]["max_fix_rounds"] = 0
        invalid_values.append(mismatched_ci_budget)

        wrong_phrase_digest = copy.deepcopy(value)
        wrong_phrase_digest["confirmation_phrase_digest"] = "0" * 64
        invalid_values.append(wrong_phrase_digest)

        for invalid_value in invalid_values:
            with self.subTest(value=invalid_value), self.assertRaises(ContractError):
                WriteAuthorization.from_dict(invalid_value)


class WorkflowRunTests(unittest.TestCase):
    def _open_draft(self) -> WorkflowRun:
        return WorkflowRun.start(authorization()).record_draft(
            url="https://github.com/octo-org/widget/pull/7",
            number=7,
            base_branch="main",
            base_commit="a" * 40,
            head_repository="contributor/widget",
            head_branch="codex/handle-empty-config",
            diff_sha256="cea1e19de362686f7fbfb351a58f5bd31a81b4bbe327e95961f7b6beb42537e9",
            head_commit="2" * 40,
            draft=True,
        )

    def test_passing_ci_completes_the_workflow(self) -> None:
        workflow = self._open_draft()
        self.assertEqual(workflow.state, "draft_open")
        completed = workflow.record_ci(
            status="passed",
            summary="All checks passed.",
            head_commit="2" * 40,
        )
        self.assertEqual(completed.state, "complete")
        self.assertEqual(WorkflowRun.from_dict(completed.as_dict()), completed)

    def test_two_repair_rounds_are_allowed_and_a_third_is_rejected(self) -> None:
        workflow = self._open_draft()
        for round_number, marker in ((1, "3"), (2, "4")):
            workflow = workflow.record_ci(
                status="failed",
                summary=f"CI failed in round {round_number}.",
                head_commit=workflow.pr_head_commit or "",
            )
            workflow = workflow.begin_repair()
            self.assertEqual(workflow.repair_rounds_used, round_number)
            workflow = workflow.record_update(
                diff_sha256=marker * 64,
                head_commit=marker * 40,
                in_scope=True,
            )
            self.assertEqual(workflow.state, "draft_open")

        workflow = workflow.record_ci(
            status="failed",
            summary="CI still fails.",
            head_commit="4" * 40,
        )
        with self.assertRaisesRegex(ContractError, "exhausted"):
            workflow.begin_repair()

    def test_wrong_commit_and_out_of_scope_update_are_rejected(self) -> None:
        workflow = self._open_draft()
        with self.assertRaisesRegex(ContractError, "head commit"):
            workflow.record_ci(status="failed", summary="wrong", head_commit="9" * 40)
        failed = workflow.record_ci(
            status="failed",
            summary="Tests failed.",
            head_commit="2" * 40,
        )
        repairing = failed.begin_repair()
        with self.assertRaisesRegex(ContractError, "new confirmation"):
            repairing.record_update(
                diff_sha256="3" * 64,
                head_commit="3" * 40,
                in_scope=False,
            )
        with self.assertRaisesRegex(ContractError, "newly assessed"):
            repairing.record_update(
                diff_sha256=repairing.current_diff_sha256,
                head_commit="3" * 40,
                in_scope=True,
            )

    def test_normal_pr_cannot_be_recorded(self) -> None:
        with self.assertRaisesRegex(ContractError, "only a Draft"):
            WorkflowRun.start(authorization()).record_draft(
                url="https://github.com/octo-org/widget/pull/7",
                number=7,
                base_branch="main",
                base_commit="a" * 40,
                head_repository="contributor/widget",
                head_branch="codex/handle-empty-config",
                diff_sha256=("cea1e19de362686f7fbfb351a58f5bd31a81b4bbe327e95961f7b6beb42537e9"),
                head_commit="2" * 40,
                draft=False,
            )

    def test_draft_url_must_match_the_authorized_repository_and_number(self) -> None:
        workflow = WorkflowRun.start(authorization())
        for url in (
            "https://github.com/other/widget/pull/7",
            "https://github.com/octo-org/widget/pull/8",
            "https://example.com/octo-org/widget/pull/7",
        ):
            with self.subTest(url=url), self.assertRaisesRegex(ContractError, "canonical GitHub"):
                workflow.record_draft(
                    url=url,
                    number=7,
                    base_branch="main",
                    base_commit="a" * 40,
                    head_repository="contributor/widget",
                    head_branch="codex/handle-empty-config",
                    diff_sha256=(
                        "cea1e19de362686f7fbfb351a58f5bd31a81b4bbe327e95961f7b6beb42537e9"
                    ),
                    head_commit="2" * 40,
                    draft=True,
                )

    def test_draft_observation_must_match_the_authorized_route_and_diff(self) -> None:
        workflow = WorkflowRun.start(authorization())
        valid = {
            "url": "https://github.com/octo-org/widget/pull/7",
            "number": 7,
            "base_branch": "main",
            "base_commit": "a" * 40,
            "head_repository": "contributor/widget",
            "head_branch": "codex/handle-empty-config",
            "diff_sha256": ("cea1e19de362686f7fbfb351a58f5bd31a81b4bbe327e95961f7b6beb42537e9"),
            "head_commit": "2" * 40,
            "draft": True,
        }
        mismatches = {
            "base_branch": "develop",
            "base_commit": "b" * 40,
            "head_repository": "other/widget",
            "head_branch": "codex/other-change",
            "diff_sha256": "3" * 64,
        }
        for field, value in mismatches.items():
            observed = dict(valid)
            observed[field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ContractError, "does not permit"),
            ):
                workflow.record_draft(**observed)

    def test_roundtripped_ci_must_belong_to_the_current_pr_commit(self) -> None:
        completed = self._open_draft().record_ci(
            status="passed",
            summary="All checks passed.",
            head_commit="2" * 40,
        )
        value = completed.as_dict()
        value["last_ci"]["head_commit"] = "3" * 40
        with self.assertRaisesRegex(ContractError, "current Draft PR"):
            WorkflowRun.from_dict(value)

    def test_roundtripped_diff_cannot_change_before_a_repair(self) -> None:
        value = self._open_draft().as_dict()
        value["current_diff_sha256"] = "3" * 64
        with self.assertRaisesRegex(ContractError, "without a repair"):
            WorkflowRun.from_dict(value)


class WorkflowCliTests(unittest.TestCase):
    def test_cli_prepares_and_authorizes_exact_packet(self) -> None:
        packet_path = ROOT / "examples" / "confirmation-packet.json"
        prepared_output = io.StringIO()
        with contextlib.redirect_stdout(prepared_output):
            status = main(["confirmation", "prepare", "--input", str(packet_path)])
        self.assertEqual(status, 0)
        prepared = json.loads(prepared_output.getvalue())

        authorized_output = io.StringIO()
        with contextlib.redirect_stdout(authorized_output):
            status = main(
                [
                    "confirmation",
                    "authorize",
                    "--input",
                    str(packet_path),
                    "--expected-packet-digest",
                    prepared["packet_digest"],
                    "--response",
                    prepared["confirmation_phrase"],
                ]
            )
        self.assertEqual(status, 0)
        grant = json.loads(authorized_output.getvalue())
        self.assertTrue(grant["policy"]["external_write_authorized"])

    def test_cli_persists_a_complete_workflow_run(self) -> None:
        grant = authorization()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authorization_path = root / "authorization.json"
            workflow_path = root / "workflow.json"
            authorization_path.write_text(json.dumps(grant.as_dict()), encoding="utf-8")

            self.assertEqual(
                main(
                    [
                        "workflow",
                        "begin",
                        "--authorization",
                        str(authorization_path),
                        "--output",
                        str(workflow_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "workflow",
                        "record-draft",
                        "--input",
                        str(workflow_path),
                        "--url",
                        "https://github.com/octo-org/widget/pull/7",
                        "--number",
                        "7",
                        "--base-branch",
                        grant.base_branch,
                        "--base-commit",
                        grant.base_commit,
                        "--head-repository",
                        grant.head_repository,
                        "--head-branch",
                        grant.head_branch,
                        "--diff-sha256",
                        grant.initial_diff_sha256,
                        "--head-commit",
                        "2" * 40,
                        "--draft",
                        "--output",
                        str(workflow_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "workflow",
                        "record-ci",
                        "--input",
                        str(workflow_path),
                        "--status",
                        "passed",
                        "--summary",
                        "All checks passed.",
                        "--head-commit",
                        "2" * 40,
                        "--output",
                        str(workflow_path),
                    ]
                ),
                0,
            )
            workflow = WorkflowRun.from_dict(json.loads(workflow_path.read_text(encoding="utf-8")))
        self.assertEqual(workflow.state, "complete")


if __name__ == "__main__":
    unittest.main()
