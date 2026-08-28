from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from prman.models import ALL_CRITERIA, ProviderMetadata, ScoreBundle
from prman.validation import (
    ContractError,
    assert_no_forbidden_scorer_fields,
    canonical_digest,
    exact_fields,
    require_object,
    require_sha256,
)


@dataclass(frozen=True)
class ScorerRequest:
    candidate_id: str
    payloads: Mapping[str, Mapping[str, Any]]
    schema_version: str = "prman-scorer-request/1.0"

    def __post_init__(self) -> None:
        if self.schema_version != "prman-scorer-request/1.0":
            raise ContractError(f"unsupported scorer request {self.schema_version!r}")
        require_sha256(self.candidate_id, path="scorer_request.candidate_id")
        if set(self.payloads) != set(ALL_CRITERIA):
            raise ContractError("scorer request must contain exactly the six criteria")
        for criterion, payload in self.payloads.items():
            if not isinstance(payload, Mapping):
                raise ContractError(f"scorer payload {criterion} must be an object")
            if payload.get("criterion") != criterion:
                raise ContractError(f"payload criterion mismatch for {criterion}")
            assert_no_forbidden_scorer_fields(payload)

    @classmethod
    def from_dict(cls, value: Any) -> ScorerRequest:
        item = require_object(value, path="scorer_request")
        exact_fields(
            item,
            {"schema_version", "candidate_id", "payloads"},
            path="scorer_request",
        )
        payloads = require_object(item["payloads"], path="scorer_request.payloads")
        normalized: dict[str, Mapping[str, Any]] = {}
        for criterion, payload in payloads.items():
            normalized[criterion] = dict(
                require_object(payload, path=f"scorer_request.payloads.{criterion}")
            )
        return cls(
            schema_version=item["schema_version"],
            candidate_id=item["candidate_id"],
            payloads=normalized,
        )

    @property
    def request_digest(self) -> str:
        return canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "payloads": {key: dict(value) for key, value in self.payloads.items()},
        }


class ScorerProvider(Protocol):
    @property
    def metadata(self) -> ProviderMetadata: ...

    def score(self, request: ScorerRequest) -> ScoreBundle: ...


class ScorerFactory(Protocol):
    def __call__(self, options: Mapping[str, Any]) -> ScorerProvider: ...


def validate_score_bundle(
    request: ScorerRequest,
    provider: ScorerProvider,
    bundle: ScoreBundle,
) -> ScoreBundle:
    if bundle.candidate_id != request.candidate_id:
        raise ContractError("scorer returned a different candidate_id")
    if bundle.request_digest != request.request_digest:
        raise ContractError("scorer returned a stale or mismatched request digest")
    if bundle.provider != provider.metadata:
        raise ContractError("scorer metadata changed during a request")
    criteria = tuple(score.criterion for score in bundle.scores)
    if set(criteria) != set(ALL_CRITERIA) or len(criteria) != len(ALL_CRITERIA):
        raise ContractError("scorer must return each required criterion exactly once")
    ordered = tuple(sorted(bundle.scores, key=lambda item: ALL_CRITERIA.index(item.criterion)))
    return ScoreBundle(
        candidate_id=bundle.candidate_id,
        request_digest=bundle.request_digest,
        provider=bundle.provider,
        scores=ordered,
    )
