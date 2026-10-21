"""Native-audio editing, timeline assembly and an author watermark."""

from __future__ import annotations
from pathlib import Path
from fractions import Fraction
import math, tempfile, wave, json
from .common import (
    binary,
    run,
    probe,
    video_stream,
    audio_hash,
    pcm,
    pcm_array,
    pcm_bytes,
    verify,
    destination,
    filter_path,
    save_json,
)


def find_font(explicit=None):
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for name in candidates:
        if Path(name).is_file():
            return Path(name)
    raise RuntimeError("Provide --font with a local TTF/OTF font path.")


def watermark(source, output, text="Fengmc", font=None, size=34, margin=40):
    if size < 1 or margin < 0:
        raise ValueError("Font size and margins must be positive.")
    output = destination(output, source)
    font = find_font(font)
    with tempfile.TemporaryDirectory(prefix=".aivideo-", dir=output.parent) as temp:
        textfile = Path(temp) / "watermark.txt"
        textfile.write_text(text, encoding="utf-8")
        vf = (
            f"drawtext=fontfile='{filter_path(font)}':textfile='{filter_path(textfile)}':"
            f"expansion=none:fontsize={size}:fontcolor=white@0.78:"
            f"x=w-tw-{margin}:y=h-th-{margin}:shadowcolor=black@0.5:shadowx=1:shadowy=1"
        )
        run(
            [
                binary("ffmpeg"),
                "-y",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-i",
                source,
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-map_metadata",
                "-1",
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "17",
                "-threads",
                "4",
                "-pix_fmt",
                "yuv420p",
                "-fps_mode",
                "passthrough",
                "-video_track_timescale",
                "15360",
                "-movie_timescale",
                "48000",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                output,
            ]
        )
    before = video_stream(source)
    after = video_stream(output)
    has_audio = any(s["codec_type"] == "audio" for s in probe(source)["streams"])
    if int(before["nb_frames"]) != int(after["nb_frames"]):
        raise RuntimeError("Watermark export changed the frame count.")
    if has_audio:
        if audio_hash(source) != audio_hash(output):
            raise RuntimeError("Watermark export changed the native audio payload.")
    result = verify(output)
    result.update(watermark=text, native_audio_payload_preserved=has_audio)
    save_json(output.with_suffix(".report.json"), result)
    return result


def replace_pcm(original, replacement, start, end, rate=48000, crossfade_ms=0):
    """Replace one stereo PCM interval; retain every sample after its end."""
    if rate <= 0 or not math.isfinite(start) or not math.isfinite(end):
        raise ValueError("Invalid sample rate or interval.")
    first = round(start * rate) * 2
    last = round(end * rate) * 2
    a = pcm_array(original)
    b = pcm_array(replacement)
    if not 0 <= first < last <= len(a):
        raise ValueError("Replacement interval is outside the original.")
    if len(b) < last - first:
        raise ValueError("Replacement audio is shorter than the chosen interval.")
    nfade = round(crossfade_ms * rate / 1000)
    if nfade < 0 or nfade * 2 > last - first:
        raise ValueError("Crossfade is longer than the replacement interval.")
    out = a[:]
    out[first:last] = b[: last - first]
    if nfade:
        for i in range(nfade):
            alpha = (i + 1) / nfade
            for ch in range(2):
                at = last - nfade * 2 + i * 2 + ch
                source_at = at - first
                out[at] = round(b[source_at] * (1 - alpha) + a[at] * alpha)
    return pcm_bytes(out)


def write_wav(path, data, rate=48000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)


def patch_audio(source, replacement, output, start, end, crossfade_ms=0):
    output = destination(output, source)
    original = pcm(source)
    new = pcm(replacement)
    master = replace_pcm(original, new, start, end, crossfade_ms=crossfade_ms)
    wav = output.with_suffix(".audio.wav")
    if wav.exists():
        raise FileExistsError(wav)
    write_wav(wav, master)
    run(
        [
            binary("ffmpeg"),
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-i",
            source,
            "-i",
            wav,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            "-movie_timescale",
            "48000",
            "-movflags",
            "+faststart",
            output,
        ]
    )
    result = verify(output)
    result.update(
        replaced_interval=[start, end],
        crossfade_ms=crossfade_ms,
        audio_master=wav.name,
        original_tail_preserved=True,
        video_stream_copied=True,
    )
    save_json(output.with_suffix(".report.json"), result)
    return result


def assemble(timeline, output, allow_frame_repeat=False):
    timeline = Path(timeline).resolve()
    cfg = json.loads(timeline.read_text(encoding="utf-8"))
    output = destination(output)
    fps = Fraction(str(cfg.get("fps", 60)))
    width = int(cfg.get("width", 1920))
    height = int(cfg.get("height", 1080))
    if fps <= 0 or width <= 0 or height <= 0 or width % 2 or height % 2:
        raise ValueError(
            "Use positive even image dimensions and a positive frame rate."
        )
    clips = cfg.get("clips", [])
    if not clips:
        raise ValueError("Timeline contains no clips.")
    rate = 48000
    inputs = []
    chains = []
    counts = []
    blocks = []
    audio_pads = []
    for i, clip in enumerate(clips):
        video = (timeline.parent / clip["video"]).resolve()
        sound = (timeline.parent / clip.get("audio", clip["video"])).resolve()
        if output in [video, sound]:
            raise ValueError("Output must be separate from every input.")
        v = video_stream(video)
        source_rate = Fraction(v["avg_frame_rate"])
        if source_rate < fps - Fraction(1, 10) and not allow_frame_repeat:
            raise ValueError(
                f"{video.name} needs motion interpolation before this {fps}fps assembly."
            )
        data = pcm(sound, rate)
        samples = len(data) // 4
        count = math.ceil(max(float(v["duration"]), samples / rate) * float(fps) - 1e-6)
        padded = round(Fraction(count, 1) / fps * rate)
        gap = padded - samples
        if gap < 0 or gap > rate:
            raise ValueError(
                "Audio/video duration difference exceeds one second; choose clip boundaries first."
            )
        blocks.append(data + b"\0" * (gap * 4))
        counts.append(count)
        audio_pads.append(gap)
        inputs += ["-i", str(video)]
        duration = count / float(fps)
        chains.append(
            f"[{i}:v]setpts=PTS-STARTPTS,fps={fps}:round=near,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:out_color_matrix=bt709,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration=1,trim=duration={duration:.9f}[v{i}]"
        )
    master = output.with_suffix(".audio.wav")
    if master.exists():
        raise FileExistsError(master)
    write_wav(master, b"".join(blocks), rate)
    chains.append(
        "".join(f"[v{i}]" for i in range(len(clips)))
        + f"concat=n={len(clips)}:v=1:a=0[v]"
    )
    run(
        [
            binary("ffmpeg"),
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            *inputs,
            "-i",
            master,
            "-filter_complex",
            ";".join(chains),
            "-map",
            "[v]",
            "-map",
            f"{len(clips)}:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "17",
            "-threads",
            "4",
            "-pix_fmt",
            "yuv420p",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-color_range",
            "tv",
            "-video_track_timescale",
            "15360",
            "-movie_timescale",
            "48000",
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            output,
        ]
    )
    result = verify(output, float(fps), decode=True, frame_check=True)
    if result["frames"] != sum(counts):
        raise RuntimeError("Assembled frame count differs from the timeline.")
    result.update(
        part_frames=counts, audio_pad_samples=audio_pads, audio_master=master.name
    )
    save_json(output.with_suffix(".report.json"), result)
    return result
