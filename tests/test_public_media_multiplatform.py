import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.public_media_input import validate_public_media_url


class PublicLinkTests(unittest.TestCase):
    def test_canonicalizes_youtube_shorts_and_watch(self):
        for url in ("https://www.youtube.com/watch?v=aqz-KE-bpKQ",
                    "https://www.youtube.com/shorts/aqz-KE-bpKQ",
                    "https://youtu.be/aqz-KE-bpKQ"):
            self.assertEqual(validate_public_media_url(url), "https://youtu.be/aqz-KE-bpKQ")

    def test_tiktok_and_threads_permalink(self):
        for url in ("https://www.tiktok.com/@creator/video/7345678901234567890",
                    "https://www.threads.com/@creator/post/DfUvH2Nkqwj"):
            self.assertEqual(validate_public_media_url(url), url)

    def test_rejects_unresolved_redirects_credentials_and_playlists(self):
        for url in ("https://vm.tiktok.com/shortCode/",
                    "https://www.threads.com/share/BAqjZobKyd",
                    "https://www.youtube.com/watch?v=aqz-KE-bpKQ&list=PLsecret",
                    "https://www.youtube.com/watch?v=aqz-KE-bpKQ&next=https://localhost/",
                    "https://www.you\ttube.com/shorts/aqz-KE-bpKQ",
                    "https://www.threads.com/@creator/post/DfUvH2Nkqwj?token=secret",
                    "https://youtu.be/aqz-KE-bpKQ@evil.com",
                    "https://www.tiktok.com/@creator/video/%2e%2e",
                    "https://www.youtube.com:444/shorts/aqz-KE-bpKQ",
                    "https://www.youtube.com/playlist?list=PLsecret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_public_media_url(url)

    def test_platform_specific_extractors_and_ids(self):
        from scripts.public_media import media_shortcode, public_extractor_commands
        base = Path("/tmp/reviewed-media-test")
        for url, selector, vid in (
                ("https://www.youtube.com/watch?v=aqz-KE-bpKQ", "youtube", "aqz-KE-bpKQ"),
                ("https://www.tiktok.com/@creator/video/7345678901234567890", "tiktok", "7345678901234567890")):
            self.assertEqual(media_shortcode(url), vid)
            commands = public_extractor_commands(url, base)
            self.assertEqual([name for name, _ in commands], ["yt-dlp"])
            cmd = commands[0][1]
            self.assertEqual(cmd[cmd.index("--use-extractors")+1], selector)
            self.assertNotIn("--cookies", cmd)

    def test_threads_requires_matching_post_and_public_video_metadata(self):
        from scripts.public_threads_media import threads_video_url
        p = "https://www.threads.com/@creator/post/DfUvH2Nkqwj"
        v = "https://scontent.cdninstagram.com/clip.mp4"
        tags = '<link rel="canonical" href="{}"><meta property="og:video:secure_url" content="{}">'
        self.assertEqual(threads_video_url(tags.format(p, v), p), v)
        photo = '<link rel="canonical" href="{}"><meta property="og:image" content="{}">'
        self.assertIsNone(threads_video_url(photo.format(p, v), p))
        self.assertIsNone(threads_video_url(tags.format(p.replace("DfUvH2Nkqwj", "DifferentId"), v), p))
        self.assertIsNone(threads_video_url(tags.format(p, "https://cdninstagram.com.evil.example/clip.mp4"), p))
        self.assertIsNone(threads_video_url(tags.format(p, v) + tags.format(p, v.replace("clip", "other")), p))
        self.assertIsNone(threads_video_url(tags.format(p, v.replace("https:", "http:")), p))

    def test_vision_bridge_returns_several_distinct_actual_frames(self):
        from scripts.public_media import vision_frame_bundle
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = [{"file": f"frame_{i:02}.jpg", "seconds": 2.5*i} for i in range(9)]
            data = b"\xff\xd8\xffjpg\xff\xd9"
            with patch("scripts.public_media.vision_preview_base64", return_value=base64.b64encode(data).decode()):
                result = vision_frame_bundle(root, records, "sample12345", "instagram")
            self.assertEqual(result["media_id"], "sample12345")
            self.assertEqual(result["platform"], "instagram")
            frames = result["frames"]
            self.assertEqual(len(frames), 6)
            self.assertEqual([frames[0]["seconds"], frames[-1]["seconds"]], [0, 20])
            self.assertEqual(len({r["frame"] for r in frames}), len(frames))
            self.assertTrue(all(base64.b64decode(r["jpeg_base64"]) == data for r in frames))
            self.assertLess(len(json.dumps(result)), 25000)

class FocusWindowTests(unittest.TestCase):
    def test_window_is_bounded_and_never_changes_generic_browser(self):
        from scripts.public_media_input import parse_media_window, validated_public_media_environment
        self.assertEqual(parse_media_window("301:331"), (301, 331))
        self.assertIsNone(parse_media_window(""))
        for value in ("1:3010", "5:5", "999:900", "-1:5", "2:99999", "2:4 --foo"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_media_window(value)
        source = {"ZEIBAEL_BROWSER_URL": "https://youtu.be/aqz-KE-bpKQ",
                  "ZEIBAEL_MEDIA_WINDOW": "301:331", "ZEIBAEL_BROWSER_STEPS": "[]"}
        self.assertEqual(validated_public_media_environment("public_media", source)["ZEIBAEL_MEDIA_WINDOW"], "301:331")
        self.assertEqual(validated_public_media_environment("public_browser", source), {})

    def test_focus_window_keeps_video_timestamp_origin_and_download_bounds(self):
        from scripts.public_media import public_extractor_commands, offset_video_records
        url = "https://youtu.be/aqz-KE-bpKQ"
        argv = public_extractor_commands(url, Path("/tmp/reviewed-media-test"), (301, 331))[0][1]
        self.assertEqual(argv[argv.index("--download-sections")+1], "*301-331")
        report = {"frame_records": [{"file": "frame_00.jpg", "seconds": 0}],
                  "ocr": [{"seconds": 1}], "scenes": [{"start": 0, "end": 2}],
                  "sampled_seconds": [0.0, 2.0], "duration_seconds": 2.0}
        offset_video_records(report, (301, 331))
        self.assertEqual(report["frame_records"][0]["seconds"], 301)
        self.assertEqual(report["ocr"][0]["seconds"], 302)
        self.assertEqual(report["scenes"][0], {"start": 301, "end": 303})
        self.assertEqual(report["sampled_seconds"], [301, 303])
        self.assertEqual(report["duration_seconds"], 2)


if __name__ == "__main__":
    unittest.main()
