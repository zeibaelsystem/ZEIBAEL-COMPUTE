"""Bounded acquisition from loopback-only protocol test services.

These adapters deliberately reject remote services and are not production OT
clients. No write, wildcard topic, discovery scan, or public dispatch route.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import queue
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

MAX_BYTES=65536
MAX_RECORDS=100

def _count(count):
    if type(count) is not int or not 1<=count<=MAX_RECORDS:
        raise ValueError("Invalid stream count")

def _local(endpoint,scheme):
    p=urlsplit(endpoint)
    if (p.scheme!=scheme or p.hostname!="127.0.0.1" or p.port is None
        or p.username is not None or p.password is not None or p.query or p.fragment):
        raise ValueError("Only explicit loopback fixture endpoint is permitted")

def _record(source,data):
    raw=json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
    if len(raw)>MAX_BYTES:raise ValueError("Record limit")
    return {"source":source,"data":data,"sha256":hashlib.sha256(raw).hexdigest(),
            "collected_at":datetime.now(timezone.utc).isoformat()}

def _decode(raw):
    if isinstance(raw,str):raw=raw.encode("utf-8")
    if not isinstance(raw,bytes) or not 1<=len(raw)<=MAX_BYTES:
        raise ValueError("Message byte limit")
    data=json.loads(raw)
    if not isinstance(data,dict):raise ValueError("Expected JSON object")
    return data

async def websocket_records(endpoint,*,count):
    _local(endpoint,"ws")
    _count(count)
    from websockets.asyncio.client import connect
    async def collect():
        records=[]
        async with connect(endpoint,proxy=None,max_size=MAX_BYTES,open_timeout=5,close_timeout=1) as ws:
            for _ in range(count):
                records.append(_record(endpoint,_decode(await ws.recv())))
        return records
    return await asyncio.wait_for(collect(),timeout=15)

async def opcua_read(endpoint,node_ids):
    _local(endpoint,"opc.tcp")
    if not isinstance(node_ids,(list,tuple)):raise ValueError("Explicit node list required")
    _count(len(node_ids))
    if not all(isinstance(n,str) and re.fullmatch(r"ns=[0-9]{1,5};i=[0-9]{1,10}",n) for n in node_ids):
        raise ValueError("Expected explicit numeric fixture nodes")
    from asyncua import Client
    async def collect():
        records=[]
        async with Client(endpoint,timeout=5) as client:
            for n in node_ids:
                value=await client.get_node(n).read_value()
                records.append(_record(endpoint+"#"+n,value))
        return records
    return await asyncio.wait_for(collect(),timeout=15)

def mqtt_records(host,port,topic,*,count):
    if (host!="127.0.0.1" or type(port) is not int or not 1<=port<=65535
        or not isinstance(topic,str) or not re.fullmatch(r"[A-Za-z0-9_/-]{1,128}",topic)):
        raise ValueError("Explicit local host and non-wildcard topic required")
    _count(count)
    import paho.mqtt.client as mqtt
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    messages=queue.Queue(maxsize=count)
    errors=queue.Queue(maxsize=1)
    def fail(reason):
        try:errors.put_nowait(reason)
        except queue.Full:pass
    def connected(c,u,flags,reason,props):
        if reason!=0:fail("Local broker refused connection")
        else:
            rc,_=c.subscribe(topic,qos=1)
            if rc!=mqtt.MQTT_ERR_SUCCESS:fail("Subscribe failed")
    def received(c,u,msg):
        try:
            if msg.topic!=topic:raise ValueError("Unexpected topic")
            rec=_record("mqtt://"+host+":"+str(port)+"/"+topic,_decode(msg.payload))
            try:messages.put_nowait(rec)
            except queue.Full:pass
        except Exception:
            fail("Invalid message")
    client.on_connect=connected
    client.on_message=received
    client.connect(host,port,keepalive=10)
    client.loop_start()
    records=[]
    deadline=time.monotonic()+10
    try:
        while len(records)<count:
            if not errors.empty():raise ValueError(errors.get_nowait())
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError("Local stream timeout")
            try:records.append(messages.get(timeout=min(remaining,.2)))
            except queue.Empty:pass
        return records
    finally:
        client.disconnect()
        client.loop_stop()
