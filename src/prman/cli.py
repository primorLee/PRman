from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from prman import __version__
from prman.assessment import Assessment, AssessmentEngine
from prman.decision import DecisionConfig
from prman.scorers.config import load_scorer_config
from prman.scorers.registry import ScorerRegistry
from prman.validation import ContractError, load_json


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prman",
        description="Deterministic assessment helper for the PRman Codex skill.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidate_id = subparsers.add_parser(
        "candidate-id",
        help="Compute the content ID for an exact unified diff.",
    )
    candidate_id.add_argument("--diff", type=Path, required=True)
    candidate_id.set_defaults(handler=_candidate_id)

    scorers = subparsers.add_parser("scorers", help="Inspect scorer providers.")
    scorer_commands = scorers.add_subparsers(dest="scorer_command", required=True)
    scorer_list = scorer_commands.add_parser("list", help="List available scorer providers.")
    scorer_list.set_defaults(handler=_scorers_list)

    assess = subparsers.add_parser(
        "assess",
        help="Validate supplied evidence, optionally score it, and make a decision.",
    )
    assess.add_argument("--input", type=Path, required=True, help="Assessment JSON path.")
    assess.add_argument(
        "--decision-config",
        type=Path,
        required=True,
        help="Decision configuration JSON path.",
    )
    assess.add_argument(
        "--scorer-config",
        type=Path,
        help="Optional production scorer configuration JSON path.",
    )
    assess.add_argument(
        "--allow-test-scorer",
        action="store_true",
        help="Allow static/fixture providers for tests only; never for a readiness claim.",
    )
    assess.add_argument("--output", type=Path, help="Write JSON here instead of stdout.")
    assess.set_defaults(handler=_assess)
    return parser


def _candidate_id(args: argparse.Namespace) -> int:
    digest = hashlib.sha256()
    try:
        with args.diff.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ContractError(f"cannot read diff {args.diff}: {exc}") from exc
    print(digest.hexdigest())
    return 0


def _scorers_list(args: argparse.Namespace) -> int:
    del args
    registry = ScorerRegistry()
    for name in registry.names():
        marker = " [test-only]" if registry.is_test_only(name) else ""
        print(f"{name}{marker}")
    return 0


def _render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"


def _assess(args: argparse.Namespace) -> int:
    assessment = Assessment.from_dict(load_json(args.input))
    decision_config = DecisionConfig.from_mapping(load_json(args.decision_config))
    scorer = None
    test_only = False
    if args.allow_test_scorer and args.scorer_config is None:
        raise ContractError("--allow-test-scorer requires a test-only scorer configuration")
    if args.scorer_config is not None:
        provider_name, options = load_scorer_config(args.scorer_config)
        registry = ScorerRegistry()
        test_only = registry.is_test_only(provider_name)
        if test_only and not args.allow_test_scorer:
            raise ContractError(
                f"scorer {provider_name!r} is test-only; pass --allow-test-scorer only in tests"
            )
        if args.allow_test_scorer and not test_only:
            raise ContractError("--allow-test-scorer is valid only for a test-only scorer")
        scorer = registry.create(provider_name, options)
    result = AssessmentEngine(decision_config, scorer, test_only=test_only).run(assessment)
    rendered = _render(result.as_dict())
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            raise ContractError(f"cannot write assessment result {args.output}: {exc}") from exc
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except ContractError as exc:
        print(f"prman: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
