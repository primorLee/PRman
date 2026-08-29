from __future__ import annotations

from collections.abc import Mapping
from importlib import metadata
from typing import Any

from prman.models import ProviderMetadata
from prman.scorers.builtin import fixture_json_factory, local_http_factory, static_factory
from prman.scorers.protocols import (
    TEST_ONLY_PROVIDER_IDS,
    ScorerFactory,
    ScorerProvider,
    ScorerUnavailableError,
)
from prman.validation import ContractError

ENTRY_POINT_GROUP = "prman.scorers"


class ScorerRegistry:
    def __init__(self) -> None:
        self._builtins: dict[str, ScorerFactory] = {
            "builtin.fixture-json": fixture_json_factory,
            "builtin.local-http": local_http_factory,
            "builtin.static": static_factory,
        }

    def names(self) -> tuple[str, ...]:
        return tuple(sorted((*self._builtins, *self._external_entry_points())))

    def is_test_only(self, name: str) -> bool:
        return name in TEST_ONLY_PROVIDER_IDS

    def trust_classification(self, name: str) -> str:
        if self.is_test_only(name):
            return "test-only"
        if name == "builtin.local-http":
            return "authenticated-service"
        if name in self._external_entry_points():
            return "trusted-in-process"
        raise ContractError(f"unknown scorer {name!r}; available={list(self.names())}")

    def _external_entry_points(self) -> dict[str, metadata.EntryPoint]:
        discovered: dict[str, metadata.EntryPoint] = {}
        for entry_point in metadata.entry_points(group=ENTRY_POINT_GROUP):
            if entry_point.name in self._builtins:
                raise ContractError(f"external scorer cannot replace builtin {entry_point.name!r}")
            if entry_point.name in discovered:
                raise ContractError(f"duplicate scorer entry point {entry_point.name!r}")
            discovered[entry_point.name] = entry_point
        return discovered

    def create(
        self,
        name: str,
        options: Mapping[str, Any],
        *,
        allow_trusted_python: bool = False,
    ) -> ScorerProvider:
        factory = self._builtins.get(name)
        external = factory is None
        if factory is None:
            entry_point = self._external_entry_points().get(name)
            if entry_point is None:
                raise ContractError(f"unknown scorer {name!r}; available={list(self.names())}")
            if not allow_trusted_python:
                raise ContractError(
                    f"scorer {name!r} executes trusted code in the PRman process; "
                    "explicit trusted-Python opt-in is required"
                )
            try:
                loaded = entry_point.load()
            except Exception as exc:
                raise ScorerUnavailableError(
                    f"trusted Python scorer {name!r} failed to load"
                ) from exc
            if not callable(loaded):
                raise ScorerUnavailableError(f"scorer entry point {name!r} is not callable")
            factory = loaded
        try:
            provider = factory(options)
        except ScorerUnavailableError:
            raise
        except ContractError as exc:
            if external:
                raise ScorerUnavailableError(
                    f"trusted Python scorer {name!r} rejected its configuration"
                ) from exc
            raise
        except Exception as exc:
            error = ScorerUnavailableError if external else ContractError
            raise error(
                f"scorer {name!r} failed to initialize: {type(exc).__name__}: {exc}"
            ) from exc
        try:
            provider_metadata = provider.metadata
            score = provider.score
        except Exception as exc:
            raise ScorerUnavailableError(f"scorer {name!r} metadata is unavailable") from exc
        if not isinstance(provider_metadata, ProviderMetadata) or not callable(score):
            error = ScorerUnavailableError if external else ContractError
            raise error(f"scorer {name!r} does not implement the protocol")
        if provider_metadata.provider_id != name:
            error = ScorerUnavailableError if external else ContractError
            raise error(
                f"scorer provider ID {provider_metadata.provider_id!r} does not match {name!r}"
            )
        return provider
