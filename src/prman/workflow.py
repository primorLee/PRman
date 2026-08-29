from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Literal, cast
from urllib.parse import urlparse

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

WriteOperation = Literal[
    "create_fork",
    "create_branch",
    "push_commits",
    "create_draft_pr",
    "update_draft_pr",
]
AssessmentDecision = Literal["ready", "revise", "abstain"]
WorkflowState = Literal["authorized", "draft_open", "ci_failed", "repairing", "complete"]
CIStatus = Literal["passed", "failed"]

_ALLOWED_WRITES = frozenset(
    {
        "create_fork",
        "create_branch",
        "push_commits",
        "create_draft_pr",
        "update_draft_pr",
    }
)
_REQUIRED_INITIAL_WRITES = frozenset({"create_branch", "push_commits", "create_draft_pr"})
_FULL_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_INVALID_BRANCH = re.compile(r"[\s~^:?*\\[]")


def _require_boolean(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{path}: expected a boolean")
    return value


def _require_integer(value: Any, *, path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ContractError(f"{path}: expected an integer in [{minimum}, {maximum}]")
    return int(value)


def _optional_string(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    return require_string(value, path=path)


def _require_https_url(value: Any, *, path: str) -> str:
    url = require_string(value, path=path)
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ContractError(f"{path}: expected an HTTPS URL without embedded credentials")
    return url


def _require_github_pr_url(
    value: Any,
    *,
    repository: str,
    number: int,
    path: str,
) -> str:
    url = _require_https_url(value, path=path)
    parsed = urlparse(url)
    expected_path = f"/{repository}/pull/{number}"
    if (
        parsed.netloc.casefold() != "github.com"
        or parsed.path.casefold() != expected_path.casefold()
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ContractError(
            f"{path}: expected the canonical GitHub Draft PR URL for {repository}#{number}"
        )
    return url


def _require_full_name(value: Any, *, path: str) -> str:
    full_name = require_string(value, path=path)
    if not _FULL_NAME.fullmatch(full_name):
        raise ContractError(f"{path}: expected OWNER/REPO")
    return full_name


def _require_branch(value: Any, *, path: str) -> str:
    branch = require_string(value, path=path)
    components = branch.split("/")
    if (
        _INVALID_BRANCH.search(branch)
        or ".." in branch
        or "@{" in branch
        or branch == "@"
        or branch.startswith((".", "/"))
        or branch.endswith((".", "/"))
        or "//" in branch
        or any(component.startswith(".") or component.endswith(".lock") for component in components)
    ):
        raise ContractError(f"{path}: invalid Git branch name")
    return branch


def _require_unique_strings(value: Any, *, path: str) -> tuple[str, ...]:
    raw = require_list(value, path=path)
    result = tuple(require_string(item, path=f"{path}[{index}]") for index, item in enumerate(raw))
    if not result:
        raise ContractError(f"{path}: expected at least one item")
    if len(result) != len(set(result)):
        raise ContractError(f"{path}: duplicate items are not allowed")
    return result


def _confirmation_phrase(
    repository: str,
    head_branch: str,
    decision: AssessmentDecision,
) -> str:
    phrase = f"CONFIRM DRAFT PR {repository} {head_branch}"
    if decision != "ready":
        phrase += f" ACKNOWLEDGE {decision.upper()}"
    if len(phrase) > 200:
        raise ContractError("confirmation.approval.confirmation_phrase exceeds 200 characters")
    return phrase


def _validate_verification(value: Any) -> None:
    records = require_list(value, path="confirmation.verification")
    if not records:
        raise ContractError("confirmation.verification: expected at least one record")
    for index, raw_record in enumerate(records):
        path = f"confirmation.verification[{index}]"
        record = require_object(raw_record, path=path)
        exact_fields(
            record,
            {"name", "command", "status", "summary", "log_digest"},
            path=path,
        )
        require_string(record["name"], path=f"{path}.name")
        _optional_string(record["command"], path=f"{path}.command")
        status = record["status"]
        if status not in {"passed", "failed", "not_run"}:
            raise ContractError(f"{path}.status: unsupported value {status!r}")
        require_string(record["summary"], path=f"{path}.summary")
        log_digest = record["log_digest"]
        if status == "not_run":
            if log_digest is not None:
                raise ContractError(f"{path}.log_digest: not_run records must use null")
        elif log_digest is None:
            raise ContractError(f"{path}.log_digest: observed checks require a digest")
        else:
            require_sha256(log_digest, path=f"{path}.log_digest")


@dataclass(frozen=True)
class ConfirmationPacket:
    packet_digest: str
    repository: str
    repository_url: str
    base_branch: str
    base_commit: str
    head_repository: str
    head_branch: str
    fork_required: bool
    diff_sha256: str
    assessment_decision: AssessmentDecision
    external_writes: tuple[WriteOperation, ...]
    ci_max_fix_rounds: int
    ci_publish_repairs: bool
    ci_scope: str
    confirmation_phrase: str
    schema_version: str = "prman-confirmation-packet/1.1"

    @classmethod
    def from_dict(cls, value: Any) -> ConfirmationPacket:
        item = require_object(value, path="confirmation")
        exact_fields(
            item,
            {
                "schema_version",
                "repository",
                "task",
                "base",
                "head",
                "diff",
                "verification",
                "assessment",
                "pull_request",
                "external_writes",
                "ci_followup",
                "approval",
            },
            path="confirmation",
        )
        if item["schema_version"] != "prman-confirmation-packet/1.1":
            raise ContractError(f"unsupported confirmation packet {item['schema_version']!r}")

        repository_value = require_object(item["repository"], path="confirmation.repository")
        exact_fields(
            repository_value,
            {"full_name", "url", "selection_reason"},
            path="confirmation.repository",
        )
        repository = _require_full_name(
            repository_value["full_name"], path="confirmation.repository.full_name"
        )
        repository_url = _require_https_url(
            repository_value["url"], path="confirmation.repository.url"
        )
        if repository_url.rstrip("/") != f"https://github.com/{repository}":
            raise ContractError("confirmation.repository.url does not match full_name")
        require_string(
            repository_value["selection_reason"],
            path="confirmation.repository.selection_reason",
        )

        task = require_object(item["task"], path="confirmation.task")
        exact_fields(task, {"title", "url", "summary"}, path="confirmation.task")
        require_string(task["title"], path="confirmation.task.title")
        if task["url"] is not None:
            _require_https_url(task["url"], path="confirmation.task.url")
        require_string(task["summary"], path="confirmation.task.summary")

        base = require_object(item["base"], path="confirmation.base")
        exact_fields(base, {"branch", "commit"}, path="confirmation.base")
        base_branch = _require_branch(base["branch"], path="confirmation.base.branch")
        base_commit = require_revision(base["commit"], path="confirmation.base.commit")
        if len(base_commit) != 40:
            raise ContractError("confirmation.base.commit: expected a full 40-character commit")

        head = require_object(item["head"], path="confirmation.head")
        exact_fields(
            head,
            {"repository", "branch", "fork_required"},
            path="confirmation.head",
        )
        head_repository = _require_full_name(
            head["repository"], path="confirmation.head.repository"
        )
        head_branch = _require_branch(head["branch"], path="confirmation.head.branch")
        fork_required = _require_boolean(
            head["fork_required"], path="confirmation.head.fork_required"
        )
        if head_branch == base_branch:
            raise ContractError("confirmation.head.branch must differ from the base branch")
        if fork_required == (head_repository == repository):
            raise ContractError("confirmation.head fork route is inconsistent with repository")

        diff = require_object(item["diff"], path="confirmation.diff")
        exact_fields(diff, {"sha256", "files", "summary", "patch"}, path="confirmation.diff")
        diff_sha256 = require_sha256(diff["sha256"], path="confirmation.diff.sha256")
        _require_unique_strings(diff["files"], path="confirmation.diff.files")
        require_string(diff["summary"], path="confirmation.diff.summary")
        patch = require_string(diff["patch"], path="confirmation.diff.patch")
        if sha256_text(patch) != diff_sha256:
            raise ContractError("confirmation.diff.sha256 does not match patch bytes")

        _validate_verification(item["verification"])

        assessment = require_object(item["assessment"], path="confirmation.assessment")
        exact_fields(
            assessment,
            {
                "decision",
                "reason",
                "scorer",
                "test_only",
                "attestation_verified",
                "override_acknowledgement_required",
            },
            path="confirmation.assessment",
        )
        decision = assessment["decision"]
        if decision not in {"ready", "revise", "abstain"}:
            raise ContractError(f"confirmation.assessment.decision: unsupported value {decision!r}")
        assessment_decision = cast(AssessmentDecision, decision)
        assessment_reason = require_string(
            assessment["reason"], path="confirmation.assessment.reason"
        )
        scorer = _optional_string(assessment["scorer"], path="confirmation.assessment.scorer")
        test_only = _require_boolean(
            assessment["test_only"], path="confirmation.assessment.test_only"
        )
        attestation_verified = _require_boolean(
            assessment["attestation_verified"],
            path="confirmation.assessment.attestation_verified",
        )
        acknowledgement_required = _require_boolean(
            assessment["override_acknowledgement_required"],
            path="confirmation.assessment.override_acknowledgement_required",
        )
        if decision == "ready":
            if scorer is None or test_only or not attestation_verified or acknowledgement_required:
                raise ContractError(
                    "confirmation.assessment: ready requires production scoring, verified "
                    "attestation, and no override acknowledgement"
                )
        elif not acknowledgement_required:
            raise ContractError(
                "confirmation.assessment: revise/abstain requires explicit acknowledgement"
            )

        pull_request = require_object(item["pull_request"], path="confirmation.pull_request")
        exact_fields(
            pull_request,
            {"draft", "title", "body", "base_branch", "head_branch"},
            path="confirmation.pull_request",
        )
        if (
            _require_boolean(pull_request["draft"], path="confirmation.pull_request.draft")
            is not True
        ):
            raise ContractError("confirmation.pull_request.draft must be true")
        require_string(pull_request["title"], path="confirmation.pull_request.title")
        require_string(pull_request["body"], path="confirmation.pull_request.body")
        if pull_request["base_branch"] != base_branch:
            raise ContractError("confirmation.pull_request.base_branch does not match base")
        if pull_request["head_branch"] != head_branch:
            raise ContractError("confirmation.pull_request.head_branch does not match head")

        raw_writes = _require_unique_strings(
            item["external_writes"], path="confirmation.external_writes"
        )
        writes = cast(tuple[WriteOperation, ...], raw_writes)
        unknown_writes = {write for write in writes if write not in _ALLOWED_WRITES}
        if unknown_writes:
            raise ContractError(
                f"confirmation.external_writes: unsupported values {sorted(unknown_writes)}"
            )
        if not _REQUIRED_INITIAL_WRITES.issubset(writes):
            raise ContractError("confirmation.external_writes: initial Draft PR writes are missing")
        if fork_required and "create_fork" not in writes:
            raise ContractError("confirmation.external_writes: fork route requires create_fork")
        if not fork_required and "create_fork" in writes:
            raise ContractError(
                "confirmation.external_writes: create_fork is not part of this route"
            )

        ci = require_object(item["ci_followup"], path="confirmation.ci_followup")
        exact_fields(
            ci,
            {"monitor", "max_fix_rounds", "publish_repairs", "scope"},
            path="confirmation.ci_followup",
        )
        if _require_boolean(ci["monitor"], path="confirmation.ci_followup.monitor") is not True:
            raise ContractError("confirmation.ci_followup.monitor must be true")
        max_fix_rounds = _require_integer(
            ci["max_fix_rounds"],
            path="confirmation.ci_followup.max_fix_rounds",
            minimum=0,
            maximum=2,
        )
        publish_repairs = _require_boolean(
            ci["publish_repairs"], path="confirmation.ci_followup.publish_repairs"
        )
        ci_scope = require_string(ci["scope"], path="confirmation.ci_followup.scope")
        if publish_repairs != (max_fix_rounds > 0):
            raise ContractError(
                "confirmation.ci_followup: publish_repairs must match a positive repair budget"
            )
        if publish_repairs != ("update_draft_pr" in writes):
            raise ContractError(
                "confirmation.external_writes: update_draft_pr must match the CI repair policy"
            )

        approval = require_object(item["approval"], path="confirmation.approval")
        exact_fields(
            approval,
            {"status", "prompt", "confirmation_phrase"},
            path="confirmation.approval",
        )
        if approval["status"] != "pending":
            raise ContractError("confirmation.approval.status must be pending")
        prompt = require_string(approval["prompt"], path="confirmation.approval.prompt")
        confirmation_phrase = require_string(
            approval["confirmation_phrase"], path="confirmation.approval.confirmation_phrase"
        )
        expected_phrase = _confirmation_phrase(repository, head_branch, assessment_decision)
        if confirmation_phrase != expected_phrase:
            raise ContractError(
                "confirmation.approval.confirmation_phrase must name the exact Draft PR target"
            )
        if confirmation_phrase not in prompt:
            raise ContractError("confirmation.approval.prompt must show the confirmation phrase")
        if (
            assessment_decision != "ready"
            and f"Assessment result: {assessment_reason}" not in prompt
        ):
            raise ContractError(
                "confirmation.approval.prompt must show the exact non-ready assessment reason"
            )

        return cls(
            packet_digest=canonical_digest(item),
            repository=repository,
            repository_url=repository_url,
            base_branch=base_branch,
            base_commit=base_commit,
            head_repository=head_repository,
            head_branch=head_branch,
            fork_required=fork_required,
            diff_sha256=diff_sha256,
            assessment_decision=assessment_decision,
            external_writes=writes,
            ci_max_fix_rounds=max_fix_rounds,
            ci_publish_repairs=publish_repairs,
            ci_scope=ci_scope,
            confirmation_phrase=confirmation_phrase,
        )

    def preparation(self) -> dict[str, Any]:
        return {
            "schema_version": "prman-confirmation-check/1.0",
            "packet_digest": self.packet_digest,
            "repository": self.repository,
            "confirmation_phrase": self.confirmation_phrase,
            "policy": {
                "human_confirmation_required": True,
                "draft_only": True,
                "external_write_authorized": False,
            },
        }


@dataclass(frozen=True)
class WriteAuthorization:
    packet_digest: str
    confirmation_phrase_digest: str
    repository: str
    base_branch: str
    base_commit: str
    head_repository: str
    head_branch: str
    initial_diff_sha256: str
    assessment_decision: AssessmentDecision
    external_writes: tuple[WriteOperation, ...]
    ci_max_fix_rounds: int
    ci_publish_repairs: bool
    ci_scope: str
    schema_version: str = "prman-write-authorization/1.0"

    @classmethod
    def from_dict(cls, value: Any) -> WriteAuthorization:
        item = require_object(value, path="authorization")
        exact_fields(
            item,
            {
                "schema_version",
                "packet_digest",
                "confirmation_phrase_digest",
                "repository",
                "base",
                "head",
                "initial_diff_sha256",
                "assessment_decision",
                "external_writes",
                "ci_followup",
                "policy",
            },
            path="authorization",
        )
        if item["schema_version"] != "prman-write-authorization/1.0":
            raise ContractError(f"unsupported write authorization {item['schema_version']!r}")
        base = require_object(item["base"], path="authorization.base")
        exact_fields(base, {"branch", "commit"}, path="authorization.base")
        head = require_object(item["head"], path="authorization.head")
        exact_fields(head, {"repository", "branch"}, path="authorization.head")
        ci = require_object(item["ci_followup"], path="authorization.ci_followup")
        exact_fields(
            ci,
            {"max_fix_rounds", "publish_repairs", "scope"},
            path="authorization.ci_followup",
        )
        policy = require_object(item["policy"], path="authorization.policy")
        expected_policy = {
            "draft_only": True,
            "external_write_authorized": True,
            "merge_authorized": False,
            "force_push_authorized": False,
            "default_branch_write_authorized": False,
        }
        if dict(policy) != expected_policy:
            raise ContractError("authorization.policy does not match the fail-closed policy")
        decision = item["assessment_decision"]
        if decision not in {"ready", "revise", "abstain"}:
            raise ContractError(f"authorization.assessment_decision: unsupported {decision!r}")
        assessment_decision = cast(AssessmentDecision, decision)
        writes = cast(
            tuple[WriteOperation, ...],
            _require_unique_strings(item["external_writes"], path="authorization.external_writes"),
        )
        if any(write not in _ALLOWED_WRITES for write in writes):
            raise ContractError("authorization.external_writes contains an unsupported operation")
        if not _REQUIRED_INITIAL_WRITES.issubset(writes):
            raise ContractError(
                "authorization.external_writes: initial Draft PR writes are missing"
            )

        packet_digest = require_sha256(item["packet_digest"], path="authorization.packet_digest")
        confirmation_phrase_digest = require_sha256(
            item["confirmation_phrase_digest"],
            path="authorization.confirmation_phrase_digest",
        )
        repository = _require_full_name(item["repository"], path="authorization.repository")
        base_branch = _require_branch(base["branch"], path="authorization.base.branch")
        base_commit = require_revision(base["commit"], path="authorization.base.commit")
        if len(base_commit) != 40:
            raise ContractError("authorization.base.commit: expected a full 40-character commit")
        head_repository = _require_full_name(
            head["repository"], path="authorization.head.repository"
        )
        head_branch = _require_branch(head["branch"], path="authorization.head.branch")
        if head_branch == base_branch:
            raise ContractError("authorization.head.branch must differ from the base branch")
        fork_required = head_repository != repository
        if fork_required != ("create_fork" in writes):
            raise ContractError("authorization fork route is inconsistent with external writes")

        ci_max_fix_rounds = _require_integer(
            ci["max_fix_rounds"],
            path="authorization.ci_followup.max_fix_rounds",
            minimum=0,
            maximum=2,
        )
        ci_publish_repairs = _require_boolean(
            ci["publish_repairs"], path="authorization.ci_followup.publish_repairs"
        )
        if ci_publish_repairs != (ci_max_fix_rounds > 0):
            raise ContractError(
                "authorization.ci_followup: publish_repairs must match a positive repair budget"
            )
        if ci_publish_repairs != ("update_draft_pr" in writes):
            raise ContractError(
                "authorization.external_writes: update_draft_pr must match the CI repair policy"
            )
        expected_phrase_digest = sha256_text(
            _confirmation_phrase(repository, head_branch, assessment_decision)
        )
        if confirmation_phrase_digest != expected_phrase_digest:
            raise ContractError(
                "authorization.confirmation_phrase_digest does not match the authorized target"
            )

        return cls(
            packet_digest=packet_digest,
            confirmation_phrase_digest=confirmation_phrase_digest,
            repository=repository,
            base_branch=base_branch,
            base_commit=base_commit,
            head_repository=head_repository,
            head_branch=head_branch,
            initial_diff_sha256=require_sha256(
                item["initial_diff_sha256"], path="authorization.initial_diff_sha256"
            ),
            assessment_decision=assessment_decision,
            external_writes=writes,
            ci_max_fix_rounds=ci_max_fix_rounds,
            ci_publish_repairs=ci_publish_repairs,
            ci_scope=require_string(ci["scope"], path="authorization.ci_followup.scope"),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "packet_digest": self.packet_digest,
            "confirmation_phrase_digest": self.confirmation_phrase_digest,
            "repository": self.repository,
            "base": {"branch": self.base_branch, "commit": self.base_commit},
            "head": {"repository": self.head_repository, "branch": self.head_branch},
            "initial_diff_sha256": self.initial_diff_sha256,
            "assessment_decision": self.assessment_decision,
            "external_writes": list(self.external_writes),
            "ci_followup": {
                "max_fix_rounds": self.ci_max_fix_rounds,
                "publish_repairs": self.ci_publish_repairs,
                "scope": self.ci_scope,
            },
            "policy": {
                "draft_only": True,
                "external_write_authorized": True,
                "merge_authorized": False,
                "force_push_authorized": False,
                "default_branch_write_authorized": False,
            },
        }

    def allows_initial_write(
        self,
        operation: str,
        *,
        repository: str,
        base_branch: str,
        base_commit: str,
        head_repository: str,
        head_branch: str,
        diff_sha256: str,
    ) -> bool:
        return (
            operation in self.external_writes
            and repository == self.repository
            and base_branch == self.base_branch
            and base_commit == self.base_commit
            and head_repository == self.head_repository
            and head_branch == self.head_branch
            and diff_sha256 == self.initial_diff_sha256
        )

    def allows_ci_repair(
        self,
        round_number: int,
        *,
        repository: str,
        head_repository: str,
        head_branch: str,
    ) -> bool:
        return (
            not isinstance(round_number, bool)
            and self.ci_publish_repairs
            and "update_draft_pr" in self.external_writes
            and 1 <= round_number <= self.ci_max_fix_rounds
            and repository == self.repository
            and head_repository == self.head_repository
            and head_branch == self.head_branch
        )


def authorize_confirmation(
    packet: ConfirmationPacket,
    *,
    expected_packet_digest: str,
    response: str,
) -> WriteAuthorization:
    require_sha256(expected_packet_digest, path="expected_packet_digest")
    if packet.packet_digest != expected_packet_digest:
        raise ContractError("confirmation packet changed after it was presented")
    if response != packet.confirmation_phrase:
        raise ContractError("response does not exactly match the confirmation phrase")
    return WriteAuthorization(
        packet_digest=packet.packet_digest,
        confirmation_phrase_digest=sha256_text(response),
        repository=packet.repository,
        base_branch=packet.base_branch,
        base_commit=packet.base_commit,
        head_repository=packet.head_repository,
        head_branch=packet.head_branch,
        initial_diff_sha256=packet.diff_sha256,
        assessment_decision=packet.assessment_decision,
        external_writes=packet.external_writes,
        ci_max_fix_rounds=packet.ci_max_fix_rounds,
        ci_publish_repairs=packet.ci_publish_repairs,
        ci_scope=packet.ci_scope,
    )


@dataclass(frozen=True)
class WorkflowRun:
    authorization: WriteAuthorization
    state: WorkflowState
    current_diff_sha256: str
    repair_rounds_used: int
    pr_url: str | None = None
    pr_number: int | None = None
    pr_head_commit: str | None = None
    last_ci_status: CIStatus | None = None
    last_ci_summary: str | None = None
    last_ci_head_commit: str | None = None
    schema_version: str = "prman-workflow-run/1.0"

    def __post_init__(self) -> None:
        if self.schema_version != "prman-workflow-run/1.0":
            raise ContractError(f"unsupported workflow run {self.schema_version!r}")
        if not isinstance(self.authorization, WriteAuthorization):
            raise ContractError("workflow.authorization must be a WriteAuthorization")
        WriteAuthorization.from_dict(self.authorization.as_dict())
        if self.state not in {"authorized", "draft_open", "ci_failed", "repairing", "complete"}:
            raise ContractError(f"workflow.state: unsupported value {self.state!r}")
        require_sha256(self.current_diff_sha256, path="workflow.current_diff_sha256")
        _require_integer(
            self.repair_rounds_used,
            path="workflow.repair_rounds_used",
            minimum=0,
            maximum=self.authorization.ci_max_fix_rounds,
        )
        if (
            self.repair_rounds_used == 0
            and self.current_diff_sha256 != self.authorization.initial_diff_sha256
        ):
            raise ContractError("workflow without a repair must use the confirmed initial diff")
        has_pr = (
            self.pr_url is not None or self.pr_number is not None or self.pr_head_commit is not None
        )
        if has_pr:
            if self.pr_url is None or self.pr_number is None or self.pr_head_commit is None:
                raise ContractError("workflow.pr fields must be set together")
            pr_number = _require_integer(
                self.pr_number, path="workflow.pr.number", minimum=1, maximum=2**63 - 1
            )
            _require_github_pr_url(
                self.pr_url,
                repository=self.authorization.repository,
                number=pr_number,
                path="workflow.pr.url",
            )
            pr_head_commit = require_revision(self.pr_head_commit, path="workflow.pr.head_commit")
            if pr_head_commit == self.authorization.base_commit:
                raise ContractError("workflow.pr.head_commit must differ from the base commit")
        has_ci = (
            self.last_ci_status is not None
            or self.last_ci_summary is not None
            or self.last_ci_head_commit is not None
        )
        if has_ci:
            if (
                self.last_ci_status not in {"passed", "failed"}
                or self.last_ci_summary is None
                or self.last_ci_head_commit is None
            ):
                raise ContractError("workflow.last_ci fields must be set together")
            require_string(self.last_ci_summary, path="workflow.last_ci.summary")
            require_revision(self.last_ci_head_commit, path="workflow.last_ci.head_commit")
            if has_pr and self.last_ci_head_commit != self.pr_head_commit:
                raise ContractError("workflow.last_ci.head_commit must match the current Draft PR")
        if self.state == "authorized":
            if has_pr or has_ci or self.repair_rounds_used != 0:
                raise ContractError("authorized workflow cannot contain PR, CI, or repair state")
            if self.current_diff_sha256 != self.authorization.initial_diff_sha256:
                raise ContractError("authorized workflow must use the confirmed initial diff")
        elif not has_pr:
            raise ContractError(f"{self.state} workflow requires a Draft PR record")
        if self.state == "draft_open" and has_ci:
            raise ContractError("draft_open workflow cannot retain a completed CI observation")
        if self.state in {"ci_failed", "repairing"} and self.last_ci_status != "failed":
            raise ContractError(f"{self.state} workflow requires a failed CI observation")
        if self.state == "repairing" and self.repair_rounds_used < 1:
            raise ContractError("repairing workflow requires a consumed repair round")
        if self.state == "complete" and self.last_ci_status != "passed":
            raise ContractError("complete workflow requires a passing CI observation")

    @classmethod
    def start(cls, authorization: WriteAuthorization) -> WorkflowRun:
        return cls(
            authorization=authorization,
            state="authorized",
            current_diff_sha256=authorization.initial_diff_sha256,
            repair_rounds_used=0,
        )

    @classmethod
    def from_dict(cls, value: Any) -> WorkflowRun:
        item = require_object(value, path="workflow")
        exact_fields(
            item,
            {
                "schema_version",
                "authorization",
                "state",
                "current_diff_sha256",
                "repair_rounds_used",
                "pull_request",
                "last_ci",
            },
            path="workflow",
        )
        pr = item["pull_request"]
        pr_url: str | None = None
        pr_number: int | None = None
        pr_head_commit: str | None = None
        if pr is not None:
            pr_value = require_object(pr, path="workflow.pull_request")
            exact_fields(
                pr_value,
                {"url", "number", "draft", "head_commit"},
                path="workflow.pull_request",
            )
            if _require_boolean(pr_value["draft"], path="workflow.pull_request.draft") is not True:
                raise ContractError("workflow.pull_request.draft must be true")
            pr_url = _require_https_url(pr_value["url"], path="workflow.pull_request.url")
            pr_number = _require_integer(
                pr_value["number"],
                path="workflow.pull_request.number",
                minimum=1,
                maximum=2**63 - 1,
            )
            pr_head_commit = require_revision(
                pr_value["head_commit"], path="workflow.pull_request.head_commit"
            )
        ci = item["last_ci"]
        ci_status: CIStatus | None = None
        ci_summary: str | None = None
        ci_head_commit: str | None = None
        if ci is not None:
            ci_value = require_object(ci, path="workflow.last_ci")
            exact_fields(ci_value, {"status", "summary", "head_commit"}, path="workflow.last_ci")
            if ci_value["status"] not in {"passed", "failed"}:
                raise ContractError("workflow.last_ci.status is unsupported")
            ci_status = ci_value["status"]
            ci_summary = require_string(ci_value["summary"], path="workflow.last_ci.summary")
            ci_head_commit = require_revision(
                ci_value["head_commit"], path="workflow.last_ci.head_commit"
            )
        return cls(
            schema_version=item["schema_version"],
            authorization=WriteAuthorization.from_dict(item["authorization"]),
            state=item["state"],
            current_diff_sha256=item["current_diff_sha256"],
            repair_rounds_used=item["repair_rounds_used"],
            pr_url=pr_url,
            pr_number=pr_number,
            pr_head_commit=pr_head_commit,
            last_ci_status=ci_status,
            last_ci_summary=ci_summary,
            last_ci_head_commit=ci_head_commit,
        )

    def as_dict(self) -> dict[str, Any]:
        pull_request = None
        if self.pr_url is not None:
            pull_request = {
                "url": self.pr_url,
                "number": self.pr_number,
                "draft": True,
                "head_commit": self.pr_head_commit,
            }
        last_ci = None
        if self.last_ci_status is not None:
            last_ci = {
                "status": self.last_ci_status,
                "summary": self.last_ci_summary,
                "head_commit": self.last_ci_head_commit,
            }
        return {
            "schema_version": self.schema_version,
            "authorization": self.authorization.as_dict(),
            "state": self.state,
            "current_diff_sha256": self.current_diff_sha256,
            "repair_rounds_used": self.repair_rounds_used,
            "pull_request": pull_request,
            "last_ci": last_ci,
        }

    def record_draft(
        self,
        *,
        url: str,
        number: int,
        base_branch: str,
        base_commit: str,
        head_repository: str,
        head_branch: str,
        diff_sha256: str,
        head_commit: str,
        draft: bool,
    ) -> WorkflowRun:
        if self.state != "authorized":
            raise ContractError("Draft PR can be recorded only from authorized state")
        if draft is not True:
            raise ContractError("PRman accepts only a Draft PR")
        observed_base_branch = _require_branch(base_branch, path="workflow.pr.base_branch")
        observed_base_commit = require_revision(base_commit, path="workflow.pr.base_commit")
        observed_head_repository = _require_full_name(
            head_repository, path="workflow.pr.head_repository"
        )
        observed_head_branch = _require_branch(head_branch, path="workflow.pr.head_branch")
        observed_diff_sha256 = require_sha256(diff_sha256, path="workflow.pr.diff_sha256")
        if not self.authorization.allows_initial_write(
            "create_draft_pr",
            repository=self.authorization.repository,
            base_branch=observed_base_branch,
            base_commit=observed_base_commit,
            head_repository=observed_head_repository,
            head_branch=observed_head_branch,
            diff_sha256=observed_diff_sha256,
        ):
            raise ContractError("write authorization does not permit this Draft PR")
        if observed_diff_sha256 != self.current_diff_sha256:
            raise ContractError("Draft PR diff does not match the current workflow diff")
        pr_number = _require_integer(
            number, path="workflow.pr.number", minimum=1, maximum=2**63 - 1
        )
        pr_url = _require_github_pr_url(
            url,
            repository=self.authorization.repository,
            number=pr_number,
            path="workflow.pr.url",
        )
        return replace(
            self,
            state="draft_open",
            pr_url=pr_url,
            pr_number=pr_number,
            pr_head_commit=require_revision(head_commit, path="workflow.pr.head_commit"),
        )

    def record_ci(self, *, status: str, summary: str, head_commit: str) -> WorkflowRun:
        if self.state != "draft_open" or self.pr_head_commit is None:
            raise ContractError("CI can be recorded only for an open Draft PR awaiting checks")
        if status not in {"passed", "failed"}:
            raise ContractError(f"workflow CI status is unsupported: {status!r}")
        if head_commit != self.pr_head_commit:
            raise ContractError("CI head commit does not match the current Draft PR")
        ci_status = cast(CIStatus, status)
        return replace(
            self,
            state="complete" if status == "passed" else "ci_failed",
            last_ci_status=ci_status,
            last_ci_summary=require_string(summary, path="workflow.last_ci.summary"),
            last_ci_head_commit=require_revision(head_commit, path="workflow.last_ci.head_commit"),
        )

    def begin_repair(self) -> WorkflowRun:
        if self.state != "ci_failed":
            raise ContractError("a repair round can begin only after CI fails")
        round_number = self.repair_rounds_used + 1
        if not self.authorization.allows_ci_repair(
            round_number,
            repository=self.authorization.repository,
            head_repository=self.authorization.head_repository,
            head_branch=self.authorization.head_branch,
        ):
            raise ContractError("confirmed CI repair budget is exhausted or unavailable")
        return replace(self, state="repairing", repair_rounds_used=round_number)

    def record_update(
        self,
        *,
        diff_sha256: str,
        head_commit: str,
        in_scope: bool,
    ) -> WorkflowRun:
        if self.state != "repairing" or self.pr_head_commit is None:
            raise ContractError("a Draft PR update can be recorded only during a repair round")
        if in_scope is not True:
            raise ContractError(
                "material or out-of-scope changes require a new confirmation packet"
            )
        next_diff = require_sha256(diff_sha256, path="workflow.current_diff_sha256")
        next_commit = require_revision(head_commit, path="workflow.pr.head_commit")
        if next_diff == self.current_diff_sha256:
            raise ContractError("repair update must contain a newly assessed diff")
        if next_commit == self.pr_head_commit:
            raise ContractError("repair update must publish a new head commit")
        return replace(
            self,
            state="draft_open",
            current_diff_sha256=next_diff,
            pr_head_commit=next_commit,
            last_ci_status=None,
            last_ci_summary=None,
            last_ci_head_commit=None,
        )
