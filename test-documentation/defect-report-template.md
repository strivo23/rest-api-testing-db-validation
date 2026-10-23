# Defect Report Template

Copy this template for every defect found during test execution. One defect per report.

| Field | Description |
| --- | --- |
| **Defect ID** | Unique identifier, e.g. `DEF-001` |
| **Summary** | One-line description of the problem, e.g. "PATCH /issues/{id} accepts an invalid severity value" |
| **Environment** | Operating system, Python version, API base URL, database and version, client (Postman/newman/pytest), commit or version under test |
| **Preconditions** | Required state before reproduction (existing defect record, running server, database initialised) |
| **Reproduction Steps** | Numbered steps with exact requests, payloads and query parameters |
| **Expected Result** | What the specification says should happen |
| **Actual Result** | What actually happened (status code, response body, database state) |
| **Severity** | Critical / High / Medium / Low (see definition below) |
| **Priority** | P1 / P2 / P3 / P4 (see definition below) |
| **Evidence** | Response bodies, screenshots, log excerpts, SQL query output, test names, report paths |
| **Status** | New / In Progress / Fixed / Retest / Closed / Rejected / Deferred |
| **Reported by / Date** | Tester name and date of report |
| **Notes / Related** | Related test case ids, requirement references, workarounds |

## Severity definitions

| Severity | Definition |
| --- | --- |
| Critical | Data loss or corruption, API not available, security exposure |
| High | Core documented flow broken, incorrect data returned, invalid data accepted and persisted |
| Medium | Non-core flow broken, incorrect status code, incomplete error handling |
| Low | Cosmetic or documentation issue, minor inconsistency |

## Priority definitions

| Priority | Definition |
| --- | --- |
| P1 | Must be fixed immediately; blocks all testing |
| P2 | Must be fixed before release |
| P3 | Should be fixed; has a workaround |
| P4 | Can be fixed later |

---

## Template body (copy from here)

**Defect ID:**
**Summary:**

**Environment:**
- OS:
- API base URL:
- Application version / commit:
- Database:
- Client:

**Preconditions:**
1.

**Reproduction Steps:**
1.
2.
3.

**Expected Result:**

**Actual Result:**

**Severity:**
**Priority:**
**Evidence:**
**Status:**
**Reported by / Date:**
**Notes / Related:**

---

# Illustrative example (NOT a real defect)

> The entry below is a **worked example of the template only**. No such defect was
> observed during execution of this project; the automated suite and the Postman
> collection currently pass. It is included to show how a report would be written.

**Defect ID:** DEF-000 (fictional)
**Summary:** PATCH /issues/{id} accepts an unsupported severity value and stores it

**Environment:**
- OS: Windows 11
- API base URL: http://127.0.0.1:8000
- Application version / commit: 1.0.0 (fictional branch `bug/patch-validation`)
- Database: PostgreSQL 16, database `defect_tracker`
- Client: Postman 11 / newman

**Preconditions:**
1. The API is running and the `issues` table exists.
2. A defect exists with id `1`.

**Reproduction Steps:**
1. Send `PATCH /issues/1` with body `{"severity": "Blocker"}`.
2. Observe the response.
3. Run `SELECT severity FROM issues WHERE id = 1;` in PostgreSQL.

**Expected Result:** HTTP 422 with `error.type = "validation_error"`; the stored severity is unchanged.

**Actual Result:** HTTP 200 and the row stores `Blocker`, which violates the documented value list.

**Severity:** High
**Priority:** P2
**Evidence:** Postman response body, pytest test `test_patch_issue_with_invalid_data_returns_422` failing, SQL output.
**Status:** Fixed (example)
**Reported by / Date:** QA Engineer / 2026-10-23 (fictional)
**Notes / Related:** Related test case `TC-UPD-002`; fix would validate the enum in the Pydantic schema before the database write.
