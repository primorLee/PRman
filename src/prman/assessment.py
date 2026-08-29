from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any, Literal

from prman.decision import (
    AggregateResult,
    DecisionConfig,
    EvidenceAttestationPolicy,
    MonotoneDecision,
    SelectionResult,
)
from prman.models import GateResult, ProviderMetadata, ScoreBundle
from prman.scorers.protocols import (
    TEST_ONLY_PROVIDER_IDS,
    ScorerProvider,
    ScorerRequest,
    ScorerUnavailableError,
    validate_score_bundle,
)
from prman.validation import (
    ContractError,
    canonical_digest,
    canonical_json_bytes,
    exact_fields,
    require_list,
    require_object,
    require_probability,
    require_revision,
    require_sha256,
    require_string,
    sha256_text,
)

AssessmentMode = Literal["single", "compare"]


@dataclass(frozen=True)
class AssessmentAttestation:
    key_id: str
    signature: str
    scheme: str = "hmac-sha256"

    def __post_init__(self) -> None:
        if self.scheme != "hmac-sha256":
            raise ContractError(f"unsupported assessment attestation {self.scheme!r}")
        require_string(self.key_id, path="assessment.attestation.key_id")
        require_sha256(self.signature, path="assessment.attestation.signature")

    @classmethod
    def from_dict(cls, value: Any) -> AssessmentAttestation:
        item = require_object(value, path="assessment.attestation")
        exact_fields(
            item,
            {"scheme", "key_id", "signature"},
            path="assessment.attestation",
        )
        return cls(**item)

    def as_dict(self) -> dict[str, str]:
        return {
            "scheme": self.scheme,
            "key_id": self.key_id,
            "signature": self.signature,
        }


@dataclass(frozen=True)
class AssessmentContext:
    repository_id: str
    base_commit: str
    task: str
    task_digest: str
    repository_rules: tuple[str, ...]

    def __post_init__(self) -> None:
        require_sha256(self.repository_id, path="assessment.context.repository_id")
        require_revision(self.base_commit, path="assessment.context.base_commit")
        require_string(self.task, path="assessment.context.task")
        require_sha256(self.task_digest, path="assessment.context.task_digest")
        if sha256_text(self.task) != self.task_digest:
            raise ContractError("assessment.context.task_digest does not match task text")
        if not isinstance(self.repository_rules, tuple):
            raise ContractError("assessment.context.repository_rules must be a tuple")
        if any(not isinstance(rule, str) or not rule.strip() for rule in self.repository_rules):
            raise ContractError("assessment.context.repository_rules contains an invalid item")

    @classmethod
    def from_dict(cls, value: Any) -> AssessmentContext:
        item = require_object(value, path="assessment.context")
        exact_fields(
            item,
            {"repository_id", "base_commit", "task", "task_digest", "repository_rules"},
            path="assessment.context",
        )
        rules = require_list(item["repository_rules"], path="assessment.context.repository_rules")
        return cls(
            repository_id=item["repository_id"],
            base_commit=item["base_commit"],
            task=item["task"],
            task_digest=item["task_digest"],
            repository_rules=tuple(rules),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "base_commit": self.base_commit,
            "task": self.task,
            "task_digest": self.task_digest,
            "repository_rules": list(self.repository_rules),
        }


@dataclass(frozen=True)
class CandidateAssessment:
    candidate_id: str
    diff: str
    truncation_ratio: float
    gates: tuple[GateResult, ...]

    def __post_init__(self) -> None:
        require_sha256(self.candidate_id, path="candidate.candidate_id")
        if not isinstance(self.diff, str) or not self.diff:
            raise ContractError("candidate.diff: expected a non-empty UTF-8 unified diff")
        if sha256_text(self.diff) != self.candidate_id:
            raise ContractError("candidate.candidate_id does not match diff bytes")
        require_probability(self.truncation_ratio, path="candidate.truncation_ratio")
        if not isinstance(self.gates, tuple):
            raise ContractError("candidate.gates must be a tuple")
        if any(not isinstance(gate, GateResult) for gate in self.gates):
            raise ContractError("candidate.gates must contain GateResult values")
        if len({gate.name for gate in self.gates}) != len(self.gates):
            raise ContractError("candidate.gates contains duplicate names")
        for gate in self.gates:
            gate.validate_candidate(self.candidate_id)

    @classmethod
    def from_dict(cls, value: Any, *, path: str) -> CandidateAssessment:
        item = require_object(value, path=path)
        exact_fields(
            item,
            {"candidate_id", "diff", "truncation_ratio", "gates"},
            path=path,
        )
        candidate_id = require_sha256(item["candidate_id"], path=f"{path}.candidate_id")
        diff = item["diff"]
        if not isinstance(diff, str) or not diff:
            raise ContractError(f"{path}.diff: expected a non-empty UTF-8 unified diff")
        if sha256_text(diff) != candidate_id:
            raise ContractError(f"{path}.candidate_id does not match diff bytes")
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
        for gate in gates:
            gate.validate_candidate(candidate_id)
        return cls(
            candidate_id=candidate_id,
            diff=diff,
            truncation_ratio=truncation_ratio,
            gates=gates,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "diff": self.diff,
            "truncation_ratio": self.truncation_ratio,
            "gates": [gate.as_dict() for gate in self.gates],
        }


