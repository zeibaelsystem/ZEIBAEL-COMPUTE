"""Contracts for bounded, disjoint-origin acquisition shards."""
import hashlib
import importlib.util
import unittest

class Shards(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_shards"),"shard module missing")
        from scripts import acquisition_shards
        self.a=acquisition_shards
        self.urls=["https://a.example.org/1","https://b.example.org/2",
                   "https://a.example.org/3","https://c.example.org/4"]

    def test_partition_keeps_origin_on_one_worker(self):
        plan=self.a.plan_shards(self.urls+["https://a.example.org/1#dup"],
                              {"a.example.org","b.example.org","c.example.org"},2)
        self.assertEqual(sum(len(s["urls"]) for s in plan),4)
        self.assertFalse(set(plan[0]["hosts"]) & set(plan[1]["hosts"]))
        self.assertEqual(plan,self.a.plan_shards(list(reversed(self.urls)),
                              {"a.example.org","b.example.org","c.example.org"},2))

    def test_reject_unapproved_origin_and_query(self):
        for url in ["https://other.example.org/","https://a.example.org/?token=1"]:
            with self.assertRaises(ValueError):
                self.a.plan_shards([url],{"a.example.org"},1)

    def test_aggregate_accepts_complete_and_exact_hash(self):
        plan=self.a.plan_shards(self.urls,{"a.example.org","b.example.org","c.example.org"},2)
        outputs=[{"id":s["id"],"records":[{"url":u,"status":"ok",
                  "sha256":hashlib.sha256(u.encode()).hexdigest()} for u in s["urls"]]} for s in plan]
        report=self.a.aggregate(plan,outputs)
        self.assertEqual(report["records"],4)
        self.assertEqual(report["unique_content"],4)
        self.assertTrue(report["complete"])
        with self.assertRaises(ValueError):self.a.aggregate(plan,outputs[:1])
        with self.assertRaises(ValueError):self.a.aggregate(plan,outputs+[outputs[0]])
        outputs[0]["records"].append(outputs[0]["records"][0])
        with self.assertRaises(ValueError):self.a.aggregate(plan,outputs)

    def test_content_duplicate_across_shards(self):
        plan=self.a.plan_shards(self.urls,{"a.example.org","b.example.org","c.example.org"},2)
        outputs=[{"id":s["id"],"records":[{"url":u,"status":"ok","sha256":"a"*64}
                  for u in s["urls"]]} for s in plan]
        report=self.a.aggregate(plan,outputs)
        self.assertEqual(report["records"],4)
        self.assertEqual(report["unique_content"],1)

    def test_rate_stop_is_not_success(self):
        plan=self.a.plan_shards(self.urls,{"a.example.org","b.example.org","c.example.org"},2)
        outputs=[{"id":s["id"],"records":[{"url":u,"status":"rate_limited"} for u in s["urls"]]} for s in plan]
        report=self.a.aggregate(plan,outputs)
        self.assertFalse(report["complete"])
        self.assertEqual(report["failed"],4)

if __name__=="__main__": unittest.main()
