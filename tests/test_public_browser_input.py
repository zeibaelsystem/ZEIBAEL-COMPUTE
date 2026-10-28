import json
import unittest
from scripts.public_browser_input import parse_public_browser_request, validated_browser_environment
class BrowserInputTests(unittest.TestCase):
    def test_public_steps(self):
        u,s=parse_public_browser_request("https://example.com/",'[{"action":"screenshot"}]')
        self.assertEqual(u,"https://example.com/")
        self.assertEqual(len(s),1)
    def test_private_and_sensitive_url_rejected(self):
        for u in ["http://example.com/","https://127.0.0.1","https://169.254.169.254",
                  "https://localhost","https://a.internal","https://a.local","https://example.com:9999",
                  "https://example.com?token=hi","https://example.com/#secret",
                  "https://user:pass@example.com","https://[::1]/"]:
            with self.subTest(u=u),self.assertRaises(ValueError): parse_public_browser_request(u,"[]")
    def test_actions_fail_closed(self):
        for s in [[{"action":"eval","js":"1+1"}],[{"action":"click","selector":"[type=password]"}],
                  [{"action":"fill","selector":"#name","value":"a@b.com"}],
                  [{"action":"screenshot"}]*9,[{"action":"goto","url":"https://example.com"}]]:
            with self.subTest(s=s),self.assertRaises(ValueError):
                parse_public_browser_request("https://example.com",json.dumps(s))
    def test_simple_interaction(self):
        _,s=parse_public_browser_request("https://example.com",json.dumps([
            {"action":"fill","selector":"#q","value":"public search"},
            {"action":"click","selector":"#find"},{"action":"text"}]))
        self.assertEqual(len(s),3)

    def test_browser_environment_is_bounded(self):
        raw={"ZEIBAEL_BROWSER_URL":"https://example.com/",
             "ZEIBAEL_BROWSER_STEPS":'[{"action":"text"}]',
             "UNRELATED_FIELD":"ignored"}
        result=validated_browser_environment("public_browser",raw)
        self.assertEqual(set(result),{"ZEIBAEL_BROWSER_URL","ZEIBAEL_BROWSER_STEPS"})
        self.assertEqual(validated_browser_environment("ordinary_job",raw),{})
        with self.assertRaises(ValueError):
            validated_browser_environment("public_browser",
                {"ZEIBAEL_BROWSER_URL":"http://127.0.0.1"})