@dataclass(frozen=True)
class Assessment:
    mode: AssessmentMode
    context: AssessmentContext
    candidates: tuple[CandidateAssessment, ...]
    attestation: AssessmentAttestation | None
    schema_version: str = "prman-assessment/1.1"

    def __post_init__(self) -> None:
        if self.schema_version != "prman-assessment/1.1":
            raise ContractError(f"unsupported assessment {self.schema_version!r}")
        if self.mode not in {"single", "compare"}:
            raise ContractError(f"assessment.mode: unsupported value {self.mode!r}")
        if not isinstance(self.context, AssessmentContext):
            raise ContractError("assessment.context must be AssessmentContext")
        if not isinstance(self.candidates, tuple):
            raise ContractError("assessment.candidates must be a tuple")
        if any(not isinstance(candidate, CandidateAssessment) for candidate in self.candidates):
            raise ContractError("assessment.candidates must contain CandidateAssessment values")
        if self.mode == "single" and len(self.candidates) != 1:
            raise ContractError("single assessment mode requires exactly one candidate")
        if self.mode == "compare" and len(self.candidates) < 2:
            raise ContractError("compare assessment mode requires at least two candidates")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ContractError("assessment contains duplicate candidate IDs")
        if self.attestation is not None and not isinstance(self.attestation, AssessmentAttestation):
            raise ContractError("assessment.attestation must be AssessmentAttestation or null")

    @classmethod
    def from_dict(cls, value: Any) -> Assessment:
        item = require_object(value, path="assessment")
        exact_fields(
            item,
            {"schema_version", "mode", "context", "candidates", "attestation"},
            path="assessment",
        )
        if item["schema_version"] != "prman-assessment/1.1":
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
        return cls(
            schema_version=item["schema_version"],
            mode=mode,
            context=AssessmentContext.from_dict(item["context"]),
            candidates=candidates,
            attestation=(
                None
                if item["attestation"] is None
                else AssessmentAttestation.from_dict(item["attestation"])
            ),
        )

    def attestation_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "context": self.context.as_dict(),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.attestation_payload(),
            "attestation": self.attestation.as_dict() if self.attestation else None,
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
class EvidenceAttestationStatus:
    verified: bool
    key_id: str | None
    error: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "key_id": self.key_id,
            "error": self.error,
        }


@dataclass(frozen=True)
class AssessmentResult:
    assessment_digest: str
    decision_config_digest: str
    repository_id: str
    base_commit: str
    task_digest: str
    evidence_attestation: EvidenceAttestationStatus
    provider: ProviderMetadata | None
    scorer_error: str | None
    test_only: bool
    evaluations: tuple[CandidateEvaluation, ...]
    selection: SelectionResult
    schema_version: str = "prman-assessment-result/1.1"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assessment_digest": self.assessment_digest,
            "decision_config_digest": self.decision_config_digest,
            "repository_id": self.repository_id,
            "base_commit": self.base_commit,
            "task_digest": self.task_digest,
            "evidence_attestation": self.evidence_attestation.as_dict(),
            "provider": self.provider.as_dict() if self.provider else None,
            "scorer_error": self.scorer_error,
            "test_only": self.test_only,
            "evaluations": [evaluation.as_dict() for evaluation in self.evaluations],
            "selection": self.selection.as_dict(),
            "policy": {
                "human_confirmation_required": True,
                "draft_only": True,
                "external_write_authorized": False,
            },
        }


def _unavailable_aggregate(code: str) -> AggregateResult:
    return AggregateResult(
        score=None,
        max_uncertainty=None,
        lcb=None,
        provisional_decision="abstain",
        reasons=(f"scorer_unavailable:{code}",),
        comparable=False,
    )


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ScorerUnavailableError):
        return "unavailable"
    if isinstance(exc, ContractError):
        return "contract_error"
    return "runtime_error"


