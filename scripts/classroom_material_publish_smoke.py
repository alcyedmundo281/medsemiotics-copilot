"""Publish one approved Classroom material package and persist private evidence (Loop 0.7D).

Usage:
    python scripts/classroom_material_publish_smoke.py --course-id <id> --topic-id <id> \
        --title "..." --folder-url "https://drive.google.com/drive/folders/..." \
        --approved-by "Name" --ledger-file <private path>

Optional resources are supplied one at a time as JSON objects:
    --resource-json '{"resource_type":"form","title":"...","url":"https://..."}'

The script publishes exactly one student-visible ``CourseWorkMaterial``. A repeated plan becomes a
local no-op before deployment credentials are loaded or Google is contacted. The required ledger
must remain outside tracked public content.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,
    ClassroomAccessRequest,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_action import ClassroomActionApproval, ClassroomActionStatus
from medsemiotics.domain.classroom_material import (
    ClassroomMaterialPackagePlan,
    ClassroomMaterialResource,
)
from medsemiotics.domain.exceptions import MedSemioticsError
from medsemiotics.integrations.google_classroom import (
    AppsScriptCourseworkMaterialWriter,
    AuthenticatedAppsScriptTransport,
    build_operator_token_provider,
    load_apps_script_deployment,
)
from medsemiotics.services.classroom_access_policy import ClassroomAccessPolicy
from medsemiotics.services.classroom_action_ledger import ClassroomActionLedgerRepository
from medsemiotics.services.classroom_material_publish import ClassroomMaterialPublishAuthorizer


def _parse_resource(value: str) -> ClassroomMaterialResource:
    """Parse one strict JSON resource without accepting hidden or extra fields."""
    try:
        raw: Any = json.loads(value)
    except json.JSONDecodeError as err:
        raise argparse.ArgumentTypeError(f"resource must be valid JSON: {err.msg}") from None
    try:
        return ClassroomMaterialResource.model_validate(raw)
    except ValidationError as err:
        raise argparse.ArgumentTypeError(f"invalid material resource: {err}") from None


def parse_arguments() -> argparse.Namespace:
    """Parse the operator-reviewed, single-material publication."""
    parser = argparse.ArgumentParser(
        description="Publish one approved, folder-backed Classroom material package."
    )
    parser.add_argument("--course-id", required=True, help="Classroom course id from the view")
    parser.add_argument("--course-code", default="NEURO", help="Tracked course code")
    parser.add_argument("--semester-id", default="2026-2", help="Academic semester")
    parser.add_argument("--topic-id", required=True, help="Tracked syllabus topic")
    parser.add_argument("--title", required=True, help="Student-visible material title")
    parser.add_argument("--description", default=None, help="Optional student-visible description")
    parser.add_argument("--folder-url", required=True, help="Reviewed HTTPS Drive folder URL")
    parser.add_argument(
        "--resource-json",
        action="append",
        default=[],
        type=_parse_resource,
        help="Optional strict JSON resource; repeat for at most nineteen resources",
    )
    parser.add_argument("--prepared-by", default="operator", help="Author of the plan")
    parser.add_argument("--approved-by", required=True, help="Named human approving the package")
    parser.add_argument(
        "--ledger-file",
        required=True,
        type=Path,
        help="Private JSON ledger path outside tracked public content",
    )
    return parser.parse_args()


def main() -> None:
    """Publish one approved package and print only its minimal ledger evidence."""
    arguments = parse_arguments()
    print("=== MedSemiotics Classroom Material Verification (Loop 0.7D) ===")

    now = datetime.now(tz=None).astimezone()
    try:
        plan = ClassroomMaterialPackagePlan(
            semester_id=arguments.semester_id,
            course_code=arguments.course_code,
            external_course_id=arguments.course_id,
            topic_id=arguments.topic_id,
            title=arguments.title,
            description=arguments.description,
            folder_url=arguments.folder_url,
            resources=tuple(arguments.resource_json),
            prepared_by=arguments.prepared_by,
            prepared_at=now,
        )
    except ValidationError as err:
        print(f"ERROR Package validation: {err}", file=sys.stderr)
        raise SystemExit(2) from None

    print(f"  course_code:   {plan.course_code}")
    print(f"  topic_id:      {plan.topic_id}")
    print(f"  material_count:{1 + len(plan.resources):>4}")
    print(f"  identity_key:  {plan.identity_key}")
    print(f"  fingerprint:   {plan.content_fingerprint}")
    print(f"  approved_by:   {arguments.approved_by}")

    authorizer = ClassroomMaterialPublishAuthorizer(build_default_agent_framework())
    ledger = ClassroomActionLedgerRepository(arguments.ledger_file)
    try:
        action_decision = authorizer.authorize(
            plan=plan,
            approval=ClassroomActionApproval(
                approved_by=arguments.approved_by,
                approved_at=now,
                content_fingerprint=plan.content_fingerprint,
            ),
            applied_actions=ledger.load(),
        )
    except MedSemioticsError as err:
        print(f"ERROR Authorization: {err}", file=sys.stderr)
        raise SystemExit(2) from None

    if action_decision.status is ClassroomActionStatus.ALREADY_APPLIED:
        print("OK No-op: this material package is already recorded in the private ledger.")
        print(f"  external_reference: {action_decision.existing_reference or 'not recorded'}")
        print("\nNo Google request was made and no duplicate material was published.")
        return

    try:
        access_decision = ClassroomAccessPolicy().authorize(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSEWORK_MATERIAL_PUBLISH,
                data_categories=(ClassroomDataCategory.OWN_COURSEWORK_MATERIAL,),
                oauth_scopes=(GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,),
                requested_by=arguments.prepared_by,
                external_mutation=True,
            )
        )
        deployment = load_apps_script_deployment()
    except MedSemioticsError as err:
        print(f"ERROR Authorization: {err}", file=sys.stderr)
        raise SystemExit(2) from None

    writer = AppsScriptCourseworkMaterialWriter(
        deployment=deployment,
        transport=AuthenticatedAppsScriptTransport(token_provider=build_operator_token_provider()),
    )
    try:
        record = writer.publish(
            plan=plan,
            action_decision=action_decision,
            access_decision=access_decision,
        )
    except MedSemioticsError as err:
        print(f"ERROR Write boundary: {err}", file=sys.stderr)
        raise SystemExit(1) from None

    try:
        ledger.append(record)
    except MedSemioticsError as err:
        print(f"ERROR Critical ledger persistence failure: {err}", file=sys.stderr)
        print(
            "The material may be visible in Classroom. Preserve this recovery evidence:",
            file=sys.stderr,
        )
        print(f"  identity_key:       {record.identity_key}", file=sys.stderr)
        print(f"  external_reference: {record.external_reference}", file=sys.stderr)
        raise SystemExit(3) from None

    print("OK One student-visible material package was published and recorded:")
    print(f"  course_code:        {plan.course_code}")
    print(f"  identity_key:       {record.identity_key}")
    print(f"  external_reference: {record.external_reference}")
    print(f"  applied_at:         {record.applied_at.isoformat()}")
    print(f"  applied_by:         {record.applied_by}")
    print("\nRe-running the identical plan with this ledger makes no Google request.")


if __name__ == "__main__":
    main()
