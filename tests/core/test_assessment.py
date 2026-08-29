from __future__ import annotations

import hashlib
import hmac
import unittest
from unittest import mock

from helpers import (
    ATTESTATION_KEY_ID,
    ATTESTATION_SECRET,
    ATTESTATION_SECRET_ENV,
    BASE_COMMIT,
    CANDIDATE_DIFF,
    CANDIDATE_ID,
    REPOSITORY_ID,
    TASK,
    TASK_DIGEST,
    TEST_PROVIDER,
    decision_config,
    gate,
    required_gates,
    score_bundle,
)

from prman.assessment import Assessment, AssessmentEngine
from prman.models import GateResult
from prman.scorers.builtin import StaticScorer
from prman.validation import ContractError, canonical_json_bytes, sha256_text


def assessment_value() -> dict[str, object]:
    return {
        "schema_version": "prman-assessment/1.1",
        "mode": "single",
        "context": {
            "repository_id": REPOSITORY_ID,
            "base_commit": BASE_COMMIT,
            "task": TASK,
            "task_digest": TASK_DIGEST,
            "repository_rules": ["Keep changes focused."],
        },
        "attestation": None,
        "candidates": [
            {
                "candidate_id": CANDIDATE_ID,
                "diff": CANDIDATE_DIFF,
                "truncation_ratio": 0,
                "gates": [gate.as_dict() for gate in required_gates()],
            }
        ],
    }


