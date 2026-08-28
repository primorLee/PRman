from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from prman.decision import AggregateResult, DecisionConfig, MonotoneDecision, SelectionResult
from prman.models import GateResult, ProviderMetadata, ScoreBundle
from prman.scorers.protocols import ScorerProvider, ScorerRequest, validate_score_bundle
from prman.validation import (
    ContractError,
    canonical_digest,
    exact_fields,
    require_list,
    require_object,
    require_probability,
    require_sha256,
)

AssessmentMode = Literal["single", "compare"]


@dataclass(frozen=True)
class CandidateAssessment:
    candidate_id: str
    truncation_ratio: float
    gates: tuple[GateResult, ...]
    scorer_request: ScorerRequest | None

    @classmethod
    def from_dict(cls, value: Any, *, path: str) -> CandidateAssessment:
        item = require_object(value, path=path)
        exact_fields(
            item,
            {"candidate_id", "truncation_ratio", "gates", "scorer_request"},
            path=path,
        )
        candidate_id = require_sha256(item["candidate_id"], path=f"{path}.candidate_id")
        truncation_ratio = require_probability(
            item["truncation_ratio"], path=f"{path}.truncation_ratio"
        )
        gates_value = require_list(item["gates"], path=f"{path}.gates")
        gates = tuple(
            GateResult.from_dict(gate, path=f"{path}.gates[{index}]")
            for index, gate in enumerate(gates_value)
        )
        if len({gate.name for gate in gates}) != len(gates):
            raise ContractError(f"{path}.gates contains duplicate names")
        raw_request = item["scorer_request"]
        scorer_request = None if raw_request is None else ScorerRequest.from_dict(raw_request)
        if scorer_request is not None and scorer_request.candidate_id != candidate_id:
            raise ContractError(f"{path}.scorer_request candidate_id mismatch")
        return cls(
            candidate_id=candidate_id,
            truncation_ratio=truncation_ratio,
            gates=gates,
            scorer_request=scorer_request,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "truncation_ratio": self.truncation_ratio,
            "gates": [gate.as_dict() for gate in self.gates],
            "scorer_request": self.scorer_request.as_dict() if self.scorer_request else None,
        }


@dataclass(frozen=True)
class Assessment:
    mode: AssessmentMode
    candidates: tuple[CandidateAssessment, ...]
    schema_version: str = "prman-assessment/1.0"

    @classmethod
    def from_dict(cls, value: Any) -> Assessment:
        item = require_object(value, path="assessment")
        exact_fields(item, {"schema_version", "mode", "candidates"}, path="assessment")
        if item["schema_version"] != "prman-assessment/1.0":
            raise ContractError(f"unsupported assessment {item['schema_version']!r}")
        mode = item["mode"]
        if mode not in {"single", "compare"}:
            raise ContractError(f"assessment.mode: unsupported value {mode!r}")
        raw_candidates = require_list(item["candidates"], path="assessment.candidates")
        candidates = tuple(
            CandidateAssessment.from_dict(candidate, path=f"assessment.candidates[{index}]")
            for index, candidate in enumerate(raw_candidates)
        )
        if mode == "single" and len(candidates) != 1:
            raise ContractError("single assessment mode requires exactly one candidate")
        if mode == "compare" and len(candidates) < 2:
            raise ContractError("compare assessment mode requires at least two candidates")
        candidate_ids = [candidate.candidate_id for candidate in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ContractError("assessment contains duplicate candidate IDs")
        return cls(schema_version=item["schema_version"], mode=mode, candidates=candidates)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    gates: tuple[GateResult, ...]
    score_bundle: ScoreBundle | None
    aggregate: AggregateResult

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "gates": [gate.as_dict() for gate in self.gates],
            "score_bundle": self.score_bundle.as_dict() if self.score_bundle else None,
            "aggregate": self.aggregate.as_dict(),
        }


@dataclass(frozen=True)
class AssessmentResult:
    assessment_digest: str
    decision_config_digest: str
    provider: ProviderMetadata | None
    test_only: bool
    evaluations: tuple[CandidateEvaluation, ...]
    selection: SelectionResult
    schema_version: str = "prman-assessment-result/1.0"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assessment_digest": self.assessment_digest,
            "decision_config_digest": self.decision_config_digest,
            "provider": self.provider.as_dict() if self.provider else None,
            "test_only": self.test_only,
            "evaluations": [evaluation.as_dict() for evaluation in self.evaluations],
            "selection": self.selection.as_dict(),
            "policy": {
                "human_confirmation_required": True,
                "draft_only": True,
                "external_write_authorized": False,
            },
        }


class AssessmentEngine:
    def __init__(
        self,
        decision_config: DecisionConfig,
        scorer: ScorerProvider | None = None,
        *,
        test_only: bool = False,
    ) -> None:
        if test_only and scorer is None:
            raise ContractError("test_only requires a configured scorer")
        self.decision_config = decision_config
        self.scorer = scorer
        self.test_only = test_only
        self.decision = MonotoneDecision(decision_config)

    def run(self, assessment: Assessment) -> AssessmentResult:
        evaluations: list[CandidateEvaluation] = []
        for candidate in assessment.candidates:
            pre_score = self.decision.aggregate(
                gates=candidate.gates,
                score_bundle=None,
                truncation_ratio=candidate.truncation_ratio,
            )
            score_bundle: ScoreBundle | None = None
            aggregate = pre_score
            gates_passed = pre_score.reasons == ("scorer_unavailable",)
            if gates_passed and self.scorer is not None:
                if candidate.scorer_request is None:
                    raise ContractError(
                        f"candidate {candidate.candidate_id} passed gates but has no scorer_request"
                    )
                request_digest_before = candidate.scorer_request.request_digest
                metadata_before = self.scorer.metadata
                raw_bundle = self.scorer.score(candidate.scorer_request)
                if candidate.scorer_request.request_digest != request_digest_before:
                    raise ContractError("scorer mutated its request payload")
                if self.scorer.metadata != metadata_before:
                    raise ContractError("scorer metadata changed during a request")
                score_bundle = validate_score_bundle(
                    candidate.scorer_request,
                    self.scorer,
                    raw_bundle,
                )
                aggregate = self.decision.aggregate(
                    gates=candidate.gates,
                    score_bundle=score_bundle,
                    truncation_ratio=candidate.truncation_ratio,
                )
            evaluations.append(
                CandidateEvaluation(
                    candidate_id=candidate.candidate_id,
                    gates=candidate.gates,
                    score_bundle=score_bundle,
                    aggregate=aggregate,
                )
            )
        selection = self.decision.finalize(
            mode=assessment.mode,
            evaluations=tuple(
                (evaluation.candidate_id, evaluation.aggregate) for evaluation in evaluations
            ),
        )
        return AssessmentResult(
            assessment_digest=canonical_digest(assessment.as_dict()),
            decision_config_digest=canonical_digest(self.decision_config.as_dict()),
            provider=self.scorer.metadata if self.scorer else None,
            test_only=self.test_only,
            evaluations=tuple(evaluations),
            selection=selection,
        )
