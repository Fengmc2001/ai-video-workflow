"""Build the public gallery with a verified copy of the released film."""

from pathlib import Path
import argparse
import hashlib
import json
import shutil


def build(video, output):
    root = Path(__file__).resolve().parents[1]
    video = Path(video).resolve()
    output = Path(output).resolve()
    expected = json.loads(
        (root / "examples/traffic-safety/postproduction.json").read_text()
    )["published_video"]["sha256"]
    digest = hashlib.sha256()
    with video.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError("Use the watermarked video from Release v0.1.0.")
    if output.exists():
        raise FileExistsError("Choose an empty output directory.")
    output.mkdir(parents=True)
    for path in (root / "site").iterdir():
        if path.is_file():
            shutil.copyfile(path, output / path.name)
    shutil.copytree(root / "assets", output / "assets")
    (output / "media").mkdir()
    shutil.copyfile(video, output / "media/traffic-safety-fengmc-1080p60.mp4")
    result = {
        "film": "media/traffic-safety-fengmc-1080p60.mp4",
        "sha256": expected,
        "languages": ["en", "zh-CN"],
        "pages": ["index.html"],
    }
    (output / "showcase-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", default="dist/showcase")
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.video, arguments.output), indent=2))