class AssessmentTests(unittest.TestCase):
    def test_no_production_scorer_fails_closed(self) -> None:
        assessment = Assessment.from_dict(assessment_value())
        result = AssessmentEngine(decision_config()).run(assessment)
        rendered = result.as_dict()
        self.assertEqual(result.selection.decision, "abstain")
        self.assertFalse(rendered["test_only"])
        self.assertEqual(result.scorer_error, "not_configured")
        self.assertEqual(
            result.evaluations[0].aggregate.reasons,
            ("scorer_unavailable:not_configured",),
        )
        self.assertEqual(rendered["repository_id"], REPOSITORY_ID)
        self.assertEqual(rendered["base_commit"], BASE_COMMIT)
        self.assertEqual(rendered["task_digest"], TASK_DIGEST)
        self.assertEqual(
            rendered["policy"],
            {
                "human_confirmation_required": True,
                "draft_only": True,
                "external_write_authorized": False,
            },
        )

    def test_single_mode_rejects_multiple_candidates(self) -> None:
        value = assessment_value()
        value["candidates"] = [*value["candidates"], *value["candidates"]]
        with self.assertRaisesRegex(ContractError, "exactly one"):
            Assessment.from_dict(value)

    def test_candidate_id_must_hash_the_supplied_diff(self) -> None:
        value = assessment_value()
        value["candidates"][0]["diff"] = "different diff"
        with self.assertRaisesRegex(ContractError, "does not match diff"):
            Assessment.from_dict(value)

    def test_gate_evidence_must_bind_to_candidate(self) -> None:
        value = assessment_value()
        value["candidates"][0]["gates"][0]["evidence"]["candidate_id"] = "b" * 64
        with self.assertRaisesRegex(ContractError, "evidence candidate_id mismatch"):
            Assessment.from_dict(value)

    def test_passing_adversarial_review_rejects_command_only_evidence(self) -> None:
        value = gate("adversarial_review").as_dict()
        value["evidence"].update(
            {
                "source": "command",
                "command": ["review-script"],
                "exit_code": 0,
            }
        )
        with self.assertRaisesRegex(ContractError, "inspection or service"):
            GateResult.from_dict(value, path="gate")

    def test_passing_adversarial_review_rejects_generic_pass_code(self) -> None:
        value = gate("adversarial_review").as_dict()
        value["code"] = "PASS"
        with self.assertRaisesRegex(ContractError, "ADVERSARIAL_REVIEW_PASSED"):
            GateResult.from_dict(value, path="gate")

    def test_task_digest_must_hash_shared_task(self) -> None:
        value = assessment_value()
        value["context"]["task"] = "different task"
        with self.assertRaisesRegex(ContractError, "task_digest"):
            Assessment.from_dict(value)

    def test_scorer_runtime_failure_becomes_structured_abstain(self) -> None:
        class FailingScorer:
            metadata = TEST_PROVIDER

            def score(self, request):
                del request
                raise RuntimeError("secret-bearing provider message")

        assessment = Assessment.from_dict(assessment_value())
        result = AssessmentEngine(decision_config(bind_provider=True), FailingScorer()).run(
            assessment
        )
        self.assertEqual(result.selection.decision, "abstain")
        self.assertEqual(result.scorer_error, "runtime_error")
        self.assertEqual(
            result.evaluations[0].aggregate.reasons,
            ("scorer_unavailable:runtime_error",),
        )
        self.assertNotIn("secret-bearing", str(result.as_dict()))

    def test_scorer_cannot_mutate_generated_request(self) -> None:
        class MutatingScorer:
            metadata = TEST_PROVIDER

            def score(self, request):
                object.__setattr__(request, "task", "mutated")
                return score_bundle()

        assessment = Assessment.from_dict(assessment_value())
        result = AssessmentEngine(decision_config(bind_provider=True), MutatingScorer()).run(
            assessment
        )
        self.assertEqual(result.selection.decision, "abstain")
        self.assertEqual(result.scorer_error, "contract_error")

    def test_unbound_production_provider_fails_closed_without_calling_it(self) -> None:
        class UnexpectedScorer:
            metadata = TEST_PROVIDER

            def score(self, request):
                raise AssertionError(f"must not score {request.candidate_id}")

        result = AssessmentEngine(decision_config(), UnexpectedScorer()).run(
            Assessment.from_dict(assessment_value())
        )
        self.assertEqual(result.scorer_error, "provider_not_bound_to_decision_config")
        self.assertEqual(result.selection.decision, "abstain")

    def test_unattested_evidence_cannot_produce_ready(self) -> None:
        class PassingScorer:
            metadata = TEST_PROVIDER

            def score(self, request):
                return score_bundle(candidate_id=request.candidate_id, diff=request.diff)

        result = AssessmentEngine(decision_config(bind_provider=True), PassingScorer()).run(
            Assessment.from_dict(assessment_value())
        )
        self.assertEqual(result.selection.decision, "abstain")
        self.assertEqual(result.selection.reason, "evidence_attestation:not_configured")
        self.assertFalse(result.evidence_attestation.verified)

    def test_valid_trusted_executor_attestation_allows_production_ready(self) -> None:
        class PassingScorer:
            metadata = TEST_PROVIDER

            def score(self, request):
                return score_bundle(candidate_id=request.candidate_id, diff=request.diff)

        value = assessment_value()
        unsigned = Assessment.from_dict(value)
        signature = hmac.new(
            ATTESTATION_SECRET.encode(),
            b"prman-evidence-v1\0" + canonical_json_bytes(unsigned.attestation_payload()),
            hashlib.sha256,
        ).hexdigest()
        value["attestation"] = {
            "scheme": "hmac-sha256",
            "key_id": ATTESTATION_KEY_ID,
            "signature": signature,
        }
        with mock.patch.dict(
            "os.environ", {ATTESTATION_SECRET_ENV: ATTESTATION_SECRET}, clear=False
        ):
            result = AssessmentEngine(
                decision_config(bind_provider=True, attest_evidence=True), PassingScorer()
            ).run(Assessment.from_dict(value))
        self.assertTrue(result.evidence_attestation.verified)
        self.assertEqual(result.selection.decision, "ready")

    def test_invalid_executor_attestation_cannot_produce_ready(self) -> None:
        class PassingScorer:
            metadata = TEST_PROVIDER

            def score(self, request):
                return score_bundle(candidate_id=request.candidate_id, diff=request.diff)

        value = assessment_value()
        value["attestation"] = {
            "scheme": "hmac-sha256",
            "key_id": ATTESTATION_KEY_ID,
            "signature": "0" * 64,
        }
        with mock.patch.dict(
            "os.environ", {ATTESTATION_SECRET_ENV: ATTESTATION_SECRET}, clear=False
        ):
            result = AssessmentEngine(
                decision_config(bind_provider=True, attest_evidence=True), PassingScorer()
            ).run(Assessment.from_dict(value))
        self.assertFalse(result.evidence_attestation.verified)
        self.assertEqual(result.selection.decision, "abstain")
        self.assertEqual(result.selection.reason, "evidence_attestation:signature_invalid")

    def test_direct_static_scorer_is_derived_as_test_only_and_cannot_return_ready(self) -> None:
        scorer = StaticScorer(
            {
                "provider_version": "1.0.0",
                "model_revision": "test-only",
                "calibrator_version": "test-only",
                "probability": 0.9,
                "uncertainty": 0.01,
            }
        )
        result = AssessmentEngine(decision_config(), scorer).run(
            Assessment.from_dict(assessment_value())
        )
        self.assertTrue(result.test_only)
        self.assertEqual(result.selection.decision, "abstain")
        self.assertIsNone(result.selection.candidate_id)

    def test_compare_context_is_shared_at_assessment_level(self) -> None:
        value = assessment_value()
        other_diff = f"{CANDIDATE_DIFF}# alternative\n"
        other_id = sha256_text(other_diff)
        other = {
            "candidate_id": other_id,
            "diff": other_diff,
            "truncation_ratio": 0,
            "gates": [gate.as_dict() for gate in required_gates(candidate_id=other_id)],
        }
        value["mode"] = "compare"
        value["candidates"].append(other)
        parsed = Assessment.from_dict(value)
        self.assertEqual(parsed.context.task_digest, TASK_DIGEST)
        self.assertEqual(len(parsed.candidates), 2)

    def test_compare_pins_metadata_for_the_entire_assessment(self) -> None:
        value = assessment_value()
        other_diff = f"{CANDIDATE_DIFF}# alternative\n"
        other_id = sha256_text(other_diff)
        value["mode"] = "compare"
        value["candidates"].append(
            {
                "candidate_id": other_id,
                "diff": other_diff,
                "truncation_ratio": 0,
                "gates": [gate.as_dict() for gate in required_gates(candidate_id=other_id)],
            }
        )

        changed_metadata = TEST_PROVIDER.__class__(
            provider_id=TEST_PROVIDER.provider_id,
            provider_version=TEST_PROVIDER.provider_version,
            model_revision="changed-between-candidates",
            calibrator_version=TEST_PROVIDER.calibrator_version,
        )

        class StatefulScorer:
            metadata_reads = 0

            @property
            def metadata(self):
                self.metadata_reads += 1
                return TEST_PROVIDER if self.metadata_reads <= 3 else changed_metadata

            def score(self, request):
                return score_bundle(candidate_id=request.candidate_id, diff=request.diff)

        result = AssessmentEngine(decision_config(bind_provider=True), StatefulScorer()).run(
            Assessment.from_dict(value)
        )
        self.assertEqual(result.selection.decision, "abstain")
        self.assertEqual(result.scorer_error, "contract_error")
        self.assertIsNotNone(result.evaluations[0].score_bundle)
        self.assertIsNone(result.evaluations[1].score_bundle)

    def test_any_compare_scorer_failure_prevents_ready(self) -> None:
        value = assessment_value()
        value["mode"] = "compare"
        for label in ("second", "third"):
            diff = f"{CANDIDATE_DIFF}# {label}\n"
            candidate_id = sha256_text(diff)
            value["candidates"].append(
                {
                    "candidate_id": candidate_id,
                    "diff": diff,
                    "truncation_ratio": 0,
                    "gates": [gate.as_dict() for gate in required_gates(candidate_id=candidate_id)],
                }
            )
        unsigned = Assessment.from_dict(value)
        value["attestation"] = {
            "scheme": "hmac-sha256",
            "key_id": ATTESTATION_KEY_ID,
            "signature": hmac.new(
                ATTESTATION_SECRET.encode(),
                b"prman-evidence-v1\0" + canonical_json_bytes(unsigned.attestation_payload()),
                hashlib.sha256,
            ).hexdigest(),
        }

        class PartialScorer:
            metadata = TEST_PROVIDER
            calls = 0

            def score(self, request):
                self.calls += 1
                if self.calls == 3:
                    raise RuntimeError("third candidate failed")
                probability = 0.95 if self.calls == 1 else 0.75
                return score_bundle(
                    probability=probability,
                    candidate_id=request.candidate_id,
                    diff=request.diff,
                )

        with mock.patch.dict(
            "os.environ", {ATTESTATION_SECRET_ENV: ATTESTATION_SECRET}, clear=False
        ):
            result = AssessmentEngine(
                decision_config(bind_provider=True, attest_evidence=True), PartialScorer()
            ).run(Assessment.from_dict(value))
        self.assertTrue(result.evidence_attestation.verified)
        self.assertEqual(result.scorer_error, "runtime_error")
        self.assertEqual(result.selection.decision, "abstain")
        self.assertEqual(result.selection.reason, "scorer_unavailable:runtime_error")


if __name__ == "__main__":
    unittest.main()
