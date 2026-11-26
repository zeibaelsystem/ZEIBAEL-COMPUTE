import unittest, tempfile, json
from pathlib import Path
from scripts.workflow_dag import plan, execute, compare, read_checkpoint

class DagContract(unittest.TestCase):
    def test_order_and_cycle(self):
        self.assertEqual(plan({"b":["a"],"a":[]}), [["a"],["b"]])
        with self.assertRaises(ValueError): plan({"a":["b"],"b":["a"]})
        with self.assertRaises(ValueError): plan({"a":["missing"]})
    def test_reject_unsafe_and_large(self):
        with self.assertRaises(ValueError): plan({"../a":[]})
        with self.assertRaises(ValueError): plan({str(i):[] for i in range(21)})
    def test_compare(self):
        self.assertTrue(compare(1,1.000001,1e-5))
        self.assertFalse(compare(1,2,1e-5))
        self.assertFalse(compare(float("nan"),1,1e-5))
    def test_chain_checkpoint_and_invalidation(self):
        graph={"a":[],"b":["a"]}
        calls=[]
        def a(_): calls.append("a"); return {"x":2}
        def b(d): calls.append("b"); return {"x":d["a"]["x"]*3}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            r=execute(graph,{"a":a,"b":b},path,"fixture-v1",max_workers=2)
            self.assertEqual(r["results"]["b"],{"x":6})
            self.assertEqual(calls,["a","b"])
            r=execute(graph,{"a":a,"b":b},path,"fixture-v1",max_workers=2)
            self.assertEqual(calls,["a","b"])
            self.assertEqual(r["cached"],["a","b"])
            execute(graph,{"a":a,"b":b},path,"fixture-v2",max_workers=2)
            self.assertEqual(calls,["a","b","a","b"])
    def test_failure_stops_downstream(self):
        def fail(_): raise RuntimeError("fixture failure")
        def forbidden(_): self.fail("dependency failure executed downstream")
        with tempfile.TemporaryDirectory() as d:
            r=execute({"a":[],"b":["a"]},{"a":fail,"b":forbidden},Path(d),"fixture-v1",max_workers=1)
            self.assertEqual(r["status"],{"a":"failed","b":"blocked"})
    def test_tampered_checkpoint_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.json"; p.write_text('{"result":2}')
            self.assertIsNone(read_checkpoint(p,"expected"))
