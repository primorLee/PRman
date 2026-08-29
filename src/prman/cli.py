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
from prman.scorers.protocols import ScorerUnavailableError
from prman.scorers.registry import ScorerRegistry
from prman.validation import ContractError, load_json
from prman.workflow import (
    ConfirmationPacket,
    WorkflowRun,
    WriteAuthorization,
    authorize_confirmation,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prman-codex",
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
    assess.add_argument(
        "--allow-trusted-python-scorer",
        action="store_true",
        help="Execute an external Python entry-point scorer as fully trusted in-process code.",
    )
    assess.add_argument("--output", type=Path, help="Write JSON here instead of stdout.")
    assess.set_defaults(handler=_assess)

    confirmation = subparsers.add_parser(
        "confirmation",
        help="Validate an exact confirmation packet and record explicit user authorization.",
    )
    confirmation_commands = confirmation.add_subparsers(dest="confirmation_command", required=True)
    confirmation_prepare = confirmation_commands.add_parser(
        "prepare", help="Validate a packet and emit its immutable digest and confirmation phrase."
    )
    confirmation_prepare.add_argument("--input", type=Path, required=True)
    confirmation_prepare.add_argument("--output", type=Path)
    confirmation_prepare.set_defaults(handler=_confirmation_prepare)

    confirmation_authorize = confirmation_commands.add_parser(
        "authorize", help="Create a scoped write authorization after an exact user response."
    )
    confirmation_authorize.add_argument("--input", type=Path, required=True)
    confirmation_authorize.add_argument("--expected-packet-digest", required=True)
    confirmation_authorize.add_argument("--response", required=True)
    confirmation_authorize.add_argument("--output", type=Path)
    confirmation_authorize.set_defaults(handler=_confirmation_authorize)

    workflow = subparsers.add_parser(
        "workflow", help="Track Draft PR and CI transitions under a write authorization."
    )
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_begin = workflow_commands.add_parser(
        "begin", help="Start a workflow run from a validated write authorization."
    )
    workflow_begin.add_argument("--authorization", type=Path, required=True)
    workflow_begin.add_argument("--output", type=Path)
    workflow_begin.set_defaults(handler=_workflow_begin)

    workflow_draft = workflow_commands.add_parser(
        "record-draft", help="Record the exact Draft PR created under the authorization."
    )
    workflow_draft.add_argument("--input", type=Path, required=True)
    workflow_draft.add_argument("--url", required=True)
    workflow_draft.add_argument("--number", type=int, required=True)
    workflow_draft.add_argument("--base-branch", required=True)
    workflow_draft.add_argument("--base-commit", required=True)
    workflow_draft.add_argument("--head-repository", required=True)
    workflow_draft.add_argument("--head-branch", required=True)
    workflow_draft.add_argument("--diff-sha256", required=True)
    workflow_draft.add_argument("--head-commit", required=True)
    workflow_draft.add_argument("--draft", action="store_true", required=True)
    workflow_draft.add_argument("--output", type=Path)
    workflow_draft.set_defaults(handler=_workflow_record_draft)

    workflow_ci = workflow_commands.add_parser(
        "record-ci", help="Record a passing or failing CI result for the current Draft PR head."
    )
    workflow_ci.add_argument("--input", type=Path, required=True)
    workflow_ci.add_argument("--status", choices=("passed", "failed"), required=True)
    workflow_ci.add_argument("--summary", required=True)
    workflow_ci.add_argument("--head-commit", required=True)
    workflow_ci.add_argument("--output", type=Path)
    workflow_ci.set_defaults(handler=_workflow_record_ci)

    workflow_repair = workflow_commands.add_parser(
        "begin-repair", help="Consume one confirmed CI repair round after a failure."
    )
    workflow_repair.add_argument("--input", type=Path, required=True)
    workflow_repair.add_argument("--output", type=Path)
    workflow_repair.set_defaults(handler=_workflow_begin_repair)

    workflow_update = workflow_commands.add_parser(
        "record-update", help="Record a newly assessed, in-scope repair commit."
    )
    workflow_update.add_argument("--input", type=Path, required=True)
    workflow_update.add_argument("--diff-sha256", required=True)
    workflow_update.add_argument("--head-commit", required=True)
    workflow_update.add_argument("--in-scope", action="store_true", required=True)
    workflow_update.add_argument("--output", type=Path)
    workflow_update.set_defaults(handler=_workflow_record_update)
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
        marker = f" [{registry.trust_classification(name)}]"
        print(f"{name}{marker}")
    return 0


def _render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"


def _emit(value: Any, output: Path | None, *, label: str) -> int:
    rendered = _render(value)
    if output is None:
        sys.stdout.write(rendered)
    else:
        try:
            output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            raise ContractError(f"cannot write {label} {output}: {exc}") from exc
    return 0


def _assess(args: argparse.Namespace) -> int:
    assessment = Assessment.from_dict(load_json(args.input))
    decision_config = DecisionConfig.from_mapping(load_json(args.decision_config))
    scorer = None
    scorer_failure = None
    if args.allow_test_scorer and args.scorer_config is None:
        raise ContractError("--allow-test-scorer requires a test-only scorer configuration")
    if args.allow_trusted_python_scorer and args.scorer_config is None:
        raise ContractError(
            "--allow-trusted-python-scorer requires an external scorer configuration"
        )
    if args.scorer_config is not None:
        provider_name, options = load_scorer_config(args.scorer_config)
        registry = ScorerRegistry()
        classification = registry.trust_classification(provider_name)
        test_only = classification == "test-only"
        if test_only and not args.allow_test_scorer:
            raise ContractError(
                f"scorer {provider_name!r} is test-only; pass --allow-test-scorer only in tests"
            )
        if args.allow_test_scorer and not test_only:
            raise ContractError("--allow-test-scorer is valid only for a test-only scorer")
        if args.allow_trusted_python_scorer and classification != "trusted-in-process":
            raise ContractError(
                "--allow-trusted-python-scorer is valid only for an external Python scorer"
            )
        try:
            scorer = registry.create(
                provider_name,
                options,
                allow_trusted_python=args.allow_trusted_python_scorer,
            )
        except ScorerUnavailableError:
            scorer_failure = "initialization_failed"
    result = AssessmentEngine(
        decision_config,
        scorer,
        scorer_failure=scorer_failure,
    ).run(assessment)
    return _emit(result.as_dict(), args.output, label="assessment result")


def _confirmation_prepare(args: argparse.Namespace) -> int:
    packet = ConfirmationPacket.from_dict(load_json(args.input))
    return _emit(packet.preparation(), args.output, label="confirmation check")


def _confirmation_authorize(args: argparse.Namespace) -> int:
    packet = ConfirmationPacket.from_dict(load_json(args.input))
    authorization = authorize_confirmation(
        packet,
        expected_packet_digest=args.expected_packet_digest,
        response=args.response,
    )
    return _emit(authorization.as_dict(), args.output, label="write authorization")


def _workflow_begin(args: argparse.Namespace) -> int:
    authorization = WriteAuthorization.from_dict(load_json(args.authorization))
    return _emit(WorkflowRun.start(authorization).as_dict(), args.output, label="workflow run")


def _workflow_record_draft(args: argparse.Namespace) -> int:
    workflow = WorkflowRun.from_dict(load_json(args.input))
    updated = workflow.record_draft(
        url=args.url,
        number=args.number,
        base_branch=args.base_branch,
        base_commit=args.base_commit,
        head_repository=args.head_repository,
        head_branch=args.head_branch,
        diff_sha256=args.diff_sha256,
        head_commit=args.head_commit,
        draft=args.draft,
    )
    return _emit(updated.as_dict(), args.output, label="workflow run")


def _workflow_record_ci(args: argparse.Namespace) -> int:
    workflow = WorkflowRun.from_dict(load_json(args.input))
    updated = workflow.record_ci(
        status=args.status,
        summary=args.summary,
        head_commit=args.head_commit,
    )
    return _emit(updated.as_dict(), args.output, label="workflow run")


def _workflow_begin_repair(args: argparse.Namespace) -> int:
    workflow = WorkflowRun.from_dict(load_json(args.input))
    return _emit(workflow.begin_repair().as_dict(), args.output, label="workflow run")


def _workflow_record_update(args: argparse.Namespace) -> int:
    workflow = WorkflowRun.from_dict(load_json(args.input))
    updated = workflow.record_update(
        diff_sha256=args.diff_sha256,
        head_commit=args.head_commit,
        in_scope=args.in_scope,
    )
    return _emit(updated.as_dict(), args.output, label="workflow run")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except ContractError as exc:
        print(f"prman-codex: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"prman-codex: internal error ({type(exc).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
