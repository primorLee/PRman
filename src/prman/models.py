from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

from prman.validation import (
    ContractError,
    exact_fields,
    require_object,
    require_probability,
    require_sha256,
    require_string,
)

ALL_CRITERIA = (
    "correctness",
    "task_alignment",
    "scope",
    "repository_conventions",
    "maintainability",
    "reviewer_effort",
)

Decision = Literal["ready", "revise", "abstain"]
GateStatus = Literal["pass", "fail", "unknown"]


@dataclass(frozen=True)
class GateResult:
    name: str
    status: GateStatus
    recoverable: bool
    code: str
    evidence: Mapping[str, Any]
    actionable: str | None

    def __post_init__(self) -> None:
        require_string(self.name, path="gate.name")
        if self.status not in {"pass", "fail", "unknown"}:
            raise ContractError(f"gate {self.name}: unsupported status {self.status!r}")
        if not isinstance(self.recoverable, bool):
            raise ContractError(f"gate {self.name}: recoverable must be boolean")
        if self.status != "fail" and self.recoverable:
            raise ContractError(f"gate {self.name}: only failures may be recoverable")
        require_string(self.code, path=f"gate.{self.name}.code")
        if not isinstance(self.evidence, Mapping):
            raise ContractError(f"gate {self.name}: evidence must be an object")
        if self.actionable is not None:
            require_string(self.actionable, path=f"gate.{self.name}.actionable")

    @classmethod
    def from_dict(cls, value: Any, *, path: str = "gate") -> GateResult:
        item = require_object(value, path=path)
        exact_fields(
            item,
            {"name", "status", "recoverable", "code", "evidence", "actionable"},
            path=path,
        )
        evidence = require_object(item["evidence"], path=f"{path}.evidence")
        return cls(
            name=item["name"],
            status=item["status"],
            recoverable=item["recoverable"],
            code=item["code"],
            evidence=dict(evidence),
            actionable=item["actionable"],
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    provider_version: str
    model_revision: str
    calibrator_version: str
    protocol_version: str = "prman-scorer-plugin/1.0"

    def __post_init__(self) -> None:
        if self.protocol_version != "prman-scorer-plugin/1.0":
            raise ContractError(f"unsupported scorer protocol {self.protocol_version!r}")
        for field in (
            "provider_id",
            "provider_version",
            "model_revision",
            "calibrator_version",
        ):
            require_string(getattr(self, field), path=f"provider.{field}")

    @classmethod
    def from_dict(cls, value: Any) -> ProviderMetadata:
        item = require_object(value, path="provider")
        exact_fields(
            item,
            {
                "protocol_version",
                "provider_id",
                "provider_version",
                "model_revision",
                "calibrator_version",
            },
            path="provider",
        )
        return cls(**item)

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class CriterionScore:
    criterion: str
    probability: float
    uncertainty: float
    evidence: tuple[str, ...]
    actionable_critique: str | None
    ood: bool

    def __post_init__(self) -> None:
        require_string(self.criterion, path="score.criterion")
        require_probability(self.probability, path=f"score.{self.criterion}.probability")
        require_probability(self.uncertainty, path=f"score.{self.criterion}.uncertainty")
        if any(not isinstance(item, str) or not item for item in self.evidence):
            raise ContractError(f"score.{self.criterion}.evidence contains an invalid item")
        if self.actionable_critique is not None:
            require_string(
                self.actionable_critique,
                path=f"score.{self.criterion}.actionable_critique",
            )
        if not isinstance(self.ood, bool):
            raise ContractError(f"score.{self.criterion}.ood must be boolean")

    @classmethod
    def from_dict(cls, value: Any, *, path: str = "score") -> CriterionScore:
        item = require_object(value, path=path)
        exact_fields(
            item,
            {
                "criterion",
                "probability",
                "uncertainty",
                "evidence",
                "actionable_critique",
                "ood",
            },
            path=path,
        )
        evidence = item["evidence"]
        if not isinstance(evidence, list):
            raise ContractError(f"{path}.evidence: expected an array")
        return cls(
            criterion=item["criterion"],
            probability=require_probability(item["probability"], path=f"{path}.probability"),
            uncertainty=require_probability(item["uncertainty"], path=f"{path}.uncertainty"),
            evidence=tuple(evidence),
            actionable_critique=item["actionable_critique"],
            ood=item["ood"],
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "probability": self.probability,
            "uncertainty": self.uncertainty,
            "evidence": list(self.evidence),
            "actionable_critique": self.actionable_critique,
            "ood": self.ood,
        }


@dataclass(frozen=True)
class ScoreBundle:
    candidate_id: str
    request_digest: str
    provider: ProviderMetadata
    scores: tuple[CriterionScore, ...]
    schema_version: str = "prman-score-bundle/1.0"

    def __post_init__(self) -> None:
        if self.schema_version != "prman-score-bundle/1.0":
            raise ContractError(f"unsupported score bundle {self.schema_version!r}")
        require_sha256(self.candidate_id, path="score_bundle.candidate_id")
        require_sha256(self.request_digest, path="score_bundle.request_digest")
        criteria = [score.criterion for score in self.scores]
        if len(criteria) != len(set(criteria)):
            raise ContractError("score bundle contains duplicate criteria")

    @classmethod
    def from_dict(cls, value: Any) -> ScoreBundle:
        item = require_object(value, path="score_bundle")
        exact_fields(
            item,
            {"schema_version", "candidate_id", "request_digest", "provider", "scores"},
            path="score_bundle",
        )
        scores = item["scores"]
        if not isinstance(scores, list):
            raise ContractError("score_bundle.scores: expected an array")
        return cls(
            schema_version=item["schema_version"],
            candidate_id=item["candidate_id"],
            request_digest=item["request_digest"],
            provider=ProviderMetadata.from_dict(item["provider"]),
            scores=tuple(
                CriterionScore.from_dict(score, path=f"score_bundle.scores[{index}]")
                for index, score in enumerate(scores)
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "request_digest": self.request_digest,
            "provider": self.provider.as_dict(),
            "scores": [score.as_dict() for score in self.scores],
        }
