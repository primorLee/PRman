from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from prman.models import ALL_CRITERIA, GateResult, ProviderMetadata, ScoreBundle
from prman.validation import (
    ContractError,
    canonical_digest,
    exact_fields,
    require_list,
    require_object,
    require_revision,
    require_sha256,
    require_string,
    sha256_text,
)

TEST_ONLY_PROVIDER_IDS = frozenset({"builtin.static", "builtin.fixture-json"})


class ScorerUnavailableError(ContractError):
    """Raised when a configured scorer cannot be initialized or contacted."""


@dataclass(frozen=True)
class ScorerEvidence:
    gate: str
    status: Literal["pass", "fail", "unknown"]
    code: str
    source: Literal["command", "inspection", "service"]
    summary: str
    log_digest: str

    def __post_init__(self) -> None:
        require_string(self.gate, path="scorer_evidence.gate")
        if self.status not in {"pass", "fail", "unknown"}:
            raise ContractError(f"scorer_evidence.status: unsupported value {self.status!r}")
        require_string(self.code, path="scorer_evidence.code")
        if self.source not in {"command", "inspection", "service"}:
            raise ContractError(f"scorer_evidence.source: unsupported value {self.source!r}")
        require_string(self.summary, path="scorer_evidence.summary")
        require_sha256(self.log_digest, path="scorer_evidence.log_digest")

    @classmethod
    def from_dict(cls, value: Any, *, path: str) -> ScorerEvidence:
        item = require_object(value, path=path)
        exact_fields(
            item,
            {"gate", "status", "code", "source", "summary", "log_digest"},
            path=path,
        )
        return cls(**item)

    def as_dict(self) -> dict[str, str]:
        return {
            "gate": self.gate,
            "status": self.status,
            "code": self.code,
            "source": self.source,
            "summary": self.summary,
            "log_digest": self.log_digest,
        }


@dataclass(frozen=True)
class ScorerRequest:
    candidate_id: str
    repository_id: str
    base_commit: str
    task: str
    task_digest: str
    repository_rules: tuple[str, ...]
    diff: str
    evidence: tuple[ScorerEvidence, ...]
    schema_version: str = "prman-scorer-request/1.1"

    def __post_init__(self) -> None:
        if self.schema_version != "prman-scorer-request/1.1":
            raise ContractError(f"unsupported scorer request {self.schema_version!r}")
        require_sha256(self.candidate_id, path="scorer_request.candidate_id")
        require_sha256(self.repository_id, path="scorer_request.context.repository_id")
        require_revision(self.base_commit, path="scorer_request.context.base_commit")
        require_string(self.task, path="scorer_request.context.task")
        require_sha256(self.task_digest, path="scorer_request.context.task_digest")
        if sha256_text(self.task) != self.task_digest:
            raise ContractError("scorer request task_digest does not match task text")
        if not isinstance(self.diff, str) or not self.diff:
            raise ContractError("scorer_request.context.diff: expected a non-empty string")
        if sha256_text(self.diff) != self.candidate_id:
            raise ContractError("scorer request candidate_id does not match diff bytes")
        if not isinstance(self.repository_rules, tuple):
            raise ContractError("scorer request repository_rules must be a tuple")
        if any(not isinstance(rule, str) or not rule.strip() for rule in self.repository_rules):
            raise ContractError("scorer request repository_rules contains an invalid item")
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(item, ScorerEvidence) for item in self.evidence
        ):
            raise ContractError("scorer request evidence must contain ScorerEvidence values")
        gate_names = [item.gate for item in self.evidence]
        if not gate_names:
            raise ContractError("scorer request evidence must not be empty")
        if len(gate_names) != len(set(gate_names)):
            raise ContractError("scorer request evidence contains duplicate gates")

    @classmethod
    def create(
        cls,
        *,
        candidate_id: str,
        repository_id: str,
        base_commit: str,
        task: str,
        task_digest: str,
        repository_rules: Sequence[str],
        diff: str,
        gates: Sequence[GateResult],
    ) -> ScorerRequest:
        return cls(
            candidate_id=candidate_id,
            repository_id=repository_id,
            base_commit=base_commit,
            task=task,
            task_digest=task_digest,
            repository_rules=tuple(repository_rules),
            diff=diff,
            evidence=tuple(
                ScorerEvidence(
                    gate=gate.name,
                    status=gate.status,
                    code=gate.code,
                    source=gate.evidence.source,
                    summary=gate.evidence.summary,
                    log_digest=gate.evidence.log_digest,
                )
                for gate in gates
            ),
        )

    @classmethod
    def from_dict(cls, value: Any) -> ScorerRequest:
        item = require_object(value, path="scorer_request")
        exact_fields(
            item,
            {"schema_version", "candidate_id", "context", "criteria"},
            path="scorer_request",
        )
        criteria = require_list(item["criteria"], path="scorer_request.criteria")
        if tuple(criteria) != ALL_CRITERIA:
            raise ContractError("scorer request criteria must be in canonical order")
        context = require_object(item["context"], path="scorer_request.context")
        exact_fields(
            context,
            {
                "repository_id",
                "base_commit",
                "task",
                "task_digest",
                "repository_rules",
                "diff",
                "evidence",
            },
            path="scorer_request.context",
        )
        raw_rules = require_list(
            context["repository_rules"], path="scorer_request.context.repository_rules"
        )
        raw_evidence = require_list(context["evidence"], path="scorer_request.context.evidence")
        return cls(
            schema_version=item["schema_version"],
            candidate_id=item["candidate_id"],
            repository_id=context["repository_id"],
            base_commit=context["base_commit"],
            task=context["task"],
            task_digest=context["task_digest"],
            repository_rules=tuple(raw_rules),
            diff=context["diff"],
            evidence=tuple(
                ScorerEvidence.from_dict(evidence, path=f"scorer_request.context.evidence[{index}]")
                for index, evidence in enumerate(raw_evidence)
            ),
        )

    @property
    def request_digest(self) -> str:
        return canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "context": {
                "repository_id": self.repository_id,
                "base_commit": self.base_commit,
                "task": self.task,
                "task_digest": self.task_digest,
                "repository_rules": list(self.repository_rules),
                "diff": self.diff,
                "evidence": [item.as_dict() for item in self.evidence],
            },
            "criteria": list(ALL_CRITERIA),
        }


class ScorerProvider(Protocol):
    @property
    def metadata(self) -> ProviderMetadata: ...

    def score(self, request: ScorerRequest) -> ScoreBundle: ...


class ScorerFactory(Protocol):
    def __call__(self, options: Mapping[str, Any]) -> ScorerProvider: ...


def validate_score_bundle(
    request: ScorerRequest,
    provider_metadata: ProviderMetadata,
    bundle: ScoreBundle,
) -> ScoreBundle:
    if not isinstance(bundle, ScoreBundle):
        raise ContractError("scorer must return a ScoreBundle")
    if bundle.candidate_id != request.candidate_id:
        raise ContractError("scorer returned a different candidate_id")
    if bundle.request_digest != request.request_digest:
        raise ContractError("scorer returned a stale or mismatched request digest")
    if bundle.provider != provider_metadata:
        raise ContractError("scorer metadata changed during a request")
    criteria = tuple(score.criterion for score in bundle.scores)
    if criteria != ALL_CRITERIA:
        raise ContractError("scorer must return each required criterion in canonical order")
    return bundle
