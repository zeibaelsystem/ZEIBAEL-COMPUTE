"""Synthetic, deterministic regression tests for public video evidence v2."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.public_video_intelligence import (
    MAX_FRAMES, make_evidence_v2, select_frame_seconds,
)
from scripts.public_video_timeline import transcribe_full, write_timeline
from scripts.public_media import capture, limited_command


class VideoSamplingTests(unittest.TestCase):
    def test_141_seconds_are_covered_without_first_42_seconds_bias(self):
        stamps = select_frame_seconds(141, [])
        self.assertEqual(stamps[0], 0.0)
        self.assertGreater(stamps[-1], 140.5)
        self.assertLessEqual(len(stamps), MAX_FRAMES)
        self.assertEqual(stamps, sorted(stamps))

    def test_scene_boundaries_are_included_when_capacity_allows(self):
        stamps = select_frame_seconds(
            30, [{"start": 10, "end": 13}, {"start": 24, "end": 27}])
        self.assertTrue(any(abs(v - 10.1) < 0.3 for v in stamps))
        self.assertTrue(any(abs(v - 25.5) < 0.3 for v in stamps))

    def test_one_or_zero_frame_limit_fails_closed(self):
        with self.assertRaises(ValueError):
            select_frame_seconds(90, [], limit=1)

    def test_long_video_reserves_scenes_even_with_dense_regular_samples(self):
        stamps = select_frame_seconds(
            300, [{"start": 123.0, "end": 125.0},
                  {"start": 253.0, "end": 255.0}])
        self.assertLessEqual(len(stamps), MAX_FRAMES)
        self.assertTrue(any(abs(v - 123.1) < 0.5 or abs(v - 124) < 0.5
                            for v in stamps))
        self.assertTrue(any(abs(v - 253.1) < 0.5 or abs(v - 254) < 0.5
                            for v in stamps))
        self.assertGreater(stamps[-1], 299)

    def test_real_141_second_media_uses_full_window_and_scene_package(self):
        if not shutil.which("ffmpeg") or not shutil.which("tesseract"):
            self.skipTest("video/OCR tools unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "clip.mp4"
            out = Path(tmp) / "out"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "testsrc=size=160x90:rate=1", "-f", "lavfi",
                            "-i", "sine=frequency=440:sample_rate=16000",
                            "-t", "141", "-c:v", "mpeg4", "-c:a", "aac",
                            str(src)], check=True, timeout=60)
            report = make_evidence_v2(src, out, limited_command, capture)
            self.assertEqual(report["scene_detection"], "completed")
            self.assertGreater(len(report["frame_records"]), 15)
            self.assertGreater(report["sampled_seconds"][-1], 139.0)
            self.assertEqual(report["coverage"]["audio_seconds_available"], 141)
            self.assertTrue((out / report["speech_full"]).is_file())
            self.assertLess(sum(p.stat().st_size for p in out.iterdir()), 12_000_000)

    def test_ocr_extracts_actual_on_screen_text(self):
        if not shutil.which("ffmpeg") or not shutil.which("tesseract"):
            self.skipTest("video/OCR tools unavailable")
        font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if not font.is_file():
            self.skipTest("test font not installed")
        from scripts.public_video_intelligence import extract_ocr
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "text.jpg"
            drawtext = ("drawtext=fontfile=%s:text=HELLO:"
                        "fontcolor=white:fontsize=90:x=(w-text_w)/2:y=(h-text_h)/2"
                        % font)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "color=c=black:s=640x160", "-vf", drawtext,
                            "-frames:v", "1", str(image)], check=True, timeout=20)
            txt, status = extract_ocr(image)
            self.assertEqual(status, "completed")
            self.assertIn("HELLO", txt.upper())

    def test_short_video_stream_and_longer_audio_are_reported_separately(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("video tools unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "audio_tail.mp4"
            out = Path(tmp) / "out"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "testsrc=size=160x90:rate=2:duration=4",
                            "-f", "lavfi",
                            "-i", "sine=frequency=440:sample_rate=16000:duration=7",
                            "-map", "0:v", "-map", "1:a",
                            "-c:v", "mpeg4", "-c:a", "aac",
                            str(src)], check=True, timeout=40)
            with patch("scripts.public_video_intelligence.extract_ocr",
                       return_value=("", "unavailable")):
                report = make_evidence_v2(src, out, limited_command, capture)
            c = report["coverage"]
            self.assertTrue(c["visual_track_shorter_than_media"])
            self.assertGreater(c["visual_gap_seconds"], 2)
            self.assertEqual(c["audio_seconds_available"], 7)
            self.assertFalse(c["visual_full_window_sampled"])
            self.assertLessEqual(report["sampled_seconds"][-1], c["visual_stream_end_seconds"])

    def test_media_frame_failure_does_not_shift_timestamps(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "synthetic.mp4"
            out = Path(tmp) / "frames"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "testsrc=size=160x90:rate=2", "-t", "13",
                            "-c:v", "mpeg4", str(src)], check=True, timeout=25)
            def fail_middle(command, timeout):
                if any("frame_01.jpg" in x for x in command):
                    return False
                return limited_command(command, timeout)
            with patch("scripts.public_video_intelligence.discover_scenes",
                       return_value=([], "completed")), patch(
                       "scripts.public_video_intelligence.extract_ocr",
                       return_value=("", "unavailable")):
                report = make_evidence_v2(src, out, fail_middle, capture)
            self.assertGreater(len(report["frames"]), 2)
            self.assertNotIn("frame_01.jpg", report["frames"])
            self.assertEqual(len(report["frames"]), len(report["sampled_seconds"]))
            self.assertEqual(len(report["frames"]), len(report["frame_records"]))
            for frame, sec in zip(report["frames"], report["sampled_seconds"]):
                self.assertEqual(next(r["seconds"] for r in report["frame_records"]
                                      if r["file"] == frame), sec)
            self.assertTrue(report["coverage"]["frames_failed"])


class FullAudioAndTimelineTests(unittest.TestCase):
    def test_audio_after_55_seconds_is_still_transcribed(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "full.opus"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "sine=frequency=440:sample_rate=16000",
                            "-t", "141", "-ac", "1", "-c:a", "libopus",
                            "-b:a", "24k", str(audio)], check=True, timeout=40)
            class Fake:
                def transcribe(self, samples, **kwargs):
                    return [SimpleNamespace(start=0.25, end=1.25,
                                            text="sample")], SimpleNamespace(
                                            language="id", language_probability=0.9)
            from scripts.public_media_transcribe import (
                serialize_transcript, transcribe_with_fallback, read_pcm16_mono)
            result = transcribe_full(Fake(), audio, 141,
                                     read_pcm16_mono, transcribe_with_fallback,
                                     serialize_transcript)
            self.assertEqual(result["status"], "transcribed")
            self.assertGreater(result["chunks_processed"], 3)
            self.assertTrue(any(x["start"] >= 120 for x in result["segments"]))
            self.assertEqual(result["audio_coverage_seconds"], 141)

    def test_timeline_preserves_exact_frame_and_ocr_relation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "media-result.json").write_text(json.dumps({
                "source": "public_instagram", "media_sha256": "abcd",
                "duration_seconds": 141, "scene_detection": "completed",
                "scenes": [], "frame_records": [
                    {"file": "frame_00.jpg", "seconds": 0.0},
                    {"file": "frame_02.jpg", "seconds": 140.85}],
                "ocr": [{"frame": "frame_02.jpg", "seconds": 140.85,
                         "text": "STOP", "status": "completed"}],
                "coverage": {"audio_seconds_available": 141}}))
            write_timeline(root, {"status": "transcribed", "segments": [
                {"start": 120, "end": 123, "text": "halo"}]})
            result = json.loads((root / "timeline.json").read_text())
            self.assertEqual(result["frames"][-1]["seconds"], 140.85)
            self.assertEqual(result["frames"][-1]["ocr"]["text"], "STOP")
            self.assertEqual(result["speech"][0]["start"], 120)
            self.assertEqual(result["claim_verification"], "not_verified")

    def test_public_manifest_still_enforces_reviewed_job_and_pinned_dependency(self):
        from scripts.job_plan import read_manifest
        root = Path(__file__).resolve().parents[1]
        manifest = read_manifest(root, "public_media")
        args = [a for cmd in manifest["jobs"][0]["commands"] for a in cmd]
        self.assertIn("scenedetect==0.7.3", args)
        self.assertIn("scripts/public_media_transcribe.py", args)


if __name__ == "__main__":
    unittest.main()
