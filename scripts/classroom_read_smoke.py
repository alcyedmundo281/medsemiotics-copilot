"""Manual operator script for live Classroom read verification (Loop 0.6F).

Usage:
    python scripts/classroom_read_smoke.py

Requires, in the environment of the dedicated Workspace operator and never in Git:

    MEDSEMIOTICS_CLASSROOM_APPS_SCRIPT_URL            Apps Script execution URL
    MEDSEMIOTICS_CLASSROOM_APPS_SCRIPT_DEPLOYMENT_ID  Deployment identifier
    MEDSEMIOTICS_CLASSROOM_SERVICE_ACCOUNT_FILE       Service account key file
    MEDSEMIOTICS_CLASSROOM_IMPERSONATED_SUBJECT       Workspace user to impersonate
    MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES              Optional comma-separated caller scopes

This script is for interactive operator verification and is NOT run by automated test suites.
It prints redacted evidence only: counts, lifecycle totals, and a content fingerprint. Course
names, identifiers, links, and the execution URL are never printed, so its output can be pasted
into a verification record.
"""

import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.domain.exceptions import MedSemioticsError
from medsemiotics.integrations.google_classroom import (
    AppsScriptCourseDiscoveryClient,
    AuthenticatedAppsScriptTransport,
    GoogleClassroomAuthenticationError,
    GoogleCredentialsTokenProvider,
    load_apps_script_deployment,
)
from medsemiotics.services.classroom_course_discovery import (
    ClassroomCourseDiscoveryService,
)
from medsemiotics.services.classroom_snapshot import ClassroomSnapshotNormalizer

SERVICE_ACCOUNT_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_SERVICE_ACCOUNT_FILE"
SUBJECT_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_IMPERSONATED_SUBJECT"
CALLER_SCOPES_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES"

DEFAULT_CALLER_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)


def build_token_provider() -> GoogleCredentialsTokenProvider:
    """Build the bearer-token source for the dedicated Workspace identity.

    Returns:
        Token provider wrapping impersonated service account credentials.

    Raises:
        SystemExit: If the operator environment is incomplete.
    """
    key_file = os.environ.get(SERVICE_ACCOUNT_ENV_VAR, "").strip()
    subject = os.environ.get(SUBJECT_ENV_VAR, "").strip()
    if not key_file or not subject:
        print(
            f"✗ Set {SERVICE_ACCOUNT_ENV_VAR} and {SUBJECT_ENV_VAR} before running.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    configured_scopes = os.environ.get(CALLER_SCOPES_ENV_VAR, "").strip()
    scopes = (
        [scope.strip() for scope in configured_scopes.split(",") if scope.strip()]
        if configured_scopes
        else list(DEFAULT_CALLER_SCOPES)
    )

    credentials = service_account.Credentials.from_service_account_file(
        str(Path(key_file)),
        scopes=scopes,
    ).with_subject(subject)
    return GoogleCredentialsTokenProvider(credentials, request=Request())


def main() -> None:
    """Run one authorized live course-discovery read and print redacted evidence."""
    print("=== MedSemiotics Classroom Read Verification (Loop 0.6F) ===")

    try:
        deployment = load_apps_script_deployment()
    except MedSemioticsError as err:
        print(f"✗ Deployment configuration: {err}", file=sys.stderr)
        raise SystemExit(2) from None

    service = ClassroomCourseDiscoveryService(
        capability_framework=build_default_agent_framework(),
        discovery_client=AppsScriptCourseDiscoveryClient(
            deployment=deployment,
            transport=AuthenticatedAppsScriptTransport(
                token_provider=build_token_provider(),
            ),
        ),
    )

    requested_by = os.environ.get(SUBJECT_ENV_VAR, "operator").strip() or "operator"

    try:
        discovery = service.discover_courses(requested_by=requested_by)
    except GoogleClassroomAuthenticationError as err:
        print(f"✗ Authentication: {err}", file=sys.stderr)
        raise SystemExit(1) from None
    except MedSemioticsError as err:
        print(f"✗ Read boundary: {err}", file=sys.stderr)
        raise SystemExit(1) from None

    summary = ClassroomSnapshotNormalizer().normalize(discovery).audit_summary()

    print("✓ Authenticated read completed. Redacted evidence:")
    print(f"  provider:      {summary.provider.value}")
    print(f"  captured_at:   {summary.captured_at.isoformat()}")
    print(f"  approved_scope:{' '}{', '.join(discovery.approved_oauth_scopes)}")
    print(f"  course_count:  {summary.course_count}")
    for lifecycle, count in summary.lifecycle_counts:
        print(f"    {lifecycle.value}: {count}")
    print(f"  fingerprint:   {summary.fingerprint}")
    print("\nCourse names, identifiers, links, and the execution URL are deliberately omitted.")


if __name__ == "__main__":
    main()
