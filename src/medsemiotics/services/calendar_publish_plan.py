"""Pure service function for constructing validated calendar publish requests."""

from collections.abc import Collection
from zoneinfo import ZoneInfo

from medsemiotics.domain.coaching import CalendarPublishRequest, CoachingBrief
from medsemiotics.domain.constants import (
    MANAGED_TRUE_VALUE,
    PROP_CLASS_DATE,
    PROP_COURSE_CODE,
    PROP_MANAGED,
    PROP_SCHEMA_VERSION,
    PROP_SEMESTER_ID,
    PROP_TOPIC_ID,
    SCHEMA_VERSION_VALUE,
)
from medsemiotics.domain.effective_schedule import (
    EffectiveClassEvent,
    EffectiveClassStatus,
)
from medsemiotics.domain.exceptions import CalendarPublishPlanError
from medsemiotics.services.coaching_formatter import (
    build_teaching_event_title,
    format_coaching_brief,
)


def build_calendar_publish_request(
    *,
    calendar_id: str,
    semester_timezone: ZoneInfo,
    class_event: EffectiveClassEvent,
    brief: CoachingBrief,
    reminders_minutes: Collection[int] = (),
) -> CalendarPublishRequest:
    """Build and validate a provider-neutral CalendarPublishRequest.

    Args:
        calendar_id: Google Calendar identifier.
        semester_timezone: Academic semester ZoneInfo.
        class_event: Reconciled EffectiveClassEvent representing the target class meeting.
        brief: Structured CoachingBrief content for the class.
        reminders_minutes: Optional popup reminder lead times in minutes.

    Returns:
        Validated CalendarPublishRequest instance.

    Raises:
        CalendarPublishPlanError: If class is cancelled, times are missing, or scopes mismatch.
    """
    if class_event.status == EffectiveClassStatus.CANCELLED:
        msg = f"Cannot publish coaching brief for cancelled class on {class_event.date} ({class_event.course_code})."
        raise CalendarPublishPlanError(msg)

    if (
        class_event.semester_id != brief.semester_id
        or class_event.course_code != brief.course_code
        or class_event.date != brief.class_date
    ):
        msg = (
            f"Scope mismatch between class event "
            f"({class_event.semester_id}, {class_event.course_code}, {class_event.date}) "
            f"and coaching brief ({brief.semester_id}, {brief.course_code}, {brief.class_date})."
        )
        raise CalendarPublishPlanError(msg)

    if class_event.start is None or class_event.end is None:
        msg = (
            f"Class event on {class_event.date} for {class_event.course_code} "
            "does not contain start/end timestamps required for publishing."
        )
        raise CalendarPublishPlanError(msg)

    local_start = class_event.start.astimezone(semester_timezone)
    local_end = class_event.end.astimezone(semester_timezone)

    title = build_teaching_event_title(
        course_code=brief.course_code,
        topic_title=brief.topic_title,
    )
    description = format_coaching_brief(brief)

    metadata: dict[str, str] = {
        PROP_MANAGED: MANAGED_TRUE_VALUE,
        PROP_SEMESTER_ID: brief.semester_id,
        PROP_COURSE_CODE: brief.course_code,
        PROP_CLASS_DATE: brief.class_date.isoformat(),
        PROP_SCHEMA_VERSION: SCHEMA_VERSION_VALUE,
    }
    if brief.topic_id:
        metadata[PROP_TOPIC_ID] = brief.topic_id

    return CalendarPublishRequest(
        calendar_id=calendar_id,
        event_date=brief.class_date,
        start=local_start,
        end=local_end,
        title=title,
        description=description,
        location=None,
        reminders_minutes=sorted(set(reminders_minutes)),
        metadata=metadata,
    )
