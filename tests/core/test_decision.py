from __future__ import annotations

import unittest

from helpers import CANDIDATE_ID, decision_config, gate, required_gates, score_bundle

from prman.decision import AggregateResult, MonotoneDecision


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

    def test_unknown_gate_forces_abstain(self) -> None:
        result = self.decision.aggregate(
            gates=(gate("scope"), gate("secrets"), gate("tests", "unknown", code="NOT_RUN")),
            score_bundle=score_bundle(),
            truncation_ratio=0,
        )
        self.assertEqual(result.provisional_decision, "abstain")
        self.assertEqual(result.reasons, ("unknown_gate:tests:NOT_RUN",))

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

    def test_comparison_requires_configured_margin(self) -> None:
        top = AggregateResult(0.9, 0.02, 0.88, "eligible", ())
        runner_up = AggregateResult(0.86, 0.02, 0.84, "eligible", ())
        selection = self.decision.finalize(
            mode="compare",
            evaluations=(("a" * 64, top), ("b" * 64, runner_up)),
        )
        self.assertEqual(selection.decision, "abstain")
        self.assertAlmostEqual(selection.margin or 0, 0.04)

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


if __name__ == "__main__":
    unittest.main()
