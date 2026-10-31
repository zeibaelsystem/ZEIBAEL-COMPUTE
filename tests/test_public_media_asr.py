import unittest
from types import SimpleNamespace
from scripts.public_media_transcribe import serialize_transcript, transcribe_with_fallback, read_pcm16_mono

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

class ASRRetryTests(unittest.TestCase):
    def test_vad_typeerror_retries_without_vad(self):
        class Fake:
            calls=[]
            def transcribe(self, source, **kwargs):
                self.calls.append(kwargs)
                if kwargs.get('vad_filter'):
                    raise TypeError('VAD input incompatible')
                return ['segments'], 'info'
        fake=Fake()
        result=transcribe_with_fallback(fake,'speech.wav')
        self.assertEqual(result[0],['segments'])
        self.assertEqual(result[1],'info')
        self.assertTrue(result[2])
        self.assertEqual(len(fake.calls),2)
        self.assertEqual(fake.calls[1]['language'],'id')
        self.assertFalse(fake.calls[1]['vad_filter'])

    def test_normal_mode_does_not_retry(self):
        class Fake:
            calls=0
            def transcribe(self, source, **kwargs):
                self.calls+=1
                return [],'info'
        fake=Fake()
        self.assertEqual(transcribe_with_fallback(fake,'speech.wav'),([], 'info', False))
        self.assertEqual(fake.calls,1)

class ASRPCMTests(unittest.TestCase):
    def test_stdlib_wave_decode_avoids_av_demux(self):
        import wave
        import tempfile
        from pathlib import Path
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"speech.wav"
            with wave.open(str(f),"wb") as out:
                out.setnchannels(1)
                out.setframerate(16000)
                out.setsampwidth(2)
                out.writeframes(b"\x00\x40" * 16000)
            x=read_pcm16_mono(f)
            self.assertEqual(x.dtype,np.float32)
            self.assertEqual(x.shape,(16000,))
            self.assertAlmostEqual(float(x[0]),0.5)

    def test_reject_bad_pcm_without_network(self):
        import wave
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"bad.wav"
            with wave.open(str(f),"wb") as out:
                out.setnchannels(2)
                out.setframerate(44100)
                out.setsampwidth(2)
                out.writeframes(b"\x00" * 100)
            with self.assertRaises(ValueError):
                read_pcm16_mono(f)
