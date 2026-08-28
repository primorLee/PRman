from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from prman.models import ALL_CRITERIA, CriterionScore, ProviderMetadata, ScoreBundle
from prman.scorers.protocols import ScorerRequest
from prman.validation import (
    ContractError,
    exact_fields,
    load_json,
    parse_json,
    require_object,
    require_probability,
    require_string,
)


def _metadata(provider_id: str, options: Mapping[str, Any]) -> ProviderMetadata:
    return ProviderMetadata(
        provider_id=provider_id,
        provider_version=require_string(
            options["provider_version"], path=f"{provider_id}.provider_version"
        ),
        model_revision=require_string(
            options["model_revision"], path=f"{provider_id}.model_revision"
        ),
        calibrator_version=require_string(
            options["calibrator_version"], path=f"{provider_id}.calibrator_version"
        ),
    )


def _scores_from_mapping(raw: Any, *, path: str) -> tuple[CriterionScore, ...]:
    items = require_object(raw, path=path)
    if set(items) != set(ALL_CRITERIA):
        raise ContractError(f"{path}: scores must cover exactly the six criteria")
    scores: list[CriterionScore] = []
    for criterion in ALL_CRITERIA:
        item = require_object(items[criterion], path=f"{path}.{criterion}")
        exact_fields(
            item,
            {"probability", "uncertainty", "evidence", "actionable_critique", "ood"},
            path=f"{path}.{criterion}",
        )
        evidence = item["evidence"]
        if not isinstance(evidence, list):
            raise ContractError(f"{path}.{criterion}.evidence must be an array")
        scores.append(
            CriterionScore(
                criterion=criterion,
                probability=require_probability(
                    item["probability"], path=f"{path}.{criterion}.probability"
                ),
                uncertainty=require_probability(
                    item["uncertainty"], path=f"{path}.{criterion}.uncertainty"
                ),
                evidence=tuple(evidence),
                actionable_critique=item["actionable_critique"],
                ood=item["ood"],
            )
        )
    return tuple(scores)


class StaticScorer:
    def __init__(self, options: Mapping[str, Any]) -> None:
        exact_fields(
            options,
            {
                "provider_version",
                "model_revision",
                "calibrator_version",
                "probability",
                "uncertainty",
            },
            path="builtin.static",
        )
        self._metadata = _metadata("builtin.static", options)
        self.probability = require_probability(
            options["probability"], path="builtin.static.probability"
        )
        self.uncertainty = require_probability(
            options["uncertainty"], path="builtin.static.uncertainty"
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def score(self, request: ScorerRequest) -> ScoreBundle:
        return ScoreBundle(
            candidate_id=request.candidate_id,
            request_digest=request.request_digest,
            provider=self.metadata,
            scores=tuple(
                CriterionScore(
                    criterion=criterion,
                    probability=self.probability,
                    uncertainty=self.uncertainty,
                    evidence=("test-only static scorer",),
                    actionable_critique=None,
                    ood=False,
                )
                for criterion in ALL_CRITERIA
            ),
        )


class FixtureJsonScorer:
    def __init__(self, options: Mapping[str, Any]) -> None:
        exact_fields(
            options,
            {
                "provider_version",
                "model_revision",
                "calibrator_version",
                "fixture_path",
            },
            path="builtin.fixture-json",
        )
        self._metadata = _metadata("builtin.fixture-json", options)
        fixture_path = Path(
            require_string(options["fixture_path"], path="builtin.fixture-json.fixture_path")
        )
        fixture = require_object(load_json(fixture_path), path="scorer_fixture")
        exact_fields(fixture, {"schema_version", "candidates"}, path="scorer_fixture")
        if fixture["schema_version"] != "prman-scorer-fixture/1.0":
            raise ContractError(f"unsupported scorer fixture {fixture['schema_version']!r}")
        self.candidates = dict(
            require_object(fixture["candidates"], path="scorer_fixture.candidates")
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def score(self, request: ScorerRequest) -> ScoreBundle:
        raw = self.candidates.get(request.candidate_id, self.candidates.get("*"))
        if raw is None:
            raise ContractError(f"no fixture score for candidate {request.candidate_id}")
        return ScoreBundle(
            candidate_id=request.candidate_id,
            request_digest=request.request_digest,
            provider=self.metadata,
            scores=_scores_from_mapping(raw, path=f"scorer_fixture.{request.candidate_id}"),
        )


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


class LocalHttpScorer:
    def __init__(self, options: Mapping[str, Any]) -> None:
        exact_fields(
            options,
            {
                "provider_version",
                "model_revision",
                "calibrator_version",
                "endpoint",
                "timeout_seconds",
            },
            path="builtin.local-http",
        )
        self._metadata = _metadata("builtin.local-http", options)
        self.endpoint = require_string(options["endpoint"], path="builtin.local-http.endpoint")
        parsed = urlparse(self.endpoint)
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
        except ValueError as exc:
            raise ContractError(
                "local scorer endpoint must use a numeric loopback address"
            ) from exc
        if parsed.scheme != "http" or not address.is_loopback:
            raise ContractError("local scorer endpoint must use loopback HTTP")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ContractError(
                "local scorer endpoint cannot contain credentials, query, or fragment"
            )
        timeout = options["timeout_seconds"]
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 < timeout <= 300
        ):
            raise ContractError("local scorer timeout_seconds must be in (0, 300]")
        self.timeout_seconds = float(timeout)
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def score(self, request: ScorerRequest) -> ScoreBundle:
        body = json.dumps(
            {
                "schema_version": "prman-scorer-service-request/1.0",
                "request_digest": request.request_digest,
                "request": request.as_dict(),
            },
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        ).encode("utf-8")
        http_request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(http_request, timeout=self.timeout_seconds) as response:
                response_body = response.read(4 * 1024 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ContractError(f"local scorer request failed: {exc}") from exc
        if len(response_body) > 4 * 1024 * 1024:
            raise ContractError("local scorer response exceeds 4 MiB")
        raw = parse_json(response_body, path="local scorer response")
        value = require_object(raw, path="scorer_response")
        exact_fields(
            value,
            {"schema_version", "request_digest", "scores"},
            path="scorer_response",
        )
        if value["schema_version"] != "prman-scorer-service-response/1.0":
            raise ContractError(f"unsupported scorer response {value['schema_version']!r}")
        if value["request_digest"] != request.request_digest:
            raise ContractError("local scorer response request digest mismatch")
        raw_scores = value["scores"]
        if not isinstance(raw_scores, list):
            raise ContractError("scorer_response.scores must be an array")
        mapped: dict[str, Any] = {}
        for index, score in enumerate(raw_scores):
            item = require_object(score, path=f"scorer_response.scores[{index}]")
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
                path=f"scorer_response.scores[{index}]",
            )
            criterion = item["criterion"]
            if criterion in mapped:
                raise ContractError(f"duplicate scorer response criterion {criterion!r}")
            mapped[criterion] = {key: value for key, value in item.items() if key != "criterion"}
        return ScoreBundle(
            candidate_id=request.candidate_id,
            request_digest=request.request_digest,
            provider=self.metadata,
            scores=_scores_from_mapping(mapped, path="scorer_response.scores"),
        )


def static_factory(options: Mapping[str, Any]) -> StaticScorer:
    return StaticScorer(options)


def fixture_json_factory(options: Mapping[str, Any]) -> FixtureJsonScorer:
    return FixtureJsonScorer(options)


def local_http_factory(options: Mapping[str, Any]) -> LocalHttpScorer:
    return LocalHttpScorer(options)
