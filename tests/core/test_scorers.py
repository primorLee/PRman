from __future__ import annotations

import hashlib
import hmac
import json
import threading
import unittest
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from helpers import (
    BASE_COMMIT,
    CANDIDATE_ID,
    REPOSITORY_ID,
    TASK,
    TASK_DIGEST,
    required_gates,
    scorer_request,
)

from prman.models import ALL_CRITERIA, ProviderMetadata
from prman.scorers.builtin import LocalHttpScorer, StaticScorer
from prman.scorers.protocols import ScorerRequest, validate_score_bundle
from prman.scorers.registry import ScorerRegistry
from prman.validation import MAX_JSON_BYTES, ContractError, canonical_json_bytes, sha256_text

HMAC_SECRET = "unit-test-secret-that-is-at-least-32-bytes"


def _http_options(endpoint: str) -> dict[str, object]:
    return {
        "provider_version": "1.0.0",
        "model_revision": "model",
        "calibrator_version": "calibrator",
        "timeout_seconds": 5,
        "endpoint": endpoint,
        "hmac_secret_env": "PRMAN_TEST_HMAC_SECRET",
    }


class _SignedScorerHandler(BaseHTTPRequestHandler):
    invalid_signature = False

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        expected = hmac.new(
            HMAC_SECRET.encode(), b"prman-request-v1\0" + body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(self.headers.get("X-PRman-Signature", ""), expected):
            self.send_error(401)
            return
        envelope = json.loads(body)
        request = ScorerRequest.from_dict(envelope["request"])
        scores = [
            {
                "criterion": criterion,
                "probability": 0.9,
                "uncertainty": 0.02,
                "evidence": ["authenticated integration test"],
                "actionable_critique": None,
                "ood": False,
            }
            for criterion in ALL_CRITERIA
        ]
        response = canonical_json_bytes(
            {
                "schema_version": "prman-scorer-service-response/1.1",
                "request_digest": request.request_digest,
                "nonce": envelope["nonce"],
                "provider": envelope["provider"],
                "scores": scores,
            }
        )
        signature = hmac.new(
            HMAC_SECRET.encode(), b"prman-response-v1\0" + response, hashlib.sha256
        ).hexdigest()
        if self.invalid_signature:
            signature = "0" * 64
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("X-PRman-Signature", signature)
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class _FakeHttpResponse:
    def __init__(self, body: bytes, signature: str) -> None:
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"
        self.headers["X-PRman-Signature"] = signature

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class _SignedFakeOpener:
    def __init__(self, *, invalid_signature: bool = False) -> None:
        self.invalid_signature = invalid_signature

    def open(self, http_request, *, timeout: float):
        self.timeout = timeout
        body = http_request.data
        expected_request_signature = hmac.new(
            HMAC_SECRET.encode(), b"prman-request-v1\0" + body, hashlib.sha256
        ).hexdigest()
        assert hmac.compare_digest(
            http_request.get_header("X-prman-signature"), expected_request_signature
        )
        envelope = json.loads(body)
        request = ScorerRequest.from_dict(envelope["request"])
        response = canonical_json_bytes(
            {
                "schema_version": "prman-scorer-service-response/1.1",
                "request_digest": request.request_digest,
                "nonce": envelope["nonce"],
                "provider": envelope["provider"],
                "scores": [
                    {
                        "criterion": criterion,
                        "probability": 0.9,
                        "uncertainty": 0.02,
                        "evidence": ["authenticated unit test"],
                        "actionable_critique": None,
                        "ood": False,
                    }
                    for criterion in ALL_CRITERIA
                ],
            }
        )
        signature = hmac.new(
            HMAC_SECRET.encode(), b"prman-response-v1\0" + response, hashlib.sha256
        ).hexdigest()
        if self.invalid_signature:
            signature = "0" * 64
        return _FakeHttpResponse(response, signature)


class ScorerTests(unittest.TestCase):
    def test_scorer_request_uses_a_strict_allowlist(self) -> None:
        value = scorer_request().as_dict()
        value["context"]["reviewer_identity"] = "identity"
        with self.assertRaisesRegex(ContractError, "strict fields mismatch"):
            ScorerRequest.from_dict(value)

    def test_raw_diff_is_an_explicit_source_field_not_a_key_denylist(self) -> None:
        request = scorer_request()
        value = request.as_dict()
        value["context"]["diff"] = value["context"]["diff"].replace("old", "author")
        value["candidate_id"] = hashlib.sha256(value["context"]["diff"].encode()).hexdigest()
        parsed = ScorerRequest.from_dict(value)
        self.assertIn("author", parsed.diff)

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
        result = validate_score_bundle(request, provider.metadata, provider.score(request))
        self.assertEqual(result.candidate_id, CANDIDATE_ID)
        self.assertEqual(len(result.scores), 6)

    def test_test_providers_are_explicitly_marked(self) -> None:
        registry = ScorerRegistry()
        self.assertTrue(registry.is_test_only("builtin.static"))
        self.assertTrue(registry.is_test_only("builtin.fixture-json"))
        self.assertFalse(registry.is_test_only("builtin.local-http"))
        self.assertEqual(
            registry.trust_classification("builtin.local-http"), "authenticated-service"
        )

    def test_http_provider_rejects_non_loopback_and_hostnames(self) -> None:
        for endpoint in ("https://127.0.0.1:8080/score", "http://localhost:8080/score"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ContractError):
                LocalHttpScorer(_http_options(endpoint))

    def test_http_provider_requires_configured_secret(self) -> None:
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            self.assertRaisesRegex(ContractError, "not set"),
        ):
            LocalHttpScorer(_http_options("http://127.0.0.1:8080/score"))

    def test_http_provider_signed_round_trip_without_a_socket(self) -> None:
        with mock.patch.dict("os.environ", {"PRMAN_TEST_HMAC_SECRET": HMAC_SECRET}, clear=False):
            provider = LocalHttpScorer(_http_options("http://127.0.0.1:8080/score"))
            provider._opener = _SignedFakeOpener()
            result = provider.score(scorer_request())
        self.assertEqual(result.provider, provider.metadata)
        self.assertEqual(len(result.scores), 6)

    def test_http_provider_invalid_signature_fails_without_a_socket(self) -> None:
        with mock.patch.dict("os.environ", {"PRMAN_TEST_HMAC_SECRET": HMAC_SECRET}, clear=False):
            provider = LocalHttpScorer(_http_options("http://127.0.0.1:8080/score"))
            provider._opener = _SignedFakeOpener(invalid_signature=True)
            with self.assertRaisesRegex(ContractError, "signature"):
                provider.score(scorer_request())

    def test_http_provider_rejects_oversized_request_before_network(self) -> None:
        large_diff = "x" * MAX_JSON_BYTES
        candidate_id = sha256_text(large_diff)
        request = ScorerRequest.create(
            candidate_id=candidate_id,
            repository_id=REPOSITORY_ID,
            base_commit=BASE_COMMIT,
            task=TASK,
            task_digest=TASK_DIGEST,
            repository_rules=(),
            diff=large_diff,
            gates=required_gates(candidate_id=candidate_id),
        )
        with mock.patch.dict("os.environ", {"PRMAN_TEST_HMAC_SECRET": HMAC_SECRET}, clear=False):
            provider = LocalHttpScorer(_http_options("http://127.0.0.1:8080/score"))
            provider._opener = mock.Mock(side_effect=AssertionError("network must not run"))
            with self.assertRaisesRegex(ContractError, "request exceeds"):
                provider.score(request)

    def test_http_provider_authenticates_request_response_and_identity(self) -> None:
        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _SignedScorerHandler)
        except PermissionError:
            self.skipTest("loopback sockets are disabled by the current sandbox")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f"http://127.0.0.1:{server.server_port}/score"
            with mock.patch.dict(
                "os.environ", {"PRMAN_TEST_HMAC_SECRET": HMAC_SECRET}, clear=False
            ):
                provider = LocalHttpScorer(_http_options(endpoint))
                result = provider.score(scorer_request())
            self.assertEqual(result.provider, provider.metadata)
            self.assertEqual(len(result.scores), 6)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_provider_rejects_invalid_response_signature(self) -> None:
        class InvalidSignatureHandler(_SignedScorerHandler):
            invalid_signature = True

        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), InvalidSignatureHandler)
        except PermissionError:
            self.skipTest("loopback sockets are disabled by the current sandbox")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f"http://127.0.0.1:{server.server_port}/score"
            with mock.patch.dict(
                "os.environ", {"PRMAN_TEST_HMAC_SECRET": HMAC_SECRET}, clear=False
            ):
                provider = LocalHttpScorer(_http_options(endpoint))
                with self.assertRaisesRegex(ContractError, "signature"):
                    provider.score(scorer_request())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_external_python_provider_requires_explicit_trust_before_load(self) -> None:
        loaded = False

        class ExternalProvider:
            metadata = ProviderMetadata(
                provider_id="acme.scorer",
                provider_version="1.0.0",
                model_revision="model",
                calibrator_version="calibrator",
            )

            def score(self, request):
                del request
                raise NotImplementedError

        class EntryPoint:
            name = "acme.scorer"

            def load(self):
                nonlocal loaded
                loaded = True
                return lambda options: ExternalProvider()

        registry = ScorerRegistry()
        with mock.patch(
            "prman.scorers.registry.metadata.entry_points", return_value=[EntryPoint()]
        ):
            with self.assertRaisesRegex(ContractError, "trusted code"):
                registry.create("acme.scorer", {})
            self.assertFalse(loaded)
            provider = registry.create("acme.scorer", {}, allow_trusted_python=True)
        self.assertTrue(loaded)
        self.assertEqual(provider.metadata.provider_id, "acme.scorer")


if __name__ == "__main__":
    unittest.main()
