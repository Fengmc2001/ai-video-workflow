"""Spatial RealESRGAN enhancement with the source presentation timestamps."""

from __future__ import annotations
from pathlib import Path
from fractions import Fraction
import math, tempfile, urllib.request
from .common import (
    binary,
    run,
    probe,
    sha256,
    audio_hash,
    timestamps,
    verify,
    destination,
    save_json,
)

MODEL_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth"
MODEL_SHA256 = "49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb"


def upscale(
    source,
    output,
    weights,
    device="cuda",
    width=1920,
    height=1080,
    strength=0.85,
    tile=1024,
):
    try:
        import av, cv2, numpy as np, torch
        from tqdm import tqdm
        from ._vendor.rrdb_arch import RRDBNet
    except ImportError as exc:
        raise RuntimeError(
            'Install the super-resolution dependencies with pip install -e ".[superres]".'
        ) from exc
    output = destination(output, source)
    weights = Path(weights)
    if (
        not 0 <= strength <= 1
        or width <= 0
        or height <= 0
        or width % 2
        or height % 2
        or tile <= 0
        or tile % 2
    ):
        raise ValueError("Use even image/tile sizes and strength from 0 to 1.")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Choose a CUDA GPU or use --device cpu/mps.")
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable.")
    if not weights.exists():
        weights.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=weights.parent, suffix=".download", delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            urllib.request.urlretrieve(MODEL_URL, temporary)
            if sha256(temporary) != MODEL_SHA256:
                raise RuntimeError("Model checksum did not match.")
            temporary.replace(weights)
        finally:
            temporary.unlink(missing_ok=True)
    if sha256(weights) != MODEL_SHA256:
        raise ValueError("Use the documented RealESRGAN_x2plus weights.")
    model = RRDBNet(3, 3, scale=2, num_feat=64, num_block=23, num_grow_ch=32)
    checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
    model.load_state_dict(
        checkpoint.get("params_ema", checkpoint.get("params")), strict=True
    )
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = model.eval().to(
        device=device, dtype=dtype, memory_format=torch.channels_last
    )
    if device == "cuda":
        torch.backends.cudnn.benchmark = True

    @torch.inference_mode()
    def enhance(rgb):
        h, w, _ = rgb.shape
        data = torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1))).unsqueeze(
            0
        )
        data = (
            data.to(device=device, dtype=dtype, memory_format=torch.channels_last) / 255
        )
        # Pixel-unshuffle in x2plus requires even spatial dimensions.
        data = torch.nn.functional.pad(data, (0, w % 2, 0, h % 2), mode="replicate")
        ph, pw = data.shape[-2:]
        scaled = torch.empty((1, 3, ph * 2, pw * 2), device=device, dtype=dtype)
        pad = 24
        for top in range(0, ph, tile):
            for left in range(0, pw, tile):
                bottom = min(ph, top + tile)
                right = min(pw, left + tile)
                yt = max(0, top - pad)
                yb = min(ph, bottom + pad)
                xl = max(0, left - pad)
                xr = min(pw, right + pad)
                block = model(data[:, :, yt:yb, xl:xr])
                scaled[:, :, top * 2 : bottom * 2, left * 2 : right * 2] = block[
                    :,
                    :,
                    (top - yt) * 2 : (bottom - yt) * 2,
                    (left - xl) * 2 : (right - xl) * 2,
                ]
        sr = (
            (
                scaled[:, :, : h * 2, : w * 2]
                .squeeze(0)
                .clamp_(0, 1)
                .float()
                .cpu()
                .numpy()
                .transpose(1, 2, 0)
                * 255
            )
            .round()
            .astype(np.uint8)
        )
        scale = min(width / w, height / h)
        size = (round(w * scale), round(h * scale))
        sr = cv2.resize(
            sr, size, interpolation=cv2.INTER_AREA if scale <= 2 else cv2.INTER_LANCZOS4
        )
        base = cv2.resize(rgb, size, interpolation=cv2.INTER_LANCZOS4)
        blended = cv2.addWeighted(sr, strength, base, 1 - strength, 0)
        canvas = np.zeros((height, width, 3), np.uint8)
        y = (height - size[1]) // 2
        x = (width - size[0]) // 2
        canvas[y : y + size[1], x : x + size[0]] = blended
        return canvas

    expected = []
    count = 0
    src_info = probe(source)
    audio = next((s for s in src_info["streams"] if s["codec_type"] == "audio"), None)
    with tempfile.TemporaryDirectory(prefix=".aivideo-sr-", dir=output.parent) as temp:
        silent = Path(temp) / "picture.mp4"
        with av.open(str(source)) as container:
            vs = container.streams.video[0]
            tb = vs.time_base
            mux_clock = math.lcm(
                tb.denominator, int(audio["sample_rate"]) if audio else 48000
            )
            with av.open(str(silent), "w") as encoder:
                stream = encoder.add_stream(
                    "libx264", rate=vs.average_rate or Fraction(60, 1)
                )
                stream.width = width
                stream.height = height
                stream.pix_fmt = "yuv420p"
                stream.time_base = tb
                stream.codec_context.time_base = tb
                stream.options = {"crf": "17", "preset": "fast"}
                stream.codec_context.thread_count = 4
                progress = tqdm(
                    total=vs.frames or None, desc="Super-resolution", mininterval=5
                )
                for frame in container.decode(video=0):
                    rgb = frame.to_ndarray(format="rgb24")
                    enhanced = enhance(rgb)
                    result = av.VideoFrame.from_ndarray(enhanced, format="rgb24")
                    result = result.reformat(format="yuv420p", dst_colorspace="ITU709")
                    result.pts = frame.pts
                    result.time_base = frame.time_base
                    expected.append(Fraction(frame.pts) * frame.time_base)
                    for packet in stream.encode(result):
                        encoder.mux(packet)
                    count += 1
                    progress.update(1)
                for packet in stream.encode():
                    encoder.mux(packet)
                progress.close()
        run(
            [
                binary("ffmpeg"),
                "-y",
                "-v",
                "error",
                "-i",
                silent,
                "-i",
                source,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0?",
                "-c",
                "copy",
                "-bsf:v",
                "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
                "-colorspace",
                "bt709",
                "-color_primaries",
                "bt709",
                "-color_trc",
                "bt709",
                "-color_range",
                "tv",
                "-movie_timescale",
                str(mux_clock),
                "-movflags",
                "+faststart",
                output,
            ]
        )
    observed = timestamps(output)
    if len(observed) != count or max(
        abs(a - b) for a, b in zip(expected, observed)
    ) > Fraction(1, 10000):
        raise RuntimeError("Source presentation timestamps were not preserved.")
    if audio and audio_hash(source) != audio_hash(output):
        raise RuntimeError("Native audio payload changed.")
    result = verify(output, decode=True)
    result.update(
        model="RealESRGAN_x2plus",
        model_sha256=MODEL_SHA256,
        strength=strength,
        source_frame_count=count,
        presentation_timestamps_preserved=True,
        native_audio_payload_preserved=bool(audio),
        source_resolution=[
            next(s for s in src_info["streams"] if s["codec_type"] == "video")[k]
            for k in ["width", "height"]
        ],
    )
    save_json(output.with_suffix(".report.json"), result)
    return result
