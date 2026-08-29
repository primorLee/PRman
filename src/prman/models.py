from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from prman.validation import (
    ContractError,
    exact_fields,
    require_list,
    require_object,
    require_probability,
    require_sha256,
    require_string,
    require_timestamp,
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
EvidenceSource = Literal["command", "inspection", "service"]


@dataclass(frozen=True)
class EvidenceRecord:
    source: EvidenceSource
    candidate_id: str
    observed_at: str
    producer: str
    producer_version: str
    summary: str
    log_digest: str
    command: tuple[str, ...] | None
    exit_code: int | None

    def __post_init__(self) -> None:
        if self.source not in {"command", "inspection", "service"}:
            raise ContractError(f"evidence.source: unsupported value {self.source!r}")
        require_sha256(self.candidate_id, path="evidence.candidate_id")
        require_timestamp(self.observed_at, path="evidence.observed_at")
        require_string(self.producer, path="evidence.producer")
        require_string(self.producer_version, path="evidence.producer_version")
        require_string(self.summary, path="evidence.summary")
        require_sha256(self.log_digest, path="evidence.log_digest")
        if self.source == "command":
            if not isinstance(self.command, tuple):
                raise ContractError("command evidence requires an immutable command tuple")
            if not self.command or any(
                not isinstance(item, str) or not item for item in self.command
            ):
                raise ContractError("command evidence requires a non-empty command array")
            if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
                raise ContractError("command evidence requires an integer exit_code")
        elif self.command is not None or self.exit_code is not None:
            raise ContractError("non-command evidence cannot contain command or exit_code")

    @classmethod
    def from_dict(cls, value: Any, *, path: str) -> EvidenceRecord:
        item = require_object(value, path=path)
        exact_fields(
            item,
            {
                "source",
                "candidate_id",
                "observed_at",
                "producer",
                "producer_version",
                "summary",
                "log_digest",
                "command",
                "exit_code",
            },
            path=path,
        )
        raw_command = item["command"]
        command: tuple[str, ...] | None
        if raw_command is None:
            command = None
        else:
            command = tuple(require_list(raw_command, path=f"{path}.command"))
        return cls(
            source=item["source"],
            candidate_id=item["candidate_id"],
            observed_at=item["observed_at"],
            producer=item["producer"],
            producer_version=item["producer_version"],
            summary=item["summary"],
            log_digest=item["log_digest"],
            command=command,
            exit_code=item["exit_code"],
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "candidate_id": self.candidate_id,
            "observed_at": self.observed_at,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "summary": self.summary,
            "log_digest": self.log_digest,
            "command": list(self.command) if self.command is not None else None,
            "exit_code": self.exit_code,
        }


@dataclass(frozen=True)
class GateResult:
    name: str
    status: GateStatus
    recoverable: bool
    code: str
    evidence: EvidenceRecord
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
        if not isinstance(self.evidence, EvidenceRecord):
            raise ContractError(f"gate {self.name}: evidence must be an EvidenceRecord")
        if self.actionable is not None:
            require_string(self.actionable, path=f"gate.{self.name}.actionable")
        if self.recoverable and self.actionable is None:
            raise ContractError(f"gate {self.name}: recoverable failure requires actionable advice")
        if (
            self.status == "pass"
            and self.evidence.source == "command"
            and self.evidence.exit_code != 0
        ):
            raise ContractError(f"gate {self.name}: passing command evidence requires exit_code 0")
        if self.name == "tests" and self.status == "pass" and self.evidence.source != "command":
            raise ContractError("gate tests: pass requires command evidence")

    def validate_candidate(self, candidate_id: str) -> None:
        if self.evidence.candidate_id != candidate_id:
            raise ContractError(f"gate {self.name}: evidence candidate_id mismatch")

    @classmethod
    def from_dict(cls, value: Any, *, path: str = "gate") -> GateResult:
        item = require_object(value, path=path)
        exact_fields(
            item,
            {"name", "status", "recoverable", "code", "evidence", "actionable"},
            path=path,
        )
        return cls(
            name=item["name"],
            status=item["status"],
            recoverable=item["recoverable"],
            code=item["code"],
            evidence=EvidenceRecord.from_dict(item["evidence"], path=f"{path}.evidence"),
            actionable=item["actionable"],
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "recoverable": self.recoverable,
            "code": self.code,
            "evidence": self.evidence.as_dict(),
            "actionable": self.actionable,
        }


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    provider_version: str
    model_revision: str
    calibrator_version: str
    protocol_version: str = "prman-scorer-plugin/1.1"

    def __post_init__(self) -> None:
        if self.protocol_version != "prman-scorer-plugin/1.1":
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
        if not isinstance(self.evidence, tuple):
            raise ContractError(f"score.{self.criterion}.evidence must be a tuple")
        if not self.evidence or any(
            not isinstance(item, str) or not item for item in self.evidence
        ):
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
    schema_version: str = "prman-score-bundle/1.1"

    def __post_init__(self) -> None:
        if self.schema_version != "prman-score-bundle/1.1":
            raise ContractError(f"unsupported score bundle {self.schema_version!r}")
        require_sha256(self.candidate_id, path="score_bundle.candidate_id")
        require_sha256(self.request_digest, path="score_bundle.request_digest")
        if not isinstance(self.provider, ProviderMetadata):
            raise ContractError("score_bundle.provider must be ProviderMetadata")
        if not isinstance(self.scores, tuple) or any(
            not isinstance(score, CriterionScore) for score in self.scores
        ):
            raise ContractError("score_bundle.scores must contain CriterionScore values")
        criteria = [score.criterion for score in self.scores]
        if tuple(criteria) != ALL_CRITERIA:
            raise ContractError("score bundle criteria must appear exactly once in canonical order")

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
