from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """Raised when an assessment or scorer contract is invalid."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_ENVIRONMENT_VARIABLE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
MAX_JSON_BYTES = 4 * 1024 * 1024


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


def load_json(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> Any:
    try:
        with path.open("rb") as handle:
            value = handle.read(max_bytes + 1)
    except OSError as exc:
        raise ContractError(f"cannot read JSON from {path}: {exc}") from exc
    if len(value) > max_bytes:
        raise ContractError(f"JSON input {path} exceeds {max_bytes} bytes")
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


def require_revision(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not _REVISION.fullmatch(value):
        raise ContractError(f"{path}: expected a lowercase 40- or 64-character Git revision")
    return value


def require_environment_variable(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not _ENVIRONMENT_VARIABLE.fullmatch(value):
        raise ContractError(f"{path}: expected an uppercase environment-variable name")
    return value


def require_timestamp(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{path}: expected an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{path}: expected an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{path}: timestamp must include a UTC offset")
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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
