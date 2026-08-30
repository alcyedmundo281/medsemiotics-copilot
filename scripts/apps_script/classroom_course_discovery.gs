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
 * This script must never expose rosters, student identifiers, coursework, submissions, grades,
 * enrollment codes, owner identifiers, group email addresses, or Drive folders, and must never
 * perform a Classroom, Drive, or Calendar write.
 */

var OPERATION = 'course_discovery';
var SCOPES = ['https://www.googleapis.com/auth/classroom.courses.readonly'];
var COURSE_STATES = ['ACTIVE', 'ARCHIVED', 'PROVISIONED', 'DECLINED', 'SUSPENDED'];

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
