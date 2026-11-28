"""Offline-safe disjoint-origin sharding and exact coverage aggregation.

This is a finite reviewed-batch primitive, not a distributed live queue.
Cross-shard link discovery is deliberately not supported. Workers must obey
the existing source, robots and rate policy. Hash metadata is not a substitute
for trusting the worker or verifying returned content.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from scripts.acquisition_core import canonical_url

MAX_URLS=100_000
MAX_SHARDS=8
MAX_HOSTS=20

def plan_shards(urls,hosts,workers):
    hosts=frozenset(hosts)
    if not 1<=len(hosts)<=MAX_HOSTS or type(workers) is not int or not 1<=workers<=MAX_SHARDS:
        raise ValueError("Invalid shard bounds")
    by_host={h:set() for h in hosts}
    for h in hosts:
        canonical_url("https://"+h+"/",hosts)
    for index,raw in enumerate(urls):
        if index>=MAX_URLS:raise ValueError("Seed capacity")
        url=canonical_url(raw,hosts)
        by_host[urlsplit(url).hostname].add(url)
    active=sorted((h for h in hosts if by_host[h]),key=lambda h:(-len(by_host[h]),h))
    if not active:raise ValueError("No seeds")
    plan=[{"id":i,"hosts":[],"urls":[]} for i in range(min(workers,len(active)))]
    for h in active:
        shard=min(plan,key=lambda x:(len(x["urls"]),x["id"]))
        shard["hosts"].append(h)
        shard["urls"].extend(sorted(by_host[h]))
    for s in plan:
        s["hosts"].sort()
        s["urls"].sort()
    return plan

def aggregate(plan,outputs):
    if not 1<=len(plan)<=MAX_SHARDS or len(outputs)!=len(plan):
        raise ValueError("Incomplete shard collection")
    expected={s["id"]:set(s["urls"]) for s in plan}
    if len(expected)!=len(plan) or sum(len(s["urls"]) for s in plan)>MAX_URLS:
        raise ValueError("Invalid plan")
    all_expected=set().union(*expected.values())
    if sum(map(len,expected.values()))!=len(all_expected):
        raise ValueError("Overlapping shard URLs")
    ids=set()
    hashes=set()
    failed=0
    for output in outputs:
        sid=output["id"]
        if sid in ids or sid not in expected:raise ValueError("Unexpected shard ID")
        ids.add(sid)
        seen=set()
        for record in output["records"]:
            url=record["url"]
            if url in seen or url not in expected[sid]:
                raise ValueError("Duplicate or unexpected URL")
            seen.add(url)
            if record["status"]=="ok":
                digest=record.get("sha256")
                if not isinstance(digest,str) or not re.fullmatch(r"[a-f0-9]{64}",digest):
                    raise ValueError("Invalid content hash")
                hashes.add(digest)
            else:failed+=1
        if seen!=expected[sid]:raise ValueError("Missing shard records")
    return {"shards":len(ids),"records":len(all_expected),"failed":failed,
            "unique_content":len(hashes),"complete":failed==0}
