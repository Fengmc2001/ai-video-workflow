"""FFmpeg and file helpers shared by the local commands."""

from __future__ import annotations
from array import array
from fractions import Fraction
import hashlib, json, shutil, subprocess, sys
from pathlib import Path


def binary(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise RuntimeError(f"{name} is required; install FFmpeg first.")
    return value


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def probe(path):
    return json.loads(
        subprocess.check_output(
            [
                binary("ffprobe"),
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
    )


def video_stream(path):
    try:
        return next(s for s in probe(path)["streams"] if s["codec_type"] == "video")
    except StopIteration:
        raise ValueError(f"No video stream in {Path(path).name}") from None


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audio_hash(path):
    return (
        subprocess.check_output(
            [
                binary("ffmpeg"),
                "-v",
                "error",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-c",
                "copy",
                "-f",
                "hash",
                "-hash",
                "sha256",
                "-",
            ]
        )
        .decode()
        .strip()
    )


def timestamps(path):
    d = json.loads(
        subprocess.check_output(
            [
                binary("ffprobe"),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_frames",
                "-show_entries",
                "frame=best_effort_timestamp_time",
                "-of",
                "json",
                str(path),
            ]
        )
    )
    return [Fraction(x["best_effort_timestamp_time"]) for x in d["frames"]]


def verify(path, fps=None, decode=False, frame_check=False):
    data = probe(path)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    result = {
        "file": Path(path).name,
        "sha256": sha256(path),
        "width": v["width"],
        "height": v["height"],
        "fps": v["avg_frame_rate"],
        "frames": int(v.get("nb_frames", 0)),
        "duration": float(v["duration"]),
        "audio_rate": int(a["sample_rate"]) if a else None,
    }
    if fps is not None and abs(
        Fraction(v["avg_frame_rate"]) - Fraction(str(fps))
    ) > Fraction(1, 1000):
        raise ValueError(f"Expected {fps}fps, found {v['avg_frame_rate']}")
    if frame_check:
        pts = timestamps(path)
        if fps is not None:
            rate = Fraction(str(fps))
            max_error = max(
                (abs(t - pts[0] - Fraction(i, 1) / rate) for i, t in enumerate(pts)),
                default=Fraction(0),
            )
            if max_error > Fraction(1, 100000):
                raise ValueError(
                    "Presentation timestamps do not follow the requested CFR grid."
                )
            result["max_timestamp_error_seconds"] = float(max_error)
        if any(b <= a for a, b in zip(pts, pts[1:])):
            raise ValueError("Non-increasing frame timestamps.")
        result["decoded_frame_count"] = len(pts)
    if decode:
        run(
            [binary("ffmpeg"), "-v", "error", "-xerror", "-i", path, "-f", "null", "-"],
            stdout=subprocess.DEVNULL,
        )
        result["full_decode_passed"] = True
    return result


def pcm(path, rate=48000):
    return subprocess.check_output(
        [
            binary("ffmpeg"),
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-ac",
            "2",
            "-ar",
            str(rate),
            "-f",
            "s16le",
            "-",
        ]
    )


def pcm_array(data):
    out = array("h", data)
    if sys.byteorder != "little":
        out.byteswap()
    return out


def pcm_bytes(values):
    out = array("h", values)
    if sys.byteorder != "little":
        out.byteswap()
    return out.tobytes()


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def destination(path, source=None):
    path = Path(path).resolve()
    if source is not None and path == Path(source).resolve():
        raise ValueError("Choose an output path different from the source.")
    if path.exists():
        raise FileExistsError(f"Output already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def filter_path(path):
    value = str(Path(path).resolve())
    for ch in ["\\", ":", "'", "[", "]", ",", ";"]:
        value = value.replace(ch, "\\" + ch)
    return value
