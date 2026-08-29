from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

from prman.models import ALL_CRITERIA, Decision, GateResult, ProviderMetadata, ScoreBundle
from prman.validation import (
    ContractError,
    exact_fields,
    require_environment_variable,
    require_object,
    require_probability,
    require_string,
)

ProvisionalDecision = Literal["eligible", "revise", "abstain"]


@dataclass(frozen=True)
class EvidenceAttestationPolicy:
    key_id: str
    hmac_secret_env: str
    scheme: str = "hmac-sha256"

    def __post_init__(self) -> None:
        if self.scheme != "hmac-sha256":
            raise ContractError(f"unsupported evidence attestation scheme {self.scheme!r}")
        require_string(self.key_id, path="decision_config.evidence_attestation.key_id")
        require_environment_variable(
            self.hmac_secret_env,
            path="decision_config.evidence_attestation.hmac_secret_env",
        )

    @classmethod
    def from_dict(cls, value: Any) -> EvidenceAttestationPolicy:
        item = require_object(value, path="decision_config.evidence_attestation")
        exact_fields(
            item,
            {"scheme", "key_id", "hmac_secret_env"},
            path="decision_config.evidence_attestation",
        )
        return cls(**item)

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class DecisionConfig:
    required_gates: tuple[str, ...]
    weights: Mapping[str, float]
    critical_min: Mapping[str, float]
    soft_min: Mapping[str, float]
    ready_score: float
    ready_lcb_min: float
    revise_floor: float
    ready_uncertainty_max: float
    abstain_uncertainty: float
    top_margin_min: float
    max_context_truncation_ratio: float
    lcb_uncertainty_weight: float
    scorer_binding: ProviderMetadata | None
    evidence_attestation: EvidenceAttestationPolicy | None
    schema_version: str = "prman-decision-config/1.1"

    @classmethod
    def from_mapping(cls, value: Any) -> DecisionConfig:
        item = require_object(value, path="decision_config")
        exact_fields(
            item,
            {
                "schema_version",
                "required_gates",
                "criteria",
                "weights",
                "critical_min",
                "soft_min",
                "ready_score",
                "ready_lcb_min",
                "revise_floor",
                "ready_uncertainty_max",
                "abstain_uncertainty",
                "top_margin_min",
                "max_context_truncation_ratio",
                "lcb_uncertainty_weight",
                "scorer_binding",
                "evidence_attestation",
            },
            path="decision_config",
        )
        if item["schema_version"] != "prman-decision-config/1.1":
            raise ContractError(f"unsupported decision config {item['schema_version']!r}")
        criteria = item["criteria"]
        if not isinstance(criteria, list) or tuple(criteria) != ALL_CRITERIA:
            raise ContractError("decision criteria order has drifted")
        required_gates = item["required_gates"]
        if not isinstance(required_gates, list) or not required_gates:
            raise ContractError("decision_config.required_gates must be a non-empty array")
        if len(required_gates) != len(set(required_gates)):
            raise ContractError("decision_config.required_gates contains duplicates")
        for index, name in enumerate(required_gates):
            require_string(name, path=f"decision_config.required_gates[{index}]")
        weights = require_object(item["weights"], path="decision_config.weights")
        critical = require_object(item["critical_min"], path="decision_config.critical_min")
        soft = require_object(item["soft_min"], path="decision_config.soft_min")
        lcb_weight = item["lcb_uncertainty_weight"]
        if (
            isinstance(lcb_weight, bool)
            or not isinstance(lcb_weight, (int, float))
            or not math.isfinite(lcb_weight)
            or lcb_weight < 0
        ):
            raise ContractError("LCB uncertainty weight must be finite and non-negative")
        config = cls(
            schema_version=item["schema_version"],
            required_gates=tuple(required_gates),
            weights={
                key: require_probability(number, path=f"decision_config.weights.{key}")
                for key, number in weights.items()
            },
            critical_min={
                key: require_probability(number, path=f"decision_config.critical_min.{key}")
                for key, number in critical.items()
            },
            soft_min={
                key: require_probability(number, path=f"decision_config.soft_min.{key}")
                for key, number in soft.items()
            },
            ready_score=require_probability(
                item["ready_score"], path="decision_config.ready_score"
            ),
            ready_lcb_min=require_probability(
                item["ready_lcb_min"], path="decision_config.ready_lcb_min"
            ),
            revise_floor=require_probability(
                item["revise_floor"], path="decision_config.revise_floor"
            ),
            ready_uncertainty_max=require_probability(
                item["ready_uncertainty_max"],
                path="decision_config.ready_uncertainty_max",
            ),
            abstain_uncertainty=require_probability(
                item["abstain_uncertainty"], path="decision_config.abstain_uncertainty"
            ),
            top_margin_min=require_probability(
                item["top_margin_min"], path="decision_config.top_margin_min"
            ),
            max_context_truncation_ratio=require_probability(
                item["max_context_truncation_ratio"],
                path="decision_config.max_context_truncation_ratio",
            ),
            lcb_uncertainty_weight=float(lcb_weight),
            scorer_binding=(
                None
                if item["scorer_binding"] is None
                else ProviderMetadata.from_dict(item["scorer_binding"])
            ),
            evidence_attestation=(
                None
                if item["evidence_attestation"] is None
                else EvidenceAttestationPolicy.from_dict(item["evidence_attestation"])
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if set(self.weights) != set(ALL_CRITERIA):
            raise ContractError("decision weights must cover exactly six criteria")
        if abs(sum(self.weights.values()) - 1.0) > 1e-9:
            raise ContractError("decision weights must sum to 1.0")
        if not set(self.critical_min) <= set(ALL_CRITERIA):
            raise ContractError("critical minima contain an unknown criterion")
        if not set(self.soft_min) <= set(ALL_CRITERIA):
            raise ContractError("soft minima contain an unknown criterion")
        if set(self.critical_min) & set(self.soft_min):
            raise ContractError("critical and soft minima cannot overlap")
        if set(self.critical_min) | set(self.soft_min) != set(ALL_CRITERIA):
            raise ContractError("critical and soft minima must cover all six criteria")
        for name, number in (
            *self.weights.items(),
            *self.critical_min.items(),
            *self.soft_min.items(),
        ):
            require_probability(number, path=f"decision_config.{name}")
        for name in (
            "ready_score",
            "ready_lcb_min",
            "revise_floor",
            "ready_uncertainty_max",
            "abstain_uncertainty",
            "top_margin_min",
            "max_context_truncation_ratio",
        ):
            require_probability(getattr(self, name), path=f"decision_config.{name}")
        if self.lcb_uncertainty_weight < 0 or not math.isfinite(self.lcb_uncertainty_weight):
            raise ContractError("LCB uncertainty weight must be finite and non-negative")
        if self.ready_score < self.revise_floor:
            raise ContractError("ready_score must be greater than or equal to revise_floor")
        if not self.revise_floor <= self.ready_lcb_min <= self.ready_score:
            raise ContractError("ready_lcb_min must be between revise_floor and ready_score")
        if self.ready_uncertainty_max > self.abstain_uncertainty:
            raise ContractError("ready_uncertainty_max cannot exceed abstain_uncertainty")
        if self.scorer_binding is not None and not isinstance(
            self.scorer_binding, ProviderMetadata
        ):
            raise ContractError("scorer_binding must be ProviderMetadata or null")
        if self.evidence_attestation is not None and not isinstance(
            self.evidence_attestation, EvidenceAttestationPolicy
        ):
            raise ContractError("evidence_attestation must be EvidenceAttestationPolicy or null")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "required_gates": list(self.required_gates),
            "criteria": list(ALL_CRITERIA),
            "weights": dict(self.weights),
            "critical_min": dict(self.critical_min),
            "soft_min": dict(self.soft_min),
            "ready_score": self.ready_score,
            "ready_lcb_min": self.ready_lcb_min,
            "revise_floor": self.revise_floor,
            "ready_uncertainty_max": self.ready_uncertainty_max,
            "abstain_uncertainty": self.abstain_uncertainty,
            "top_margin_min": self.top_margin_min,
            "max_context_truncation_ratio": self.max_context_truncation_ratio,
            "lcb_uncertainty_weight": self.lcb_uncertainty_weight,
            "scorer_binding": (
                self.scorer_binding.as_dict() if self.scorer_binding is not None else None
            ),
            "evidence_attestation": (
                self.evidence_attestation.as_dict()
                if self.evidence_attestation is not None
                else None
            ),
        }


@dataclass(frozen=True)
class AggregateResult:
    score: float | None
    max_uncertainty: float | None
    lcb: float | None
    provisional_decision: ProvisionalDecision
    reasons: tuple[str, ...]
    comparable: bool

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        return value


@dataclass(frozen=True)
class SelectionResult:
    decision: Decision
    candidate_id: str | None
    margin: float | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class MonotoneDecision:
    def __init__(self, config: DecisionConfig) -> None:
        config.validate()
        self.config = config

    def aggregate(
        self,
        *,
        gates: Sequence[GateResult],
        score_bundle: ScoreBundle | None,
        truncation_ratio: float,
    ) -> AggregateResult:
        require_probability(truncation_ratio, path="candidate.truncation_ratio")
        by_name = {gate.name: gate for gate in gates}
        if len(by_name) != len(gates):
            raise ContractError("candidate gates contain duplicate names")
        missing = sorted(set(self.config.required_gates) - set(by_name))
        if missing:
            return AggregateResult(
                None,
                None,
                None,
                "abstain",
                tuple(f"missing_gate:{name}" for name in missing),
                False,
            )
        blocking_gates = tuple(by_name[name] for name in self.config.required_gates)
        fatal = sorted(
            (gate for gate in blocking_gates if gate.status == "fail" and not gate.recoverable),
            key=lambda gate: gate.name,
        )
        if fatal:
            return AggregateResult(
                None,
                None,
                None,
                "abstain",
                tuple(f"hard_gate:{gate.name}:{gate.code}" for gate in fatal),
                False,
            )
        unknown = sorted(
            (gate for gate in blocking_gates if gate.status == "unknown"),
            key=lambda gate: gate.name,
        )
        if unknown:
            return AggregateResult(
                None,
                None,
                None,
                "abstain",
                tuple(f"unknown_gate:{gate.name}:{gate.code}" for gate in unknown),
                False,
            )
        recoverable = sorted(
            (gate for gate in blocking_gates if gate.status == "fail" and gate.recoverable),
            key=lambda gate: gate.name,
        )
        if recoverable:
            return AggregateResult(
                None,
                None,
                None,
                "revise",
                tuple(f"hard_gate:{gate.name}:{gate.code}" for gate in recoverable),
                False,
            )
        if score_bundle is None:
            return AggregateResult(
                None,
                None,
                None,
                "abstain",
                ("scorer_unavailable",),
                False,
            )

        score_by_name = {score.criterion: score for score in score_bundle.scores}
        if set(score_by_name) != set(ALL_CRITERIA):
            raise ContractError("score bundle does not cover all decision criteria")
        epsilon = 1e-9
        total = sum(
            self.config.weights[name] * math.log(max(epsilon, score_by_name[name].probability))
            for name in ALL_CRITERIA
        )
        score = math.exp(total)
        uncertainty = max(item.uncertainty for item in score_bundle.scores)
        lcb = score - self.config.lcb_uncertainty_weight * uncertainty - truncation_ratio
        reasons: list[str] = []
        if any(item.ood for item in score_bundle.scores):
            reasons.append("out_of_distribution")
        if uncertainty > self.config.abstain_uncertainty:
            reasons.append("uncertainty_above_abstain_threshold")
        if truncation_ratio > self.config.max_context_truncation_ratio:
            reasons.append("context_truncation_above_threshold")
        if reasons:
            return AggregateResult(
                score,
                uncertainty,
                lcb,
                "abstain",
                tuple(reasons),
                False,
            )

        minima = {**self.config.critical_min, **self.config.soft_min}
        minima_failures = sorted(
            name for name, minimum in minima.items() if score_by_name[name].probability < minimum
        )
        if (
            not minima_failures
            and score >= self.config.ready_score
            and lcb >= self.config.ready_lcb_min
            and uncertainty <= self.config.ready_uncertainty_max
        ):
            return AggregateResult(score, uncertainty, lcb, "eligible", (), True)
        if minima_failures:
            reasons.append(f"criterion_minimum:{','.join(minima_failures)}")
        if lcb < self.config.ready_lcb_min:
            reasons.append("lcb_below_ready_threshold")
        actionable = any(item.actionable_critique for item in score_bundle.scores)
        if score >= self.config.revise_floor and actionable:
            return AggregateResult(
                score,
                uncertainty,
                lcb,
                "revise",
                tuple(reasons or ["actionable"]),
                True,
            )
        reasons.append("below_revise_or_not_actionable")
        return AggregateResult(score, uncertainty, lcb, "abstain", tuple(reasons), True)

    def finalize(
        self,
        *,
        mode: Literal["single", "compare"],
        evaluations: Sequence[tuple[str, AggregateResult]],
    ) -> SelectionResult:
        ranked = sorted(
            (
                (candidate_id, result)
                for candidate_id, result in evaluations
                if result.lcb is not None and result.comparable
            ),
            key=lambda item: (-cast(float, item[1].lcb), item[0]),
        )
        if not ranked:
            revisable = [
                candidate_id
                for candidate_id, result in evaluations
                if result.provisional_decision == "revise"
            ]
            if len(revisable) == 1:
                return SelectionResult(
                    "revise",
                    revisable[0],
                    None,
                    "recoverable hard-gate failure",
                )
            if len(revisable) > 1:
                return SelectionResult(
                    "abstain",
                    None,
                    None,
                    "multiple candidates have recoverable gate failures; no quality ranking exists",
                )
            reasons = sorted({reason for _, result in evaluations for reason in result.reasons})
            reason = ";".join(reasons) if reasons else "no gate-passed scored candidate"
            return SelectionResult("abstain", None, None, reason)

        top_id, top = ranked[0]
        if top.provisional_decision != "eligible":
            if top.provisional_decision == "revise":
                return SelectionResult("revise", top_id, None, ";".join(top.reasons))
            return SelectionResult("abstain", None, None, ";".join(top.reasons))
        if mode == "single":
            return SelectionResult("ready", top_id, None, "all gates and thresholds passed")
        if mode != "compare":
            raise ContractError(f"unsupported assessment mode {mode!r}")
        if len(ranked) < 2:
            return SelectionResult(
                "abstain",
                None,
                None,
                "comparison readiness requires a scored runner-up",
            )
        margin = cast(float, top.lcb) - cast(float, ranked[1][1].lcb)
        if margin < self.config.top_margin_min:
            return SelectionResult(
                "abstain",
                None,
                margin,
                f"top LCB margin {margin:.6f} is below {self.config.top_margin_min:.6f}",
            )
        return SelectionResult(
            "ready",
            top_id,
            margin,
            "all gates, thresholds, and comparison margin passed",
        )
