import test from "node:test";
import assert from "node:assert/strict";
import { mergeStageAssessmentDraft, prepareStageAssessments } from "./stage-assessment-data.js";
import { prepareDemography } from "./draft-store.js";
const definitions = {
  preflight: { sections: [{ criteria: [{ id: 11, code: "1-1" }, { id: 12, code: "1-2" }] }] },
};
const server = { stage_assessments: {
  preflight: { facts: "Сервер", scores: {"11": 2, "12": null} },
  cruise: { facts: "Факты на сервере", scores: {"31": null} },
}};
test("legacy offline facts and scores are upgraded by criterion code", () => {
  const local = {preflight:{facts:"Локальные факты",scores:{"1-1":4,"1-2":null}},cruise:{facts:"Крейсерские факты"}};
  const result=mergeStageAssessmentDraft(local,server,definitions);
  assert.deepEqual(result.values.preflight,{facts:"Локальные факты",scores:{"11":4,"12":null}});
  assert.equal(result.values.cruise.facts,"Крейсерские факты");
  assert.deepEqual(result.unmapped,[]);
});
test("new criteria are merged without overwriting local ratings or mutating inputs",()=>{
  const local={stage_assessments:{preflight:{facts:"Локально",scores:{"11":1}}}};
  const result=mergeStageAssessmentDraft(local,server,definitions);
  assert.deepEqual(result.values.preflight.scores,{"11":1,"12":null});
  assert.equal(server.stage_assessments.preflight.scores["11"],2);
});
test("unmappable nonempty legacy scores block submission and stay in the draft",()=>{
  const form={preflight:{facts:"Факты",scores:{"missing":3}},is_delay:false,delay:null};
  const merged=mergeStageAssessmentDraft(form,server,definitions);
  assert.deepEqual(merged.unmapped,["missing"]);
  assert.throws(()=>prepareDemography({revision:0,form:{...form,stage_assessments:merged.values},assessment_migration_errors:merged.unmapped}));
  assert.equal(form.preflight.scores.missing,3);
});
test("new payload has stage criteria IDs and omits duplicate legacy blocks",()=>{
  const form={is_delay:false,delay:null,preflight:{facts:"Старое"},cruise:{facts:"Старое"},stage_assessments:server.stage_assessments};
  const result=prepareDemography({revision:0,form});
  assert.equal("preflight" in result,false);
  assert.equal("cruise" in result,false);
  assert.equal(result.stage_assessments.preflight.scores["11"],2);
  assert.ok(form.preflight);
});
test("scale bounds and IDs are validated, empty scores remain null",()=>{
  assert.equal(prepareStageAssessments({cruise:{facts:"",scores:{"1":null}}}).cruise.scores["1"],null);
  assert.throws(()=>prepareStageAssessments({cruise:{facts:"",scores:{"1":5}}}));
  assert.throws(()=>prepareStageAssessments({cruise:{facts:"",scores:{"bad":2}}}));
});
