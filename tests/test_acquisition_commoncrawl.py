"""Common Crawl range policy and archive fixture tests."""
import importlib.util
import unittest

ENTRY={"url":"https://example.com/","timestamp":"20261005112841","status":"200",
       "filename":"crawl-data/CC-MAIN-2026-43/segments/1791170053823.21/warc/CC-MAIN-20261005105623-20261005135623-00162.warc.gz",
       "offset":"204233603","length":"996"}

class ArchiveRangeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_commoncrawl"),"archive range module missing")
        from scripts import acquisition_commoncrawl
        self.a=acquisition_commoncrawl

    def test_exact_range(self):
        locator=self.a.validate_entry(ENTRY)
        self.assertEqual(locator["range"],"bytes=204233603-204234598")
        self.assertEqual(locator["host"],"data.commoncrawl.org")
        self.assertEqual(locator["length"],996)

    def test_invalid_path_and_limits(self):
        for patch in [{"filename":"https://other.example/file"},{"filename":"crawl-data/../../secret"},
                      {"offset":"-1"},{"length":"99999999"},{"length":"0"},{"status":"403"}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                self.a.validate_entry({**ENTRY,**patch})

    def test_require_exact_206(self):
        locator=self.a.validate_entry(ENTRY)
        body=b"x"*996
        self.assertEqual(self.a.check_range(locator,206,"bytes 204233603-204234598/999999999",body),body)
        for status,header,payload in [(200,"",body),(206,"bytes 0-995/10000",body),(206,"bytes 204233603-204234598/999999999",body[:-1])]:
            with self.subTest(status=status,header=header),self.assertRaises(ValueError):
                self.a.check_range(locator,status,header,payload)

if __name__=="__main__":unittest.main(verbosity=2)
