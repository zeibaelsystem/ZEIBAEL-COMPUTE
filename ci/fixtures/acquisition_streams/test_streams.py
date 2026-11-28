"""Real protocol clients on fixed loopback-only synthetic services."""
import asyncio
import importlib.util
import json
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

class Streams(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_streams"),"stream module missing")
        from scripts import acquisition_streams
        self.a=acquisition_streams

    def test_websocket(self):
        from websockets.asyncio.server import serve
        async def handler(ws):
            for n in range(3):
                await ws.send(json.dumps({"seq":n,"value":n+10}))
        async def scenario():
            async with serve(handler,"127.0.0.1",18771):
                r=await self.a.websocket_records("ws://127.0.0.1:18771",count=3)
                self.assertEqual([x["data"]["seq"] for x in r],[0,1,2])
                self.assertTrue(all(len(x["sha256"])==64 for x in r))
        asyncio.run(scenario())

    def test_opcua_read_only(self):
        from asyncua import Server
        async def scenario():
            srv=Server()
            await srv.init()
            srv.set_endpoint("opc.tcp://127.0.0.1:18772/fixture/")
            idx=await srv.register_namespace("urn:zeibael:fixture")
            node=await srv.nodes.objects.add_variable(idx,"Temperature",21.5)
            async with srv:
                result=await self.a.opcua_read("opc.tcp://127.0.0.1:18772/fixture/",[node.nodeid.to_string()])
                self.assertEqual(result[0]["data"],21.5)
                self.assertEqual(await node.read_value(),21.5)
        asyncio.run(scenario())

    def test_mqtt(self):
        import paho.mqtt.client as mqtt
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"mosquitto.conf"
            path.write_text("listener 18773 127.0.0.1\nallow_anonymous true\npersistence false\n")
            p=subprocess.Popen(["mosquitto","-c",str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                deadline=time.monotonic()+5
                while True:
                    try:
                        with socket.create_connection(("127.0.0.1",18773),0.1):break
                    except OSError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.05)
                pub=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="fixture-publisher")
                pub.connect("127.0.0.1",18773)
                pub.loop_start()
                try:
                    message=pub.publish("zeibael/fixture",json.dumps({"value":42}),qos=1,retain=True)
                    message.wait_for_publish(timeout=5)
                    self.assertTrue(message.is_published())
                    records=self.a.mqtt_records("127.0.0.1",18773,"zeibael/fixture",count=1)
                    self.assertEqual(records[0]["data"],{"value":42})
                finally:
                    pub.disconnect()
                    pub.loop_stop()
            finally:
                p.terminate()
                p.wait(timeout=5)

    def test_remote_rejected(self):
        with self.assertRaises(ValueError):
            asyncio.run(self.a.websocket_records("ws://example.org/",count=1))
        with self.assertRaises(ValueError):
            asyncio.run(self.a.opcua_read("opc.tcp://example.org:4840/",["ns=2;i=1"]))
        with self.assertRaises(ValueError):
            self.a.mqtt_records("example.org",1883,"#",count=1)
        with self.assertRaises(ValueError):
            self.a.mqtt_records("127.0.0.1",18773,"#",count=1)

if __name__=="__main__":unittest.main(verbosity=2)
