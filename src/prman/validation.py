from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """Raised when an assessment or scorer contract is invalid."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_SCORER_FIELDS = frozenset(
    {
        "review",
        "reviews",
        "review_state",
        "review_comment",
        "review_comments",
        "approval",
        "approved",
        "merge",
        "merged",
        "merge_state",
        "revert",
        "reverted",
        "author",
        "author_id",
        "author_identity",
        "actor",
        "maintainer_identity",
        "selected_candidate",
        "selection_probability",
        "model_score",
        "reward",
    }
)


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def parse_json(value: str | bytes, *, path: str) -> Any:
    try:
        return json.loads(
            value,
            object_pairs_hook=_pairs_without_duplicates,
        )
    except ContractError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot parse JSON from {path}: {exc}") from exc


def load_json(path: Path) -> Any:
    try:
        value = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot read JSON from {path}: {exc}") from exc
    return parse_json(value, path=str(path))


def canonical_json_bytes(value: Any) -> bytes:
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ContractError(f"value is not canonical JSON data: {exc}") from exc
    return rendered.encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def exact_fields(value: Mapping[str, Any], expected: set[str], *, path: str) -> None:
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown or missing:
        raise ContractError(
            f"{path}: strict fields mismatch; unknown={sorted(unknown)}, missing={sorted(missing)}"
        )


def require_object(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{path}: expected an object")
    return value


def require_list(value: Any, *, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"{path}: expected an array")
    return value


def require_string(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{path}: expected a non-empty string")
    return value


def require_sha256(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ContractError(f"{path}: expected a lowercase SHA-256 digest")
    return value


def require_probability(value: Any, *, path: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ContractError(f"{path}: expected a finite number in [0, 1]")
    return float(value)


def normalize_field(name: str) -> str:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()


def find_forbidden_scorer_fields(value: Any, *, path: str = "$") -> tuple[str, ...]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if normalize_field(str(key)) in _FORBIDDEN_SCORER_FIELDS:
                findings.append(child_path)
            findings.extend(find_forbidden_scorer_fields(item, path=child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            findings.extend(find_forbidden_scorer_fields(item, path=f"{path}[{index}]"))
    return tuple(findings)


def assert_no_forbidden_scorer_fields(value: Any) -> None:
    findings = find_forbidden_scorer_fields(value)
    if findings:
        raise ContractError(f"future/identity fields are forbidden from scorer input: {findings}")
