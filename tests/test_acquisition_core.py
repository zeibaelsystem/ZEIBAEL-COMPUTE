"""Offline acquisition contracts; no live requests or customer data."""
import importlib.util
import json
import unittest

class TestAcquisitionCore(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("scripts.acquisition_core")
        self.assertIsNotNone(spec, "acquisition core is not implemented")
        from scripts import acquisition_core
        self.core = acquisition_core

    def test_url_policy(self):
        url = self.core.canonical_url
        hosts = {"example.org"}
        self.assertEqual(url("https://EXAMPLE.org/a#part", hosts), "https://example.org/a")
        self.assertEqual(url("https://example.org/a?page=2", hosts, {"page"}), "https://example.org/a?page=2")
        for candidate in ("http://example.org", "https://example.org@other.org",
                          "https://other.org", "https://127.0.0.1",
                          "https://example.org:444", "https://example.org/?token=secret",
                          "https://example.org/?%74oken=secret", "https://example.org/\\bad"):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                url(candidate, hosts, {"page", "token"})

    def test_offline_formats(self):
        parse = self.core.parse_document
        html = parse(b'<title>Example</title><script>IGNORE</script><p>hello</p><a href="/next">next</a>',
                     "text/html", "https://example.org/")
        self.assertEqual(html["title"], "Example")
        self.assertIn("hello", html["text"])
        self.assertNotIn("IGNORE", html["text"])
        self.assertEqual(html["links"], ["https://example.org/next"])
        self.assertEqual(parse(b'{"price":12}', "application/json", "")["data"], {"price":12})
        self.assertEqual(parse(b'name,value\nA,12\n', "text/csv", "")["rows"], [["name","value"],["A","12"]])
        self.assertEqual(parse(b'<urlset><url><loc>https://example.org/a</loc></url></urlset>',
                               "application/xml", "")["links"], ["https://example.org/a"])
        with self.assertRaises(ValueError):
            parse(b'<!DOCTYPE a [<!ENTITY x "abc">]><a>&x;</a>', "application/xml", "")
        with self.assertRaises(ValueError):
            parse(b'%PDF', "application/pdf", "")

    def test_bounded_crawl_and_robots(self):
        R = self.core.Response
        requested = []
        pages = {
            "https://example.org/robots.txt": R(200, "text/plain", b"User-agent: *\nDisallow: /blocked\n"),
            "https://example.org/": R(200, "text/html", b'<a href="/a">a</a><a href="/a">again</a><a href="/blocked">b</a><a href="https://other.org/">offsite</a>'),
            "https://example.org/a": R(200, "text/html", b'<a href="/">home</a><a href="/deep">deep</a>'),
        }
        def fetch(url, limit):
            requested.append(url)
            return pages[url]
        report = self.core.crawl(["https://example.org/"], {"example.org"}, fetch,
                                 max_pages=10, max_depth=1, sleep=lambda _: None)
        self.assertEqual(requested, ["https://example.org/robots.txt", "https://example.org/", "https://example.org/a"])
        self.assertEqual([r["status"] for r in report["records"]], ["ok","ok","denied"])
        self.assertEqual(len(report["records"][0]["sha256"]), 64)
        self.assertEqual(report["pending"], [])

    def test_rate_limit_stops_origin(self):
        R = self.core.Response
        requested = []
        def fetch(url, limit):
            requested.append(url)
            if url.endswith("/robots.txt"):
                return R(404, "text/plain", b"")
            return R(429, "text/plain", b"", "120")
        report = self.core.crawl(["https://example.org/a","https://example.org/b"], {"example.org"}, fetch,
                                 max_pages=5, sleep=lambda _: None)
        self.assertEqual(requested, ["https://example.org/robots.txt","https://example.org/a"])
        self.assertEqual([r["status"] for r in report["records"]], ["rate_limited","origin_stopped"])
        self.assertEqual(report["records"][0]["retry_after"], "120")

    def test_robots_unavailable_fails_closed(self):
        R = self.core.Response
        requested = []
        def fetch(url, limit):
            requested.append(url)
            return R(503, "text/plain", b"")
        report = self.core.crawl(["https://example.org/"], {"example.org"}, fetch, sleep=lambda _: None)
        self.assertEqual(requested, ["https://example.org/robots.txt"])
        self.assertEqual(report["records"][0]["status"], "robots_unavailable")

    def test_size_and_budget(self):
        R = self.core.Response
        def fetch(url, limit):
            if url.endswith("/robots.txt"):
                return R(404, "text/plain", b"")
            return R(200, "text/plain", b"123456")
        report = self.core.crawl(["https://example.org/a","https://example.org/b"], {"example.org"}, fetch,
                                 max_pages=1, max_bytes=5, sleep=lambda _: None)
        self.assertEqual(report["records"][0]["status"], "too_large")
        self.assertEqual(report["pending"], [{"url":"https://example.org/b","depth":0}])

    def test_dns_and_redirect_policy(self):
        self.assertFalse(self.core.is_public_address("127.0.0.1"))
        self.assertFalse(self.core.is_public_address("169.254.169.254"))
        self.assertFalse(self.core.is_public_address("::1"))
        self.assertFalse(self.core.is_public_address("::ffff:10.0.0.1"))
        self.assertTrue(self.core.is_public_address("8.8.8.8"))
        R = self.core.Response
        def fetch(url, limit):
            if url.endswith("/robots.txt"):
                return R(404, "text/plain", b"")
            return R(302, "text/html", b"")
        report = self.core.crawl(["https://example.org/"], {"example.org"}, fetch, sleep=lambda _: None)
        self.assertEqual(report["records"][0]["status"], "redirect_not_followed")

if __name__ == "__main__":
    unittest.main()
