from __future__ import annotations

from pathlib import Path
from typing import Any

from prman.decision import DecisionConfig
from prman.models import (
    ALL_CRITERIA,
    CriterionScore,
    EvidenceRecord,
    GateResult,
    ProviderMetadata,
    ScoreBundle,
)
from prman.scorers.protocols import ScorerRequest
from prman.validation import load_json, sha256_text

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIFF = (
    "diff --git a/example.py b/example.py\n"
    "--- a/example.py\n"
    "+++ b/example.py\n"
    "@@ -1 +1 @@\n"
    "-old\n"
    "+new\n"
)
CANDIDATE_ID = sha256_text(CANDIDATE_DIFF)
REPOSITORY_ID = sha256_text("https://example.test/acme/repository")
BASE_COMMIT = "1" * 40
TASK = "Implement the requested test change"
TASK_DIGEST = sha256_text(TASK)
TEST_PROVIDER = ProviderMetadata(
    provider_id="test.provider",
    provider_version="1.0.0",
    model_revision="test-model",
    calibrator_version="test-calibrator",
)
ATTESTATION_KEY_ID = "unit-test-executor"
ATTESTATION_SECRET_ENV = "PRMAN_TEST_EVIDENCE_SECRET"
ATTESTATION_SECRET = "unit-test-evidence-secret-at-least-32-bytes"


def decision_config(
    *, bind_provider: bool = False, attest_evidence: bool = False
) -> DecisionConfig:
    value = load_json(ROOT / "configs" / "decision.json")
    if bind_provider:
        value["scorer_binding"] = TEST_PROVIDER.as_dict()
    if attest_evidence:
        value["evidence_attestation"] = {
            "scheme": "hmac-sha256",
            "key_id": ATTESTATION_KEY_ID,
            "hmac_secret_env": ATTESTATION_SECRET_ENV,
        }
    return DecisionConfig.from_mapping(value)


def gate(
    name: str,
    status: str = "pass",
    *,
    recoverable: bool = False,
    code: str = "PASS",
    candidate_id: str = CANDIDATE_ID,
) -> GateResult:
    source = "command" if name == "tests" and status == "pass" else "inspection"
    return GateResult(
        name=name,
        status=status,
        recoverable=recoverable,
        code=code,
        evidence=EvidenceRecord(
            source=source,
            candidate_id=candidate_id,
            observed_at="2026-08-29T00:00:00Z",
            producer="unit-test",
            producer_version="1.0.0",
            summary=f"observed {name} as {status}",
            log_digest=sha256_text(f"{candidate_id}:{name}:{status}:{code}"),
            command=("unit-test", name) if source == "command" else None,
            exit_code=0 if source == "command" else None,
        ),
        actionable="fix the change" if recoverable else None,
    )


def required_gates(*, candidate_id: str = CANDIDATE_ID) -> tuple[GateResult, ...]:
    return (
        gate("scope", candidate_id=candidate_id),
        gate("secrets", candidate_id=candidate_id),
        gate("tests", candidate_id=candidate_id),
    )


def scorer_request(
    candidate_id: str = CANDIDATE_ID,
    *,
    diff: str = CANDIDATE_DIFF,
) -> ScorerRequest:
    return ScorerRequest.create(
        candidate_id=candidate_id,
        repository_id=REPOSITORY_ID,
        base_commit=BASE_COMMIT,
        task=TASK,
        task_digest=TASK_DIGEST,
        repository_rules=("Keep changes focused.",),
        diff=diff,
        gates=required_gates(candidate_id=candidate_id),
    )


def score_bundle(
    probability: float = 0.9,
    *,
    uncertainty: float = 0.05,
    candidate_id: str = CANDIDATE_ID,
    diff: str = CANDIDATE_DIFF,
    overrides: dict[str, float] | None = None,
    actionable: bool = False,
    ood: bool = False,
    provider: ProviderMetadata = TEST_PROVIDER,
) -> ScoreBundle:
    request = scorer_request(candidate_id, diff=diff)
    values: dict[str, Any] = overrides or {}
    return ScoreBundle(
        candidate_id=candidate_id,
        request_digest=request.request_digest,
        provider=provider,
        scores=tuple(
            CriterionScore(
                criterion=criterion,
                probability=values.get(criterion, probability),
                uncertainty=uncertainty,
                evidence=("test evidence",),
                actionable_critique="improve this criterion" if actionable else None,
                ood=ood,
            )
            for criterion in ALL_CRITERIA
        ),
    )
