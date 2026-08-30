"""Manual operator script for narrowly controlled Classroom write verification (Loop 0.6F).

Usage:
    python scripts/classroom_write_smoke.py --course-id <id> --topic-id <id> \
        --title "..." --approved-by "Name" --ledger-file <private path> \
        [--instructions "..."] [--due-date YYYY-MM-DD]

Requires the same operator environment as scripts/classroom_read_smoke.py, plus a deployment
authorized for the coursework write scope.

This script applies exactly one Classroom coursework item in DRAFT state. It never publishes to
students, never sends a grading field, and persists redacted evidence in an operator-supplied
private ledger so a repeat run becomes a local no-op before any Google call.
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,
    ClassroomAccessRequest,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_action import (
    ClassroomActionApproval,
    ClassroomActionPlan,
    ClassroomActionStatus,
    ClassroomActionType,
)
from medsemiotics.domain.exceptions import MedSemioticsError
from medsemiotics.integrations.google_classroom import (
    AppsScriptCourseworkWriter,
    AuthenticatedAppsScriptTransport,
    build_operator_token_provider,
    load_apps_script_deployment,
)
from medsemiotics.services.classroom_access_policy import ClassroomAccessPolicy
from medsemiotics.services.classroom_action_ledger import ClassroomActionLedgerRepository
from medsemiotics.services.classroom_action_plan import ClassroomActionAuthorizer


def parse_arguments() -> argparse.Namespace:
    """Parse the operator's declared write."""
    parser = argparse.ArgumentParser(description="Apply one approved Classroom coursework draft.")
    parser.add_argument("--course-id", required=True, help="Classroom course id from the view")
    parser.add_argument("--course-code", default="NEURO", help="Tracked course code")
    parser.add_argument("--semester-id", default="2026-2", help="Academic semester")
    parser.add_argument("--topic-id", required=True, help="Tracked syllabus topic")
    parser.add_argument("--title", required=True, help="Coursework title")
    parser.add_argument("--instructions", default=None, help="Optional instructions")
    parser.add_argument("--due-date", default=None, help="Optional due date, YYYY-MM-DD")
    parser.add_argument("--prepared-by", default="operator", help="Author of the plan")
    parser.add_argument("--approved-by", required=True, help="Named human approving the plan")
    parser.add_argument(
        "--ledger-file",
        required=True,
        type=Path,
        help="Private JSON ledger path outside tracked public content",
    )
    return parser.parse_args()


def main() -> None:
    """Apply one approved coursework draft and print the ledger entry it produced."""
    arguments = parse_arguments()
    print("=== MedSemiotics Classroom Write Verification (Loop 0.6F) ===")

    now = datetime.now(tz=None).astimezone()
    plan = ClassroomActionPlan(
        action_type=ClassroomActionType.CREATE_COURSEWORK_DRAFT,
        semester_id=arguments.semester_id,
        course_code=arguments.course_code,
        external_course_id=arguments.course_id,
        topic_id=arguments.topic_id,
        title=arguments.title,
        instructions=arguments.instructions,
        due_date=date.fromisoformat(arguments.due_date) if arguments.due_date else None,
        prepared_by=arguments.prepared_by,
        prepared_at=now,
    )

    print(f"  identity_key:  {plan.identity_key}")
    print(f"  fingerprint:   {plan.content_fingerprint}")
    print(f"  approved_by:   {arguments.approved_by}")

    authorizer = ClassroomActionAuthorizer(build_default_agent_framework())
    ledger = ClassroomActionLedgerRepository(arguments.ledger_file)

    try:
        applied_actions = ledger.load()
        action_decision = authorizer.authorize(
            plan=plan,
            approval=ClassroomActionApproval(
                approved_by=arguments.approved_by,
                approved_at=now,
                content_fingerprint=plan.content_fingerprint,
            ),
            applied_actions=applied_actions,
        )
    except MedSemioticsError as err:
        print(f"✗ Authorization: {err}", file=sys.stderr)
        raise SystemExit(2) from None

    if action_decision.status is ClassroomActionStatus.ALREADY_APPLIED:
        print("✓ No-op: this coursework draft is already recorded in the private ledger.")
        print(f"  external_reference: {action_decision.existing_reference or 'not recorded'}")
        print("\nNo Google request was made and no duplicate draft was created.")
        return

    try:
        access_decision = ClassroomAccessPolicy().authorize(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSEWORK_DRAFT_CREATE,
                data_categories=(ClassroomDataCategory.OWN_COURSEWORK_DRAFT,),
                oauth_scopes=(GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
                requested_by=arguments.prepared_by,
                external_mutation=True,
            )
        )
        deployment = load_apps_script_deployment()
    except MedSemioticsError as err:
        print(f"✗ Authorization: {err}", file=sys.stderr)
        raise SystemExit(2) from None

    writer = AppsScriptCourseworkWriter(
        deployment=deployment,
        transport=AuthenticatedAppsScriptTransport(token_provider=build_operator_token_provider()),
    )

    try:
        record = writer.create_coursework_draft(
            plan=plan,
            action_decision=action_decision,
            access_decision=access_decision,
        )
    except MedSemioticsError as err:
        print(f"✗ Write boundary: {err}", file=sys.stderr)
        raise SystemExit(1) from None

    try:
        ledger.append(record)
    except MedSemioticsError as err:
        print(f"✗ Critical ledger persistence failure: {err}", file=sys.stderr)
        print("The draft may exist in Classroom. Preserve this recovery evidence:", file=sys.stderr)
        print(f"  identity_key:       {record.identity_key}", file=sys.stderr)
        print(f"  external_reference: {record.external_reference}", file=sys.stderr)
        raise SystemExit(3) from None

    print("✓ One coursework draft was applied and recorded in the private ledger:")
    print(f"  identity_key:       {record.identity_key}")
    print(f"  external_course_id: {record.external_course_id}")
    print(f"  external_reference: {record.external_reference}")
    print(f"  applied_at:         {record.applied_at.isoformat()}")
    print(f"  applied_by:         {record.applied_by}")
    print("\nThe item stays in DRAFT state; nothing was published to students.")
    print("Re-running the same plan with this ledger file will make no Google request.")


if __name__ == "__main__":
    main()
