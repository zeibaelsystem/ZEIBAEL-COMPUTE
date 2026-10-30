// Public deterministic test reference. No inference, secrets, external APIs, or dispatcher.
// Supabase's existing SQL RPCs remain the production implementation.
const TASKS = new Set(["engineering","code","quick","reasoning_crosscheck","safety_policy","prompt_guard","prompt_guard_thorough","deep_analysis","deep_code","document_text","general","translation","extraction","simple_summary","alternative","bugfix","agent_plan","alternative_multimodal_reasoning","structured_document","lightweight_check","rapid_reasoning","long_context_fast","code_agent","long_context","fast_code_revision","terminal_code","content_safety","complex_alternative","multimodal_perception_review","multilingual_fast","multilingual_thorough"]);
const GROQ = new Set(["openai/gpt-oss-120b","openai/gpt-oss-20b","qwen/qwen3.8-27b","openai/gpt-oss-safeguard-20b","meta-llama/llama-prompt-guard-2-22m","meta-llama/llama-prompt-guard-2-86m"]);
const DAY=86400000;
export function planCandidates(taskType, candidates=[], now=Date.now()){
 if(!TASKS.has(taskType)||!Array.isArray(candidates)||!Number.isFinite(now))return [];
 return candidates.filter(c=>c&&c.enabled===true&&c.freeVerified===true&&
  c.paidFallback===false&&c.billingRequired===false&&
  Number.isFinite(c.verifiedAt)&&c.verifiedAt<=now&&now-c.verifiedAt<=DAY&&
  Number.isFinite(c.remainingRequests)&&c.remainingRequests>0&&
  ((c.provider==="groq"&&GROQ.has(c.model))||
   (c.provider==="openrouter"&&typeof c.model==="string"&&c.model.endsWith(":free"))))
  .sort((a,b)=>(a.priority??100)-(b.priority??100))
  .filter((c,i,arr)=>arr.findIndex(x=>x.provider===c.provider&&x.model===c.model)===i);
}
export function validateOutput(output,candidate){
 if(output?.ok!==true)return {ok:false,code:"PROVIDER_FAILED"};
 if(output.model!==candidate.model)return {ok:false,code:"UNEXPECTED_MODEL"};
 if(["content_filter","SAFETY","PROHIBITED_CONTENT","SPII"].includes(output.finish_reason))
  return {ok:false,code:"OUTPUT_SAFETY_BLOCKED",stopFallback:true};
 if(["length","MAX_TOKENS","max_tokens"].includes(output.finish_reason))
  return {ok:false,code:"INCOMPLETE_OUTPUT"};
 if(!["stop","STOP"].includes(output.finish_reason))
  return {ok:false,code:"COMPLETION_NOT_PROVEN"};
 if(typeof output.text!=="string"||!output.text.trim())return {ok:false,code:"EMPTY_OUTPUT"};
 if(output.text.length>7000)return {ok:false,code:"OUTPUT_TOO_LONG"};
 return {ok:true,code:"COMPLETE",answer:output.text};
}
export async function routeWithFallback({taskType,classification,question,candidates=[],now=Date.now(),invoke}={}){
 const receipts=[];
 const fail=code=>({ok:false,code,receipts,paidFallback:false,inferenceExecuted:receipts.some(r=>r.outcome==="FAILED")});
 if(classification!=="public_approved")return fail("DATA_NOT_APPROVED");
 if(typeof question!=="string"||question.trim().length<5||question.length>4000)return fail("QUESTION_LENGTH_INVALID");
 if(typeof invoke!=="function")return fail("INVOKER_MISSING");
 const planned=planCandidates(taskType,candidates,now).slice(0,3);
 if(!planned.length)return fail("NO_VERIFIED_FREE_CANDIDATES");
 for(const c of planned){
  let response;try{response=await invoke(c,question);}
  catch{receipts.push({provider:c.provider,model:c.model,outcome:"FAILED",reason:"PROVIDER_FAILED"});continue;}
  const q=validateOutput(response,c);
  receipts.push({provider:c.provider,model:c.model,outcome:q.ok?"SUCCEEDED":"FAILED",reason:q.code});
  if(q.ok)return {ok:true,provider:c.provider,model:c.model,answer:q.answer,receipts,paidFallback:false,inferenceExecuted:true,complete:true};
  if(q.stopFallback)return fail(q.code);
 }
 return fail("NO_COMPLETE_VERIFIED_FREE_RESPONSE");
}

/** Evidence is reliability/latency (not factual correctness), aggregated per task; never overrides FREE-ONLY. */
export function rankByEvidence(task,candidates=[],records=[],now=Date.now()){
 if(!Array.isArray(candidates)||!Array.isArray(records))return candidates;
 const supported=planCandidates(task,candidates,now);
 if(supported.length<2)return supported;
 const aggregated=supported.map(c=>{
  const eligible=records.filter(r=>r.task===task&&r.provider===c.provider&&r.model===c.model&&r.windowDays<=7);
  return eligible.reduce((acc,r)=>({attempts:acc.attempts+Math.max(0,Number(r.attempts)||0),completed:acc.completed+Math.max(0,Number(r.completed)||0),totalLatencyMs:acc.totalLatencyMs+Math.max(0,Number(r.totalLatencyMs)||0)}),{attempts:0,completed:0,totalLatencyMs:0});
 });
 if(aggregated.some(r=>r.attempts<5))return supported;
 const score=r=>(r.completed/r.attempts)*100-Math.min(r.totalLatencyMs/r.attempts/1000,20);
 return supported.map((c,i)=>({c,i,score:score(aggregated[i])})).sort((a,b)=>b.score-a.score||a.i-b.i).map(x=>x.c);
}
export function telemetryRecord({task,candidate,ok,elapsedMs}){
 return {task,provider:candidate.provider,model:candidate.model,completed:ok===true,latencyMs:Math.max(0,Math.round(Number(elapsedMs)||0))};
}
