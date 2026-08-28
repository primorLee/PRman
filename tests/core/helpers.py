from __future__ import annotations

from pathlib import Path
from typing import Any

from prman.decision import DecisionConfig
from prman.models import ALL_CRITERIA, CriterionScore, GateResult, ProviderMetadata, ScoreBundle
from prman.scorers.protocols import ScorerRequest
from prman.validation import load_json

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_ID = "a" * 64


def decision_config() -> DecisionConfig:
    return DecisionConfig.from_mapping(load_json(ROOT / "configs" / "decision.json"))


def gate(
    name: str,
    status: str = "pass",
    *,
    recoverable: bool = False,
    code: str = "PASS",
) -> GateResult:
    return GateResult(
        name=name,
        status=status,
        recoverable=recoverable,
        code=code,
        evidence={"observed": True},
        actionable="fix the change" if recoverable else None,
    )


def required_gates() -> tuple[GateResult, ...]:
    return (gate("scope"), gate("secrets"), gate("tests"))


def scorer_request(candidate_id: str = CANDIDATE_ID) -> ScorerRequest:
    return ScorerRequest(
        candidate_id=candidate_id,
        payloads={
            criterion: {
                "criterion": criterion,
                "task": {"title": "test task"},
                "candidate": {"changed_files": ["example.py"]},
                "evidence": {"tests": "passed"},
            }
            for criterion in ALL_CRITERIA
        },
    )


def score_bundle(
    probability: float = 0.9,
    *,
    uncertainty: float = 0.05,
    candidate_id: str = CANDIDATE_ID,
    overrides: dict[str, float] | None = None,
    actionable: bool = False,
) -> ScoreBundle:
    request = scorer_request(candidate_id)
    values: dict[str, Any] = overrides or {}
    return ScoreBundle(
        candidate_id=candidate_id,
        request_digest=request.request_digest,
        provider=ProviderMetadata(
            provider_id="test.provider",
            provider_version="1.0.0",
            model_revision="test-model",
            calibrator_version="test-calibrator",
        ),
        scores=tuple(
            CriterionScore(
                criterion=criterion,
                probability=values.get(criterion, probability),
                uncertainty=uncertainty,
                evidence=("test evidence",),
                actionable_critique="improve this criterion" if actionable else None,
                ood=False,
            )
            for criterion in ALL_CRITERIA
        ),
    )
