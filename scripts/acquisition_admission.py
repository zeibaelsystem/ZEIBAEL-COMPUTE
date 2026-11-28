"""Fail-closed policy helper for the existing Compute acquisition manifests.

No execution or dispatcher. Authorization and free entitlement must come
from reviewed evidence supplied by GPT, not from arbitrary source content.
"""
REVIEWED_JOBS=frozenset({"acquisition_owned_public","acquisition_archive_example"})
FIELDS=frozenset({"purpose","sensitivity","source_access","free_entitlement","job_id","parameters"})

def admit_compute(request):
    if not isinstance(request,dict) or set(request)!=FIELDS:
        return {"decision":"STOP","reason":"invalid_request"}
    if request["purpose"]!="development_test" or request["sensitivity"]!="public_safe":
        return {"decision":"STOP","reason":"scope_not_admitted"}
    if request["source_access"]!="allowed":
        return {"decision":"STOP","reason":"source_not_admitted"}
    if request["free_entitlement"]!="verified":
        return {"decision":"STOP","reason":"free_entitlement_not_verified"}
    if not isinstance(request["job_id"],str) or request["job_id"] not in REVIEWED_JOBS:
        return {"decision":"STOP","reason":"unreviewed_manifest"}
    if not isinstance(request["parameters"],dict) or request["parameters"]:
        return {"decision":"STOP","reason":"runtime_parameters_not_admitted"}
    return {"decision":"ADMIT","job_id":request["job_id"],"scope":"fixed_public_development_fixture"}

def fallback_policy(reason):
    if reason=="technical_failure":
        return "RECHECK_ELIGIBLE_ALTERNATIVE"
    return "STOP"
