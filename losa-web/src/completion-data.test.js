import test from "node:test";
import assert from "node:assert/strict";
import { scratchCount, completionRequest } from "./completion-data.js";
import { loadDraft, storeDraft } from "./draft-store.js";

test("scratch drafts are counted separately from fixed journal observations",()=>{
  assert.equal(scratchCount({form:{observations:{mistakes:[{id:"saved"}]}}}),0);
  assert.equal(scratchCount({observation_scratch:{a:{},b:{}}}),2);
});
test("review and final confirmation carry the same snapshot and explicit acknowledgement",()=>{
  const form={revision:3,stage_assessments:{}};
  const draft={observation_scratch:{}};
  const preview=completionRequest(form,draft);
  assert.deepEqual(preview,{form,scratch_count:0});
  const complete=completionRequest(form,draft,{review_token:"signed",acknowledged:true});
  assert.equal(complete.form,form);
  assert.equal(complete.review_token,"signed");
  assert.equal(complete.acknowledge_missing,true);
  assert.equal(completionRequest(form,draft,{review_token:"signed"}).acknowledge_missing,false);
});
test("completed status persists locally with unfinished scratch; no data is removed",()=>{
  const map=new Map();
  const storage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v)};
  const draft={status:"completed",revision:8,meta:{},form:{stage_assessments:{}},
    observation_scratch:{raw:{kind:"mistake",event:{comment:"Локальный набросок"}}}};
  storeDraft(storage,1,"audit",draft);
  const restored=loadDraft(storage,1,"audit");
  assert.equal(restored.status,"completed");
  assert.equal(restored.revision,8);
  assert.equal(restored.observation_scratch.raw.event.comment,"Локальный набросок");
});
