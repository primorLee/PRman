from __future__ import annotations

import unittest

from helpers import CANDIDATE_ID, scorer_request

from prman.scorers.builtin import LocalHttpScorer, StaticScorer
from prman.scorers.protocols import ScorerRequest, validate_score_bundle
from prman.scorers.registry import ScorerRegistry
from prman.validation import ContractError


class ScorerTests(unittest.TestCase):
    def test_future_and_identity_fields_are_rejected(self) -> None:
        value = scorer_request().as_dict()
        value["payloads"]["correctness"]["author"] = "identity"
        with self.assertRaisesRegex(ContractError, "forbidden"):
            ScorerRequest.from_dict(value)

    def test_static_provider_round_trip(self) -> None:
        provider = StaticScorer(
            {
                "provider_version": "1.0.0",
                "model_revision": "test-only",
                "calibrator_version": "test-only",
                "probability": 0.8,
                "uncertainty": 0.1,
            }
        )
        request = scorer_request()
        result = validate_score_bundle(request, provider, provider.score(request))
        self.assertEqual(result.candidate_id, CANDIDATE_ID)
        self.assertEqual(len(result.scores), 6)

    def test_test_providers_are_explicitly_marked(self) -> None:
        registry = ScorerRegistry()
        self.assertTrue(registry.is_test_only("builtin.static"))
        self.assertTrue(registry.is_test_only("builtin.fixture-json"))
        self.assertFalse(registry.is_test_only("builtin.local-http"))

    def test_http_provider_rejects_non_loopback_and_hostnames(self) -> None:
        base = {
            "provider_version": "1.0.0",
            "model_revision": "model",
            "calibrator_version": "calibrator",
            "timeout_seconds": 5,
        }
        for endpoint in ("https://127.0.0.1:8080/score", "http://localhost:8080/score"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ContractError):
                LocalHttpScorer({**base, "endpoint": endpoint})


if __name__ == "__main__":
    unittest.main()
