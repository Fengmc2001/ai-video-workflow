"""Exercise role binding, sample-preserving edits and encoded video timing."""

from array import array
from fractions import Fraction
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import wave

from aivideo_workflow.common import (
    audio_hash,
    binary,
    pcm,
    pcm_array,
    pcm_bytes,
    timestamps,
    verify,
)
from aivideo_workflow.media import (
    assemble,
    patch_audio,
    replace_pcm,
    watermark,
    write_wav,
)
from aivideo_workflow.project import check_project, export_prompts, init_project

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples/traffic-safety/project.json"


class AudioIntervalTests(unittest.TestCase):
    def test_interval_replacement_keeps_every_outside_sample(self):
        original = pcm_bytes(array("h", range(80)))
        replacement = pcm_bytes(array("h", [500] * 24))
        result = replace_pcm(original, replacement, 1, 2, rate=10)
        self.assertEqual(result[:40], original[:40])
        self.assertEqual(result[80:], original[80:])
        self.assertEqual(pcm_array(result)[20:40], array("h", [500] * 20))

    def test_crossfade_rejoins_original_inside_interval(self):
        original = pcm_bytes(array("h", [100] * 80))
        replacement = pcm_bytes(array("h", [500] * 24))
        result = replace_pcm(original, replacement, 1, 2, rate=10, crossfade_ms=200)
        values = pcm_array(result)
        self.assertEqual(values[36:38], array("h", [300, 300]))
        self.assertEqual(values[38:40], array("h", [100, 100]))
        self.assertEqual(result[80:], original[80:])

    def test_short_or_out_of_bounds_audio_is_rejected(self):
        original = pcm_bytes(array("h", [100] * 80))
        short = pcm_bytes(array("h", [500] * 2))
        with self.assertRaisesRegex(ValueError, "shorter"):
            replace_pcm(original, short, 1, 2, rate=10)
        with self.assertRaisesRegex(ValueError, "outside"):
            replace_pcm(original, original, -1, 2, rate=10)


