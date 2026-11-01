import test from "node:test";
import assert from "node:assert/strict";
import { emptyApproach, prepareApproach } from "./approach-data.js";
import { loadDraft, storeDraft, prepareDemography } from "./draft-store.js";

test("each checkpoint starts empty and is independent", () => {
  const data = emptyApproach();
  data.measurements["1000_ft"].speed_deviation = 10;
  assert.equal(data.measurements["500_ft"].speed_deviation, null);
  assert.equal(data.descent.ten_thousand_brief, null);
  assert.equal(data.conditions.visual_condition, null);
});

test("signed speed outside guidance and decimal comma are preserved", () => {
  const data = emptyApproach();
  data.measurements.glideslope_entry.speed_deviation = "+25";
  data.measurements["1000_ft"].speed_deviation = "-8";
  data.measurements["500_ft"].speed_deviation = "0";
  data.measurements["500_ft"].course_deviation = "1,25";
  data.measurements["500_ft"].course_more_than = true;
  data.measurements["1000_ft"].glideslope_deviation = "0";
  const saved = prepareApproach(data);
  assert.equal(saved.measurements.glideslope_entry.speed_deviation, 25);
  assert.equal(saved.measurements["1000_ft"].speed_deviation, -8);
  assert.equal(saved.measurements["500_ft"].speed_deviation, 0);
  assert.equal(saved.measurements["500_ft"].course_deviation, "1.25");
  assert.equal(saved.measurements["1000_ft"].glideslope_deviation, "0.00");
  assert.equal(data.measurements["500_ft"].course_deviation, "1,25");
});

test("invalid numbers and more-than without value cannot be sent", () => {
  for (const [field, value] of [
    ["speed_deviation", "1.5"], ["speed_deviation", "+"],
    ["course_deviation", "-1"], ["course_deviation", "0.001"],
    ["glideslope_deviation", "Infinity"],
  ]) {
    const data = emptyApproach();
    data.measurements["1000_ft"][field] = value;
    assert.throws(() => prepareApproach(data));
  }
  const data = emptyApproach();
  data.measurements["1000_ft"].course_more_than = true;
  assert.throws(() => prepareApproach(data));
});

test("offline draft preserves incomplete input and previous block; submission normalizes a copy", () => {
  const approach = emptyApproach();
  approach.descent.describe_deviation = "Причина\nДействия";
  approach.measurements["1000_ft"].speed_deviation = "+";
  const draft = {
    revision: 2, meta: {}, form: {
      date: "2026-10-18", is_delay: false, delay: null,
      captain_experience: null, captain_type_experience: null,
      first_officer_experience: null, first_officer_type_experience: null,
      cruise: { facts: "Факты крейсерского этапа" }, approach,
    },
  };
  const map = new Map();
  const storage = { getItem: k => map.get(k) ?? null, setItem: (k,v) => map.set(k,v) };
  storeDraft(storage, 3, "audit", draft);
  let saved = loadDraft(storage, 3, "audit");
  assert.equal(saved.form.approach.measurements["1000_ft"].speed_deviation, "+");
  assert.throws(() => prepareDemography(saved));
  saved.form.approach.measurements["1000_ft"].speed_deviation = "+10";
  const payload = prepareDemography(saved);
  assert.equal(payload.approach.measurements["1000_ft"].speed_deviation, 10);
  assert.equal(saved.form.approach.measurements["1000_ft"].speed_deviation, "+10");
  assert.equal(payload.cruise.facts, "Факты крейсерского этапа");
  assert.equal(loadDraft(storage, 4, "audit"), null);
});

test("legacy drafts omit new block without erasing it on server", () => {
  const value = prepareDemography({ revision: 0, form: { is_delay: false, delay: null } });
  assert.equal(Object.hasOwn(value, "approach"), false);
});
