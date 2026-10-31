import unittest
from types import SimpleNamespace
from scripts.public_media_transcribe import serialize_transcript

class FreeASRTests(unittest.TestCase):
    def test_realistic_segment_text_and_provenance(self):
        segments = [SimpleNamespace(start=0, end=1.5, text="Halo, Claude."),
                    SimpleNamespace(start=1.5, end=3.0, text=" gratis")]
        info = SimpleNamespace(language="id", language_probability=0.91)
        result = serialize_transcript(segments, info)
        self.assertEqual(result["status"], "transcribed")
        self.assertEqual(result["text"], "Halo, Claude. gratis")
        self.assertEqual(result["language"], "id")
        self.assertEqual(len(result["segments"]), 2)

    def test_no_speech_is_not_claimed_as_transcribed(self):
        info = SimpleNamespace(language="id", language_probability=0.2)
        result = serialize_transcript([], info)
        self.assertEqual(result["status"], "no_recognized_speech")
        self.assertEqual(result["text"], "")
