import test from "node:test";
import assert from "node:assert/strict";
import {
  emptyJournal, newObservation, observationId, needsDetails, putObservation,
  removeObservation, observationProblem, searchMistakes, searchThreats,
} from "./observation-data.js";
import { loadDraft, storeDraft, prepareDemography } from "./draft-store.js";

const catalog = {
  phases: [{ id: 1, code: "preflight", label: "Предполетная" }],
  mistakes: [
    { id: 1, code: "111", name: "Связь с УВД", type_id: 2, section_id: 5 },
    { id: 2, code: "48", name: "Параметры", type_id: 4, section_id: null },
  ],
  threats: [{ id: 1, code: "12", type: "atc", describe: "Команда УВД" }],
};
test("UUID fallback works without randomUUID (HTTP local network)", () => {
  const fallback = { getRandomValues(bytes) { return bytes.fill(17); } };
  const id = observationId(fallback);
  assert.match(id, /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
  assert.throws(() => observationId({}));
});
test("repeated same mistake remains two different observations", () => {
  let journal = emptyJournal();
  const a = { ...newObservation("mistake",1), mistake: 1 };
  const b = { ...newObservation("mistake",1), mistake: 1 };
  journal = putObservation(putObservation(journal,"mistake",a),"mistake",b);
  assert.equal(journal.mistakes.length,2);
  assert.notEqual(a.id,b.id);
  journal = putObservation(journal,"mistake",{...a,comment:"Обновлено"});
  assert.equal(journal.mistakes.length,2);
  assert.equal(journal.mistakes[0].comment,"Обновлено");
});
test("quick capture validates only reference and phase; false is a completed answer", () => {
  const mistake = newObservation("mistake");
  assert.equal(observationProblem("mistake",mistake,emptyJournal(),catalog),"Выберите точную фазу полёта.");
  mistake.flight_phase=1;
  assert.equal(observationProblem("mistake",mistake,emptyJournal(),catalog),"Выберите конкретную ошибку.");
  mistake.mistake=1;
  assert.equal(observationProblem("mistake",mistake,emptyJournal(),catalog),"");
  assert.equal(needsDetails("mistake",mistake),true);
  const threat = { ...newObservation("threat",1), threat:1, was_control_effective:false, correct_actions:false };
  assert.equal(needsDetails("threat",threat),false);
});
test("links use observation UUIDs, not threat dictionary IDs", () => {
  const threat = {...newObservation("threat",1),threat:1};
  const mistake = {...newObservation("mistake",1),mistake:1,threat_id:threat.id};
  const journal=putObservation(emptyJournal(),"threat",threat);
  assert.equal(observationProblem("mistake",mistake,journal,catalog),"");
  assert.notEqual(observationProblem("mistake",mistake,emptyJournal(),catalog),"");
});
test("deleting linked threat is blocked; explicit tombstones survive retry", () => {
  const threat={...newObservation("threat",1),threat:1};
  const mistake={...newObservation("mistake",1),mistake:1,threat_id:threat.id};
  let journal=putObservation(putObservation(emptyJournal(),"threat",threat),"mistake",mistake);
  assert.throws(()=>removeObservation(journal,"threat",threat.id));
  journal=putObservation(journal,"mistake",{...mistake,threat_id:null});
  journal=removeObservation(journal,"threat",threat.id);
  journal=removeObservation(journal,"threat",threat.id);
  assert.deepEqual(journal.deleted_threats,[threat.id]);
});
test("type-section filtering and code/name search support unsectioned mistakes", () => {
  assert.equal(searchMistakes(catalog,"111","2","5").length,1);
  assert.equal(searchMistakes(catalog,"параметры","4","none")[0].id,2);
  assert.equal(searchMistakes(catalog,"","2","none").length,0);
  assert.equal(searchThreats(catalog,"увд","atc").length,1);
});
test("incomplete scratch survives reload but is excluded from API payload", () => {
  const raw=newObservation("mistake");
  raw.comment="Пока только текст";
  const journal=emptyJournal();
  const draft={
    revision:0,form:{is_delay:false,delay:null,observations:journal},
    meta:{observations:catalog},observation_scratch:{[raw.id]:{kind:"mistake",event:raw}},
  };
  const map=new Map();
  const storage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v)};
  storeDraft(storage,2,"assignment",draft);
  const saved=loadDraft(storage,2,"assignment");
  assert.equal(saved.observation_scratch[raw.id].event.comment,"Пока только текст");
  const payload=prepareDemography(saved);
  assert.equal("observation_scratch" in payload,false);
  assert.deepEqual(payload.observations,emptyJournal());
});
test("safety-linked mistake needs explicit detach before deletion",()=>{
  const row={...newObservation("mistake",1),mistake:1,safety_condition_ids:[7]};
  const journal=putObservation(emptyJournal(),"mistake",row);
  assert.throws(()=>removeObservation(journal,"mistake",row.id));
});
