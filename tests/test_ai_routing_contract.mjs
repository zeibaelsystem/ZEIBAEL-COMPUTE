import test from "node:test";
import assert from "node:assert/strict";
import {planCandidates,validateOutput,routeWithFallback} from "../ci/fixtures/ai_routing_contract.mjs";
const now=Date.parse("2026-10-31T00:00:00Z");
const entry=(provider,model,extra={})=>({provider,model,priority:10,freeVerified:true,enabled:true,verifiedAt:now-3600000,remainingRequests:5,paidFallback:false,billingRequired:false,...extra});
const groq=entry("groq","openai/gpt-oss-120b");
const gemma=entry("openrouter","google/gemma-4-31b-it:free",{priority:20});
test("selects multiple eligible candidates in priority order",()=>{
 assert.deepEqual(planCandidates("engineering",[gemma,groq],now).map(x=>x.provider),["groq","openrouter"]);
});
test("rejects expired policy, quota zero, billing and unverified candidates",()=>{
 const inputs=[groq,entry("x","expired",{verifiedAt:now-172800000}),entry("y","empty",{remainingRequests:0}),entry("z","paid",{billingRequired:true}),entry("w","unknown",{freeVerified:false})];
 assert.deepEqual(planCandidates("engineering",inputs,now).map(x=>x.provider),["groq"]);
});
test("does not accept unsupported task or an arbitrary provider",()=>{
 assert.deepEqual(planCandidates("unknown",[groq],now),[]);
 assert.deepEqual(planCandidates("engineering",[entry("random","model")],now),[]);
});
test("complete output requires exact model identity and stop reason",()=>{
 assert.equal(validateOutput({ok:true,model:groq.model,text:"answer",finish_reason:"stop"},groq).ok,true);
});
test("truncated output is rejected",()=>{
 assert.equal(validateOutput({ok:true,model:groq.model,text:"partial",finish_reason:"length"},groq).code,"INCOMPLETE_OUTPUT");
});
test("missing finish reason is rejected",()=>{
 assert.equal(validateOutput({ok:true,model:groq.model,text:"answer"},groq).code,"COMPLETION_NOT_PROVEN");
});
test("wrong model is rejected",()=>{
 assert.equal(validateOutput({ok:true,model:"paid-model",text:"answer",finish_reason:"stop"},groq).code,"UNEXPECTED_MODEL");
});
test("safety blocked response stops fallback",()=>{
 assert.equal(validateOutput({ok:true,model:groq.model,text:"blocked",finish_reason:"content_filter"},groq).stopFallback,true);
});
test("fallback executes a second free candidate after first error",async()=>{
 const called=[];const r=await routeWithFallback({taskType:"engineering",classification:"public_approved",question:"Explain the Python GIL briefly",candidates:[groq,gemma],now,invoke:async c=>{called.push(c.provider);return c.provider==="groq"?{ok:false,code:"RATE_LIMIT"}:{ok:true,model:gemma.model,text:"GIL explanation",finish_reason:"stop"};}});
 assert.equal(r.ok,true);assert.deepEqual(called,["groq","openrouter"]);assert.equal(r.paidFallback,false);
});
test("never calls provider if quota exhausted",async()=>{
 let count=0;const r=await routeWithFallback({taskType:"engineering",classification:"public_approved",question:"Explain the Python GIL briefly",candidates:[entry("groq",groq.model,{remainingRequests:0})],now,invoke:async()=>{count++;}});
 assert.equal(count,0);assert.equal(r.ok,false);
});
test("private inputs never execute inference",async()=>{
 let count=0;const r=await routeWithFallback({taskType:"engineering",classification:"private",question:"This contains restricted data",candidates:[groq],now,invoke:async()=>{count++;}});
 assert.equal(count,0);assert.equal(r.code,"DATA_NOT_APPROVED");
});
test("safety stop does not try a fallback",async()=>{
 let count=0;const r=await routeWithFallback({taskType:"engineering",classification:"public_approved",question:"Explain the Python GIL briefly",candidates:[groq,gemma],now,invoke:async()=>{count++;return {ok:true,model:groq.model,text:"blocked",finish_reason:"content_filter"};}});
 assert.equal(count,1);assert.equal(r.code,"OUTPUT_SAFETY_BLOCKED");
});
