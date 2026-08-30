/**
 * MedSemiotics — metadata-only Google Classroom course discovery (Loop 0.6B).
 *
 * Deploy this script inside the dedicated Workspace account that owns the Classroom
 * authorization. The deployment holds the persistent grant; MedSemiotics never stores a
 * Classroom OAuth token. The reply is sanitized here and re-validated by
 * `AppsScriptCourseDiscoveryClient` before any value reaches the domain.
 *
 * Deployment settings: "Execute as: Me", "Who has access: Only myself" (or the dedicated
 * Workspace account). Enable the Classroom advanced service (v1) and pin the single scope
 * `https://www.googleapis.com/auth/classroom.courses.readonly` in `appsscript.json`.
 *
 * Owner-only access is intentional for Loop 0.6B: the read path is exercised through an injected
 * transport and from the owning account's authenticated session. Unattended invocation from a
 * backend needs an authenticated caller identity and belongs to Loop 0.6F; see
 * `docs/loop-0.6b-classroom-apps-script-read-boundary.md`.
 *
 * This script must never expose rosters, student identifiers, existing coursework, submissions,
 * grades, enrollment codes, owner identifiers, group email addresses, or Drive folders.
 *
 * It performs exactly one write, added in Loop 0.6F: creating a coursework item in DRAFT state
 * from an approved MedSemiotics plan. It never publishes coursework to students, never sets
 * maxPoints or any grading field, and never modifies or deletes an existing item.
 */

var OPERATION = 'course_discovery';
var WRITE_OPERATION = 'coursework_draft_create';
var SCOPES = ['https://www.googleapis.com/auth/classroom.courses.readonly'];
var WRITE_SCOPES = ['https://www.googleapis.com/auth/classroom.coursework.students'];
var COURSE_STATES = ['ACTIVE', 'ARCHIVED', 'PROVISIONED', 'DECLINED', 'SUSPENDED'];
var DRAFT_STATE = 'DRAFT';

/**
 * Handle one read request and return the sanitized course-discovery envelope.
 *
 * @param {Object} e Apps Script web app event object.
 * @return {GoogleAppsScript.Content.TextOutput} JSON envelope.
 */
function doGet(e) {
  var requestedOperation = (e && e.parameter && e.parameter.operation) || OPERATION;
  if (requestedOperation !== OPERATION) {
    return jsonOutput({ error: 'unsupported_operation' });
  }
  return jsonOutput({
    operation: OPERATION,
    scopes: SCOPES,
    external_mutation: false,
    courses: listCourseMetadata()
  });
}

/**
 * List accessible courses reduced to non-personal metadata.
 *
 * @return {Array<Object>} Sanitized course metadata entries.
 */
function listCourseMetadata() {
  var courses = [];
  var pageToken = null;

  do {
    var response = Classroom.Courses.list({
      courseStates: COURSE_STATES,
      pageSize: 100,
      pageToken: pageToken
    });

    var items = response.courses || [];
    for (var index = 0; index < items.length; index += 1) {
      courses.push(sanitizeCourse(items[index]));
    }

    pageToken = response.nextPageToken || null;
  } while (pageToken);

  return courses;
}

/**
 * Copy only the five declared metadata fields from one Classroom course.
 *
 * @param {Object} course Raw Classroom course resource.
 * @return {Object} Sanitized course metadata.
 */
function sanitizeCourse(course) {
  return {
    id: course.id || '',
    name: course.name || '',
    section: course.section || null,
    course_state: course.courseState || '',
    alternate_link: course.alternateLink || null
  };
}

/**
 * Serialize a payload as a JSON web-app response.
 *
 * @param {Object} payload Response payload.
 * @return {GoogleAppsScript.Content.TextOutput} JSON output.
 */
function jsonOutput(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(
    ContentService.MimeType.JSON
  );
}

/**
 * Handle one write request and create a single coursework item in DRAFT state.
 *
 * The request body declares only the fields MedSemiotics is allowed to send. No grading field is
 * read from the request or sent to Classroom, and the item is never published to students.
 *
 * @param {Object} e Apps Script web app event object.
 * @return {GoogleAppsScript.Content.TextOutput} JSON envelope.
 */
function doPost(e) {
  var request = parseRequest(e);
  if (!request || request.operation !== WRITE_OPERATION) {
    return jsonOutput({ error: 'unsupported_operation' });
  }
  if (!request.course_id || !request.title) {
    return jsonOutput({ error: 'incomplete_request' });
  }

  var coursework = {
    title: String(request.title),
    workType: 'ASSIGNMENT',
    state: DRAFT_STATE
  };
  if (request.instructions) {
    coursework.description = String(request.instructions);
  }
  var dueDate = parseDueDate(request.due_date);
  if (dueDate) {
    coursework.dueDate = dueDate;
    coursework.dueTime = { hours: 23, minutes: 59 };
  }

  var created = Classroom.Courses.CourseWork.create(coursework, String(request.course_id));

  return jsonOutput({
    operation: WRITE_OPERATION,
    scopes: WRITE_SCOPES,
    external_mutation: true,
    coursework: {
      id: created.id || '',
      state: created.state || '',
      alternate_link: created.alternateLink || null
    }
  });
}

/**
 * Decode the JSON request body of a write request.
 *
 * @param {Object} e Apps Script web app event object.
 * @return {Object|null} Parsed request, or null when it cannot be read.
 */
function parseRequest(e) {
  if (!e || !e.postData || !e.postData.contents) {
    return null;
  }
  try {
    return JSON.parse(e.postData.contents);
  } catch (err) {
    return null;
  }
}

/**
 * Convert an ISO date string into the Classroom date shape.
 *
 * @param {string} value ISO-8601 local date, or an empty string.
 * @return {Object|null} Classroom date, or null when no due date was requested.
 */
function parseDueDate(value) {
  if (!value) {
    return null;
  }
  var parts = String(value).split('-');
  if (parts.length !== 3) {
    return null;
  }
  return {
    year: Number(parts[0]),
    month: Number(parts[1]),
    day: Number(parts[2])
  };
}
