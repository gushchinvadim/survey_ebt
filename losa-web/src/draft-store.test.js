import test from "node:test";
import assert from "node:assert/strict";
import { loadDraft, storeDraft, prepareDemography } from "./draft-store.js";

const draft = {
  revision: 0,
  meta: {},
  form: {
    date: "2026-10-16",
    actual_departure: "AAA",
    actual_arrival: "BBB",
    captain_experience: "10",
    captain_type_experience: "5",
    first_officer_experience: "",
    first_officer_type_experience: "0",
    working_together: "",
    is_delay: false,
    delay: "15",
  },
  dirty: true,
};
test("draft persists and is isolated by user and assignment", () => {
  const map = new Map();
  const storage = {
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => map.set(k, v),
  };
  storeDraft(storage, 1, "assignment", draft);
  assert.equal(
    loadDraft(storage, 1, "assignment").form.captain_experience,
    "10",
  );
  assert.equal(loadDraft(storage, 2, "assignment"), null);
  assert.equal(loadDraft(storage, 1, "other"), null);
});
test("quota failure is not reported as saved", () => {
  assert.throws(() =>
    storeDraft(
      {
        setItem() {
          throw new Error("quota");
        },
      },
      1,
      "a",
      draft,
    ),
  );
});
test("normalization distinguishes zero and unknown; disabled delay clears minutes", () => {
  const data = prepareDemography(draft);
  assert.equal(data.captain_experience, 10);
  assert.equal(data.first_officer_experience, null);
  assert.equal(data.first_officer_type_experience, 0);
  assert.equal(data.delay, null);
});
test("fractional and inconsistent experience rejected", () => {
  assert.throws(() =>
    prepareDemography({
      ...draft,
      form: { ...draft.form, captain_experience: "2.5" },
    }),
  );
  assert.throws(() =>
    prepareDemography({
      ...draft,
      form: { ...draft.form, captain_type_experience: "11" },
    }),
  );
});

test("preflight facts and all scores survive local save and submission", () => {
  const preflight = {
    facts: "Наблюдения\nЭкипаж выполнил инструктаж",
    scores: { "1-1": 4, "1-2": null, "2-1": 2 },
  };
  const value = { ...draft, form: { ...draft.form, preflight } };
  const map = new Map();
  const storage = { getItem: k => map.get(k) ?? null, setItem: (k, v) => map.set(k, v) };
  storeDraft(storage, 1, "assignment", value);
  const restored = loadDraft(storage, 1, "assignment");
  assert.deepEqual(restored.form.preflight, preflight);
  assert.deepEqual(prepareDemography(restored).preflight, preflight);
});

test("final crew observations persist offline, preserve null and do not calculate total", async () => {
  const { emptyFinalCrew } = await import("./final-crew-data.js");
  const final = emptyFinalCrew();
  final.free_communication = 4;
  final.capt_as_leader = 4;
  final.general_mark_capt = 4;
  final.general_mark_copilot = 4;
  final.total_general_mark = 1;
  final.preflight_brief_with_fa = "3";
  final.general_notes = "  Общее впечатление\nЭкипаж  ";
  const value = { ...draft, form: { ...draft.form, final_crew_mark: final } };
  const map = new Map();
  const storage = { getItem: k => map.get(k) ?? null, setItem: (k,v) => map.set(k,v) };
  storeDraft(storage, 1, "assignment", value);
  const saved = loadDraft(storage, 1, "assignment");
  assert.deepEqual(saved.form.final_crew_mark, final);
  assert.equal(prepareDemography(saved).final_crew_mark.total_general_mark, 1);
  saved.form.final_crew_mark.free_communication = null;
  assert.equal(prepareDemography(saved).final_crew_mark.free_communication, null);
  assert.equal(prepareDemography(saved).final_crew_mark.general_notes, final.general_notes);
});
