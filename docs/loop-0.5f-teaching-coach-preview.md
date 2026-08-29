# Loop 0.5F — Automatic Teaching Coach Preview

## Purpose

Close the gap between the catalog-backed Teaching Coach engine and a usable conversational
experience. A caller should be able to ask for the brief for one course and class date without
knowing which internal topic ID is current.

## Delivered contract

`TeachingCoachPreviewRequest` requires:

- semester and course;
- explicit class date;
- explicit timezone-aware calendar evaluation window; and
- an accountable requester.

`TeachingCoachPreviewService` then:

1. resolves the effective teaching position;
2. rejects an inactive date, mismatched scope, or completed course;
3. selects the authoritative current topic;
4. delegates to the existing catalog-backed draft service;
5. relies on the Teaching Coach agent to revalidate the topic and state; and
6. returns the structured draft plus a human-readable preview title and body.

## Safety boundaries

- Read-only KNOW and REASON workflow.
- No Calendar, Classroom, or Drive writer dependency.
- No publish method and no combined preview-and-publish operation.
- No LLM dependency or invented medical content.
- No caller-supplied topic override.
- Any missing guide or state discrepancy fails closed.

## Acceptance evidence

- Unit coverage for automatic topic selection, rendering, invalid dates, completed courses,
  cross-course state, missing guides, strict request fields, and timezone-aware windows.
- Real tracked configuration coverage for both NEURO and GASTRO with empty Calendar evidence.
- The existing agent authorization and separate approved publication workflow remain unchanged.

## Explicitly out of scope

- HTTP/mobile endpoint deployment.
- Google Classroom access.
- LLM enrichment.
- Calendar or Classroom writes.
- Autonomous publication.
