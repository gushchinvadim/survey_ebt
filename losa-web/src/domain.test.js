import test from "node:test";
import assert from "node:assert/strict";
import { dateKey, canStart, validateAssignment } from "./domain.js";

const user = { roles: ["auditor"], auditor_id: 2 };
const assignment = { date: "2026-10-15", auditor: 2, status: "scheduled" };
test("program date changes at UTC midnight", () => {
  assert.equal(dateKey(new Date("2026-10-14T21:01:00Z")), "2026-10-14");
  assert.equal(dateKey(new Date("2026-10-14T23:59:59Z")), "2026-10-14");
  assert.equal(dateKey(new Date("2026-10-15T00:00:00Z")), "2026-10-15");
});
test("only assigned auditor can start on or after assignment date", () => {
  assert.equal(canStart(assignment, user, "2026-10-15"), true);
  assert.equal(canStart(assignment, user, "2026-10-14"), false);
  assert.equal(canStart(assignment, user, "2026-10-16"), true);
  assert.equal(
    canStart(assignment, { ...user, auditor_id: 1 }, "2026-10-15"),
    false,
  );
  assert.equal(
    canStart(
      assignment,
      { roles: ["coordinator"], auditor_id: 2 },
      "2026-10-15",
    ),
    false,
  );
  assert.equal(
    canStart({ ...assignment, status: "completed" }, user, "2026-10-15"),
    false,
  );
});
test("coordinator with auditor permission can perform own assignment", () => {
  assert.equal(
    canStart(
      assignment,
      { ...user, roles: ["coordinator", "auditor"] },
      "2026-10-15",
    ),
    true,
  );
});

test("server denial overrides client date and role", () => {
  assert.equal(
    canStart({ ...assignment, can_start: false }, user, "2026-10-15"),
    false,
  );
});
test("crew cannot contain same pilot twice and references must exist", () => {
  const catalog = {
    flights: [{ id: 1 }],
    pilots: [{ id: 1 }, { id: 2 }],
    auditors: [{ id: 2 }],
  };
  const data = {
    date: "2026-10-15",
    flight: 1,
    captain: 1,
    first_officer: 2,
    auditor: 2,
  };
  assert.equal(validateAssignment(data, catalog), "");
  assert.notEqual(
    validateAssignment({ ...data, first_officer: 1 }, catalog),
    "",
  );
  assert.notEqual(validateAssignment({ ...data, auditor: 99 }, catalog), "");
});
