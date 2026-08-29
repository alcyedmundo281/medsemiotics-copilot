# Loop 0.4E-B live Calendar verification record

This tracked record preserves the non-secret evidence that had previously existed only in an
ignored scratch workflow and conversation history.

## Verified result

On 2026-08-27, a dedicated Google Workspace account completed a controlled live test against the
`Neurologia HECAM` calendar using course code `TEST`.

Two consecutive executions verified:

```text
OAuth read                         passed
OAuth calendar.events write       passed
Initial publish                    updated
Ownership lookup                  passed
Update                             passed
Unchanged/no-op detection          passed
Read-back mapping                  passed
Stable event ID                    qavfi3g48tsdg98jeb74mdc5kc
Duplicate TEST events              0
Delete calls                       0
```

The original rerunnable helper lived under ignored `scratch/` and was therefore not contained in
commit `07a1aaa`; that commit added the live setup documentation only. The supported tracked tool
is `scripts/google_calendar_write_smoke.py`. It is dry-run by default, uses neutral `TEST` content,
accepts `created`, `updated`, or `unchanged` as valid idempotent outcomes, and requires an explicit
`--execute` flag before it can mutate Calendar.

No OAuth client secret, refresh token, account email, or credential path is recorded here.

## GASTRO activation verification

On 2026-08-29, after binding the dedicated empty `Gastroenterología HECAM` calendar, the
tracked public smoke tool verified the production route with neutral `TEST` metadata:

```text
First publish                      created
Second identical publish          unchanged
Stable event ID                    dfha8ls15ektv7r8m2ngqfjuu8
Read-back events on test date      1
Read-back event ID                 dfha8ls15ektv7r8m2ngqfjuu8
Duplicate TEST events              0
```

The test event is scheduled for 2026-09-02 from 18:00 to 18:15 in
`America/Guayaquil`, contains no attendees, meeting link, attachment, student data, or clinical
content, and can be removed manually from Google Calendar after review.
