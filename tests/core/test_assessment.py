from __future__ import annotations

import unittest

from helpers import CANDIDATE_ID, decision_config, required_gates, score_bundle, scorer_request

from prman.assessment import Assessment, AssessmentEngine
from prman.models import ProviderMetadata
from prman.validation import ContractError


def assessment_value(*, scorer: bool = True) -> dict[str, object]:
    return {
        "schema_version": "prman-assessment/1.0",
        "mode": "single",
        "candidates": [
            {
                "candidate_id": CANDIDATE_ID,
                "truncation_ratio": 0,
                "gates": [gate.as_dict() for gate in required_gates()],
                "scorer_request": scorer_request().as_dict() if scorer else None,
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
        self.assertEqual(result.evaluations[0].aggregate.reasons, ("scorer_unavailable",))
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

    def test_request_candidate_must_match_candidate(self) -> None:
        value = assessment_value()
        candidate = value["candidates"][0]
        candidate["scorer_request"]["candidate_id"] = "b" * 64
        with self.assertRaisesRegex(ContractError, "candidate_id mismatch"):
            Assessment.from_dict(value)

    def test_scorer_cannot_mutate_request_payload(self) -> None:
        class MutatingScorer:
            metadata = ProviderMetadata(
                provider_id="test.mutating",
                provider_version="1.0.0",
                model_revision="test",
                calibrator_version="test",
            )

            def score(self, request):
                request.payloads["correctness"]["task"]["title"] = "mutated"
                return score_bundle()

        assessment = Assessment.from_dict(assessment_value())
        with self.assertRaisesRegex(ContractError, "mutated its request"):
            AssessmentEngine(decision_config(), MutatingScorer()).run(assessment)


if __name__ == "__main__":
    unittest.main()
