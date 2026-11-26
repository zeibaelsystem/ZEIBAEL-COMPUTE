import json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class Stage3Contract(unittest.TestCase):
    def test_ledger_and_manifests(self):
        ledger=json.loads((ROOT/"ci/stage3_candidates.json").read_text())
        candidates=ledger["candidates"]
        ids=[c["id"] for c in candidates]
        self.assertEqual(len(ids),90)
        self.assertEqual(len(set(ids)),90)
        verified={c["id"] for c in candidates if c["status"]=="verified"}
        self.assertEqual(len(verified),ledger["verified_count"])
        self.assertEqual(90-len(verified),ledger["blocked_count"])
        batch=[]
        for p in sorted((ROOT/"ci/jobs").glob("stage3_batch_*.json")):
            jobs=json.loads(p.read_text())["jobs"]
            self.assertLessEqual(len(jobs),18)
            batch.extend(j["id"] for j in jobs)
        self.assertEqual(len(batch),len(set(batch)))
        self.assertEqual(set(batch),verified)
        for c in candidates:
            p=ROOT/"ci/jobs"/("engine_"+c["id"]+".json")
            if c["id"] in verified:
                self.assertTrue(p.exists(),c["id"])
                self.assertEqual(c["evidence"]["manifest_step"],"success")
                self.assertEqual(c["evidence"]["artifact_step"],"success")
            else:
                self.assertEqual(c["status"],"blocked")
                self.assertFalse(p.exists(),c["id"])
