"""Regression tests: clean source links, media processing, and fail-closed behavior."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.public_media_input import (validate_public_media_url,
                                        validated_public_media_environment)

class MediaInputTests(unittest.TestCase):
    def test_public_reel_and_photo(self):
        self.assertEqual(validate_public_media_url("https://instagram.com/reel/DfJe39jptS8"),
                         "https://www.instagram.com/reel/DfJe39jptS8/")
        self.assertEqual(validate_public_media_url("https://www.instagram.com/p/ABCdef123_/"),
                         "https://www.instagram.com/p/ABCdef123_/")

    def test_auth_secrets_and_unsafe_hosts_rejected(self):
        bad = [
            "http://www.instagram.com/reel/DfJe39jptS8/",
            "https://evil.com/reel/DfJe39jptS8/",
            "https://instagram.com.evil.com/reel/DfJe39jptS8/",
            "https://localhost/reel/DfJe39jptS8/",
            "https://user:pass@instagram.com/reel/DfJe39jptS8/",
            "https://www.instagram.com/reel/DfJe39jptS8/?token=secret",
            "https://www.instagram.com/reel/DfJe39jptS8/#private",
            "https://www.instagram.com/reel/DfJe39jptS8/../../",
            "https://www.instagram.com/reel/DfJe39jptS8/%2f",
            "https://www.instagram.com/anything/DfJe39jptS8/",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_public_media_url(url)
        with self.assertRaises(ValueError):
            validate_public_media_url("https://www.instagram.com/reel/DfJe39jptS8/",
                                      '[{"action":"click"}]')

    def test_job_env_does_not_forward_credentials(self):
        env = validated_public_media_environment("public_media", {
            "ZEIBAEL_BROWSER_URL": "https://instagram.com/reel/DfJe39jptS8",
            "ZEIBAEL_BROWSER_STEPS": "[]",
            "GITHUB_TOKEN": "private"})
        self.assertEqual(set(env), {"ZEIBAEL_MEDIA_URL"})
        self.assertEqual(validated_public_media_environment("public_browser", {}), {})

class MediaProcessorTests(unittest.TestCase):
    def test_media_manifest_is_reviewed_and_never_exposes_private_input(self):
        from scripts.job_plan import read_manifest, build_plan
        from unittest.mock import patch
        root = Path(__file__).resolve().parents[1]
        job = read_manifest(root, "public_media")["jobs"][0]
        self.assertTrue(job["output_files"])
        self.assertEqual(job["runtime"], "python")
        self.assertTrue(any("install_media_tools.sh" in arg
                            for argv in job["commands"] for arg in argv))
        env = {"ZEIBAEL_BROWSER_URL": "https://instagram.com/reel/DfJe39jptS8",
               "ZEIBAEL_BROWSER_STEPS": "[]"}
        with patch.dict("os.environ", env):
            p = build_plan(root, "script", "public_media")
            self.assertEqual(len(p["include"]), 1)
        with patch.dict("os.environ", {
                "ZEIBAEL_BROWSER_URL": "https://evil.com/reel/DfJe39jptS8",
                "ZEIBAEL_BROWSER_STEPS": "[]"}):
            with self.assertRaises(ValueError):
                build_plan(root, "script", "public_media")

    def test_media_module_importable_and_no_side_effects(self):
        from scripts.public_media import find_approved_media
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.txt").write_text("no media")
            self.assertIsNone(find_approved_media(root))
            (root / "photo.jpg").write_bytes(b"a" * 500)
            self.assertEqual(find_approved_media(root).suffix, ".jpg")
            (root / "video.mp4").write_bytes(b"a" * 500)
            self.assertEqual(find_approved_media(root).suffix, ".mp4")

    def test_ffmpeg_synthetic_video_extracts_frames_audio(self):
        from shutil import which
        if not which("ffmpeg") or not which("ffprobe"):
            self.skipTest("ffmpeg/ffprobe absent on this host")
        from scripts.public_media import make_evidence
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "synthetic.mp4"
            output = root / "out"
            output.mkdir()
            cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                   "-i", "testsrc=size=160x90:rate=4", "-f", "lavfi",
                   "-i", "sine=frequency=440:sample_rate=16000", "-t", "2",
                   "-c:v", "mpeg4", "-c:a", "aac", str(src)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True, timeout=20)
            report = make_evidence(src, output)
            self.assertEqual(report["kind"], "video")
            self.assertGreaterEqual(len(report["frames"]), 1)
            for fname in report["frames"]:
                self.assertGreater((output / fname).stat().st_size, 500)
            self.assertTrue((output / "speech.wav").stat().st_size > 10000)

    def test_reject_overlarge_and_symlink_media(self):
        from scripts.public_media import find_approved_media
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            big = root / "large.mp4"
            with big.open("wb") as f:
                f.truncate(32_000_001)
            self.assertIsNone(find_approved_media(root))
            link = root / "evil.jpg"
            link.symlink_to(big)
            self.assertIsNone(find_approved_media(root))