class PlanningTests(unittest.TestCase):
    def test_case_has_three_characters_and_two_segments(self):
        result = check_project(CASE)
        self.assertTrue(result["valid"])
        self.assertEqual(result["characters"], 3)
        self.assertEqual(result["segments"], 2)

    def test_prompt_pack_copies_images_and_original_voice_references(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pack"
            result = export_prompts(CASE, output)
            self.assertEqual(result["prompts"], ["G1.md", "G2.md"])
            self.assertTrue((output / "references/linhao.jpg").is_file())
            self.assertTrue((output / "references/linhao_voice.wav").is_file())
            self.assertIn("自行车天天骑着也太累了", (output / "G1.md").read_text())

    def test_dialogue_cannot_be_assigned_to_a_different_character(self):
        data = json.loads(CASE.read_text())
        for reference in data["references"].values():
            reference["path"] = str((CASE.parent / reference["path"]).resolve())
        for segment in data["segments"]:
            segment["prompt_file"] = str(
                (CASE.parent / segment["prompt_file"]).resolve()
            )
        data["segments"][0]["shots"][0]["speaker"] = "zhangwei"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "different speaker"):
                check_project(path)

    def test_init_keeps_an_existing_project(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "film"
            init_project(output, "我的短片")
            original = (output / "project.json").read_bytes()
            with self.assertRaises(FileExistsError):
                init_project(output, "another")
            self.assertEqual((output / "project.json").read_bytes(), original)


def make_clip(directory, name, color="blue", frames=8, size="128x72"):
    directory = Path(directory)
    video = directory / (name + ".mp4")
    audio = directory / (name + ".wav")
    samples = frames * 800
    values = array("h")
    for i in range(samples):
        value = (i % 80 - 40) * 100
        values.extend([value, value])
    write_wav(audio, pcm_bytes(values))
    subprocess.run(
        [
            binary("ffmpeg"),
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={size}:r=60",
            "-i",
            str(audio),
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movie_timescale",
            "48000",
            "-video_track_timescale",
            "15360",
            str(video),
        ],
        check=True,
    )
    return video, audio


def video_payload(path):
    return subprocess.check_output(
        [
            binary("ffmpeg"),
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-c",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ]
    )


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required"
)
class MediaIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.a, self.a_audio = make_clip(self.root, "a", "blue")
        self.b, self.b_audio = make_clip(self.root, "b", "red")

    def test_watermark_keeps_frames_duration_and_native_audio(self):
        output = self.root / "marked.mp4"
        result = watermark(self.a, output, size=12, margin=4)
        self.assertEqual(result["frames"], 8)
        self.assertAlmostEqual(result["duration"], 8 / 60, places=6)
        self.assertEqual(audio_hash(self.a), audio_hash(output))
        self.assertNotEqual(video_payload(self.a), video_payload(output))
        verify(output, 60, decode=True, frame_check=True)

    def test_watermark_text_is_literal(self):
        output = self.root / "literal.mp4"
        watermark(self.a, output, text="Fengmc:%{x}'[1]", size=10, margin=2)
        self.assertTrue(output.is_file())

    def test_assembly_keeps_fractional_clip_duration_and_pcm(self):
        timeline = self.root / "timeline.json"
        timeline.write_text(
            json.dumps(
                {
                    "width": 128,
                    "height": 72,
                    "fps": 60,
                    "clips": [
                        {"video": "a.mp4", "audio": "a.wav"},
                        {"video": "b.mp4", "audio": "b.wav"},
                    ],
                }
            )
        )
        output = self.root / "joined.mp4"
        result = assemble(timeline, output)
        self.assertEqual(result["part_frames"], [8, 8])
        self.assertEqual(result["frames"], 16)
        self.assertAlmostEqual(result["duration"], 16 / 60, places=6)
        expected = pcm(self.a_audio) + pcm(self.b_audio)
        with wave.open(str(output.with_suffix(".audio.wav")), "rb") as handle:
            self.assertEqual(handle.readframes(handle.getnframes()), expected)
        for i, timestamp in enumerate(timestamps(output)):
            self.assertLess(abs(timestamp - Fraction(i, 60)), Fraction(1, 100000))

    def test_audio_patch_keeps_video_and_unselected_samples(self):
        original = pcm(self.a)
        output = self.root / "patched.mp4"
        patch_audio(self.a, self.b_audio, output, start=0.02, end=0.1)
        self.assertEqual(video_payload(output), video_payload(self.a))
        with wave.open(str(output.with_suffix(".audio.wav")), "rb") as handle:
            edited = handle.readframes(handle.getnframes())
        self.assertEqual(edited[: 960 * 4], original[: 960 * 4])
        self.assertEqual(edited[4800 * 4 :], original[4800 * 4 :])

    def test_existing_audio_master_is_kept(self):
        output = self.root / "kept.mp4"
        master = output.with_suffix(".audio.wav")
        master.write_bytes(b"keep this")
        with self.assertRaises(FileExistsError):
            patch_audio(self.a, self.b_audio, output, start=0.02, end=0.1)
        self.assertEqual(master.read_bytes(), b"keep this")


@unittest.skipUnless(
    os.environ.get("AIVIDEO_TEST_WEIGHTS") and importlib.util.find_spec("torch"),
    "Set AIVIDEO_TEST_WEIGHTS and install superres dependencies for the neural smoke test",
)
class SuperResolutionTests(unittest.TestCase):
    def test_neural_upscale_preserves_timestamps_and_audio(self):
        from aivideo_workflow.upscale import upscale

        with tempfile.TemporaryDirectory() as directory:
            source, _ = make_clip(directory, "tiny", frames=2, size="32x18")
            output = Path(directory) / "tiny-sr.mp4"
            result = upscale(
                source,
                output,
                weights=os.environ["AIVIDEO_TEST_WEIGHTS"],
                device="cpu",
                width=64,
                height=36,
                tile=64,
            )
            self.assertEqual(
                (result["width"], result["height"], result["frames"]), (64, 36, 2)
            )
            self.assertEqual(audio_hash(source), audio_hash(output))
            self.assertEqual(timestamps(source), timestamps(output))


if __name__ == "__main__":
    unittest.main()
