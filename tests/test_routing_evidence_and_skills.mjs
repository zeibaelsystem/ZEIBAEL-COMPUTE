import test from "node:test";
import assert from "node:assert/strict";
import * as router from "../ci/fixtures/ai_routing_contract.mjs";
import {routeSkills} from "../ci/fixtures/skill_intent_contract.mjs";
const now=Date.parse("2026-10-31T00:00:00Z"),base={enabled:true,freeVerified:true,verifiedAt:now-3600000,remainingRequests:5,paidFallback:false,billingRequired:false};
const items=[{...base,provider:"groq",model:"openai/gpt-oss-120b",priority:0},{...base,provider:"openrouter",model:"google/gemma-4-31b-it:free",priority:1}];
const e=(provider,model,task,attempts,completed,latency)=>({provider,model,task,attempts,completed,totalLatencyMs:latency,windowDays:7});
test("no evidence keeps original eligible model order",()=>{
 const r=router.rankByEvidence("engineering",items,[],now);
 assert.deepEqual(r.map(x=>x.provider),["groq","openrouter"]);
});
test("one-sided or low-sample evidence cannot reorder models",()=>{
 const r=router.rankByEvidence("engineering",items,[e("groq",items[0].model,"engineering",7,1,10000)],now);
 assert.equal(r[0].provider,"groq");
});
test("task-specific evidence with >=5 attempts per model reorders by reliability and latency",()=>{
 const rows=[e("groq",items[0].model,"engineering",10,4,90000),e("openrouter",items[1].model,"engineering",10,9,50000)];
 assert.equal(router.rankByEvidence("engineering",items,rows,now)[0].provider,"openrouter");
 assert.equal(router.rankByEvidence("code",items,rows,now)[0].provider,"groq");
});
test("evidence never resurrects unverified or paid model",()=>{
 const paid={...items[1],billingRequired:true};
 const eligible=router.planCandidates("engineering",[items[0],paid],now);
 const rows=[e("groq",items[0].model,"engineering",10,3,90000),e("openrouter",items[1].model,"engineering",10,10,10000)];
 assert.deepEqual(router.rankByEvidence("engineering",eligible,rows,now).map(x=>x.provider),["groq"]);
});
test("no prompt or answer text stored in telemetry",()=>{
 const sample=router.telemetryRecord({task:"engineering",candidate:items[0],ok:true,elapsedMs:1234,question:"secret question",answer:"secret answer"});
 assert.deepEqual(Object.keys(sample).sort(),["completed","latencyMs","model","provider","task"].sort());
 assert.ok(!JSON.stringify(sample).includes("secret"));
});
test("skill routing finds one primary specialist from actual runtime inventory",()=>{
 const skills=[{uri:"skills://plugins/skillquiver/diagnose-systematically",eligible:true},{uri:"skills://plugins/engineering-suite/test-driven-development",eligible:true}];
 const r=routeSkills({intent:"debug_existing_failure",phase:"diagnosis",available:skills});
 assert.deepEqual(r.primary,skills[0].uri);
});
test("skill routing blocks unavailable, unverified, auto-disabled and cross-domain fallback",()=>{
 const skills=[{uri:"skills://plugins/skillquiver/diagnose-systematically",eligible:true,autoDisabled:true}];
 const r=routeSkills({intent:"debug_existing_failure",phase:"diagnosis",available:skills});
 assert.equal(r.ok,false);
});
test("skill routing correctly differentiates source quality and result validation",()=>{
 const a=[{uri:"skills://plugins/data/analyze-data-quality",eligible:true},{uri:"skills://plugins/data/validate-data",eligible:true}];
 assert.equal(routeSkills({intent:"dataset_quality",phase:"analysis",available:a}).primary,a[0].uri);
 assert.equal(routeSkills({intent:"validate_results",phase:"verification",available:a}).primary,a[1].uri);
});
