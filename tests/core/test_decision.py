from __future__ import annotations

import unittest

from helpers import CANDIDATE_ID, decision_config, gate, required_gates, score_bundle

from prman.decision import AggregateResult, DecisionConfig, MonotoneDecision
from prman.validation import ContractError


class DecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.decision = MonotoneDecision(decision_config())

    def test_missing_gate_forces_abstain_before_score(self) -> None:
        result = self.decision.aggregate(
            gates=(gate("scope"), gate("tests")),
            score_bundle=score_bundle(),
            truncation_ratio=0,
        )
        self.assertEqual(result.provisional_decision, "abstain")
        self.assertEqual(result.reasons, ("missing_gate:secrets",))
        self.assertIsNone(result.score)

    def test_fatal_gate_dominates_recoverable_gate(self) -> None:
        result = self.decision.aggregate(
            gates=(
                gate("scope", "fail", recoverable=True, code="TOO_WIDE"),
                gate("secrets", "fail", code="SECRET_FOUND"),
                gate("tests"),
            ),
            score_bundle=score_bundle(),
            truncation_ratio=0,
        )
        self.assertEqual(result.provisional_decision, "abstain")
        self.assertEqual(result.reasons, ("hard_gate:secrets:SECRET_FOUND",))

    def test_unknown_required_gate_forces_abstain(self) -> None:
        result = self.decision.aggregate(
            gates=(gate("scope"), gate("secrets"), gate("tests", "unknown", code="NOT_RUN")),
            score_bundle=score_bundle(),
            truncation_ratio=0,
        )
        self.assertEqual(result.provisional_decision, "abstain")
        self.assertEqual(result.reasons, ("unknown_gate:tests:NOT_RUN",))

    def test_unknown_advisory_gate_does_not_block(self) -> None:
        result = self.decision.aggregate(
            gates=(*required_gates(), gate("lint", "unknown", code="NOT_CONFIGURED")),
            score_bundle=score_bundle(),
            truncation_ratio=0,
        )
        self.assertEqual(result.provisional_decision, "eligible")

    def test_single_eligible_candidate_is_ready(self) -> None:
        aggregate = self.decision.aggregate(
            gates=required_gates(),
            score_bundle=score_bundle(),
            truncation_ratio=0,
        )
        selection = self.decision.finalize(
            mode="single",
            evaluations=((CANDIDATE_ID, aggregate),),
        )
        self.assertEqual(aggregate.provisional_decision, "eligible")
        self.assertEqual(selection.decision, "ready")
        self.assertEqual(selection.candidate_id, CANDIDATE_ID)

    def test_low_lcb_cannot_be_ready_even_when_raw_thresholds_pass(self) -> None:
        aggregate = self.decision.aggregate(
            gates=required_gates(),
            score_bundle=score_bundle(probability=0.75, uncertainty=0.12),
            truncation_ratio=0.4,
        )
        self.assertAlmostEqual(aggregate.score or 0, 0.75)
        self.assertAlmostEqual(aggregate.lcb or 0, 0.26)
        self.assertNotEqual(aggregate.provisional_decision, "eligible")
        self.assertIn("lcb_below_ready_threshold", aggregate.reasons)

    def test_comparison_requires_configured_margin(self) -> None:
        top = AggregateResult(0.9, 0.02, 0.88, "eligible", (), True)
        runner_up = AggregateResult(0.86, 0.02, 0.84, "eligible", (), True)
        selection = self.decision.finalize(
            mode="compare",
            evaluations=(("a" * 64, top), ("b" * 64, runner_up)),
        )
        self.assertEqual(selection.decision, "abstain")
        self.assertAlmostEqual(selection.margin or 0, 0.04)

    def test_ood_candidate_cannot_serve_as_comparison_runner_up(self) -> None:
        top = self.decision.aggregate(
            gates=required_gates(),
            score_bundle=score_bundle(probability=0.9),
            truncation_ratio=0,
        )
        ood = self.decision.aggregate(
            gates=required_gates(),
            score_bundle=score_bundle(probability=0.1, ood=True),
            truncation_ratio=0,
        )
        self.assertFalse(ood.comparable)
        selection = self.decision.finalize(
            mode="compare",
            evaluations=(("a" * 64, top), ("b" * 64, ood)),
        )
        self.assertEqual(selection.decision, "abstain")
        self.assertIn("runner-up", selection.reason)

    def test_multiple_gate_only_revisions_are_not_ranked_by_hash(self) -> None:
        revise_a = self.decision.aggregate(
            gates=(
                gate("scope", "fail", recoverable=True, code="TOO_WIDE"),
                gate("secrets"),
                gate("tests"),
            ),
            score_bundle=None,
            truncation_ratio=0,
        )
        revise_b = self.decision.aggregate(
            gates=(
                gate("scope", "fail", recoverable=True, code="TOO_WIDE"),
                gate("secrets"),
                gate("tests"),
            ),
            score_bundle=None,
            truncation_ratio=0,
        )
        selection = self.decision.finalize(
            mode="compare",
            evaluations=(("f" * 64, revise_a), ("0" * 64, revise_b)),
        )
        self.assertEqual(selection.decision, "abstain")
        self.assertIsNone(selection.candidate_id)

    def test_aggregate_is_monotone_in_each_probability(self) -> None:
        baseline = self.decision.aggregate(
            gates=required_gates(),
            score_bundle=score_bundle(probability=0.8),
            truncation_ratio=0,
        )
        self.assertIsNotNone(baseline.score)
        for criterion in decision_config().weights:
            improved = self.decision.aggregate(
                gates=required_gates(),
                score_bundle=score_bundle(probability=0.8, overrides={criterion: 0.9}),
                truncation_ratio=0,
            )
            self.assertGreaterEqual(improved.score or 0, baseline.score or 0)

    def test_semantically_contradictory_config_is_rejected(self) -> None:
        value = decision_config().as_dict()
        value["ready_score"] = 0.4
        with self.assertRaisesRegex(ContractError, "ready_score"):
            DecisionConfig.from_mapping(value)

        value = decision_config().as_dict()
        value["ready_uncertainty_max"] = 0.3
        with self.assertRaisesRegex(ContractError, "uncertainty"):
            DecisionConfig.from_mapping(value)

        value = decision_config().as_dict()
        value["critical_min"] = {}
        value["soft_min"] = {}
        with self.assertRaisesRegex(ContractError, "cover"):
            DecisionConfig.from_mapping(value)


if __name__ == "__main__":
    unittest.main()
