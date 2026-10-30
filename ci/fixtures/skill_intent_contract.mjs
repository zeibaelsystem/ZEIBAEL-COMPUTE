// Public, deterministic contract fixture only. Real GPT skill selection occurs at runtime.
const ROUTES={
 "debug_existing_failure":{phase:"diagnosis",uri:"skills://plugins/skillquiver/diagnose-systematically"},
 "dataset_quality":{phase:"analysis",uri:"skills://plugins/data/analyze-data-quality"},
 "validate_results":{phase:"verification",uri:"skills://plugins/data/validate-data"},
 "implement_behavior":{phase:"implementation",uri:"skills://plugins/skillquiver/test-driven-development"},
 "verify_completed_claim":{phase:"verification",uri:"skills://plugins/skillquiver/verify-work"}
};
export function routeSkills({intent,phase,available=[]}={}){
 const rule=ROUTES[intent];
 if(!rule||rule.phase!==phase)return {ok:false,primary:null,code:"UNMAPPED_INTENT"};
 const entry=available.find(s=>s.uri===rule.uri);
 if(!entry||entry.eligible!==true||entry.autoDisabled===true)return {ok:false,primary:null,code:"SKILL_UNAVAILABLE"};
 return {ok:true,primary:entry.uri,code:"SOURCE_READ_REQUIRED"};
}