def _verify_evidence_attestation(
    assessment: Assessment,
    policy: EvidenceAttestationPolicy | None,
) -> EvidenceAttestationStatus:
    if policy is None:
        return EvidenceAttestationStatus(False, None, "not_configured")
    if assessment.attestation is None:
        return EvidenceAttestationStatus(False, policy.key_id, "missing")
    if assessment.attestation.key_id != policy.key_id:
        return EvidenceAttestationStatus(False, policy.key_id, "key_mismatch")
    secret = os.environ.get(policy.hmac_secret_env)
    if secret is None:
        return EvidenceAttestationStatus(False, policy.key_id, "secret_unavailable")
    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) < 32:
        return EvidenceAttestationStatus(False, policy.key_id, "secret_invalid")
    expected = hmac.new(
        secret_bytes,
        b"prman-evidence-v1\0" + canonical_json_bytes(assessment.attestation_payload()),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(assessment.attestation.signature, expected):
        return EvidenceAttestationStatus(False, policy.key_id, "signature_invalid")
    return EvidenceAttestationStatus(True, policy.key_id, None)


class AssessmentEngine:
    def __init__(
        self,
        decision_config: DecisionConfig,
        scorer: ScorerProvider | None = None,
        *,
        scorer_failure: str | None = None,
    ) -> None:
        if scorer is not None and scorer_failure is not None:
            raise ContractError("scorer and scorer_failure cannot both be configured")
        self.decision_config = decision_config
        self.scorer = scorer
        self.initial_scorer_failure = scorer_failure
        self.decision = MonotoneDecision(decision_config)

    def run(self, assessment: Assessment) -> AssessmentResult:
        evidence_attestation = _verify_evidence_attestation(
            assessment, self.decision_config.evidence_attestation
        )
        metadata: ProviderMetadata | None = None
        scorer_error = self.initial_scorer_failure
        if self.scorer is None and scorer_error is None:
            scorer_error = "not_configured"
        if self.scorer is not None:
            try:
                raw_metadata = self.scorer.metadata
                if not isinstance(raw_metadata, ProviderMetadata):
                    raise ContractError("scorer metadata must be ProviderMetadata")
                metadata = raw_metadata
            except Exception as exc:
                scorer_error = _failure_code(exc)

        test_only = metadata is not None and metadata.provider_id in TEST_ONLY_PROVIDER_IDS
        if (
            metadata is not None
            and not test_only
            and self.decision_config.scorer_binding != metadata
        ):
            scorer_error = "provider_not_bound_to_decision_config"

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
            if gates_passed and scorer_error is not None:
                aggregate = _unavailable_aggregate(scorer_error)
            elif gates_passed and self.scorer is not None and metadata is not None:
                request = ScorerRequest.create(
                    candidate_id=candidate.candidate_id,
                    repository_id=assessment.context.repository_id,
                    base_commit=assessment.context.base_commit,
                    task=assessment.context.task,
                    task_digest=assessment.context.task_digest,
                    repository_rules=assessment.context.repository_rules,
                    diff=candidate.diff,
                    gates=candidate.gates,
                )
                request_digest_before = request.request_digest
                try:
                    if self.scorer.metadata != metadata:
                        raise ContractError("scorer metadata changed during assessment")
                    raw_bundle = self.scorer.score(request)
                    if request.request_digest != request_digest_before:
                        raise ContractError("scorer mutated its request payload")
                    if self.scorer.metadata != metadata:
                        raise ContractError("scorer metadata changed during assessment")
                    score_bundle = validate_score_bundle(request, metadata, raw_bundle)
                    aggregate = self.decision.aggregate(
                        gates=candidate.gates,
                        score_bundle=score_bundle,
                        truncation_ratio=candidate.truncation_ratio,
                    )
                except Exception as exc:
                    scorer_error = _failure_code(exc)
                    score_bundle = None
                    aggregate = _unavailable_aggregate(scorer_error)
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
        if selection.decision == "ready" and scorer_error is not None:
            selection = SelectionResult(
                decision="abstain",
                candidate_id=None,
                margin=None,
                reason=f"scorer_unavailable:{scorer_error}",
            )
        if selection.decision == "ready" and not evidence_attestation.verified:
            selection = SelectionResult(
                decision="abstain",
                candidate_id=None,
                margin=None,
                reason=f"evidence_attestation:{evidence_attestation.error}",
            )
        if test_only:
            selection = SelectionResult(
                decision="abstain",
                candidate_id=None,
                margin=None,
                reason="test-only scorer cannot issue a readiness decision",
            )
        return AssessmentResult(
            assessment_digest=canonical_digest(assessment.as_dict()),
            decision_config_digest=canonical_digest(self.decision_config.as_dict()),
            repository_id=assessment.context.repository_id,
            base_commit=assessment.context.base_commit,
            task_digest=assessment.context.task_digest,
            evidence_attestation=evidence_attestation,
            provider=metadata,
            scorer_error=scorer_error,
            test_only=test_only,
            evaluations=tuple(evaluations),
            selection=selection,
        )
