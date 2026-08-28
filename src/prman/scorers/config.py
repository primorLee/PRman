from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from prman.validation import ContractError, exact_fields, load_json, require_object, require_string


def load_scorer_config(path: Path) -> tuple[str, Mapping[str, Any]]:
    value = require_object(load_json(path), path="scorer_config")
    exact_fields(
        value,
        {"schema_version", "provider", "options"},
        path="scorer_config",
    )
    if value["schema_version"] != "prman-scorer-config/1.0":
        raise ContractError(f"unsupported scorer config {value['schema_version']!r}")
    provider = require_string(value["provider"], path="scorer_config.provider")
    options = dict(require_object(value["options"], path="scorer_config.options"))
    fixture_path = options.get("fixture_path")
    if isinstance(fixture_path, str) and not Path(fixture_path).is_absolute():
        options["fixture_path"] = str((path.parent / fixture_path).resolve())
    return provider, options
