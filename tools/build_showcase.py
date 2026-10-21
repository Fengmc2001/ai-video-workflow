"""Build the bilingual gallery with verified Mandarin and English films."""

from pathlib import Path
import argparse
import hashlib
import json
import shutil


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(video, english_video, output):
    root = Path(__file__).resolve().parents[1]
    output = Path(output).resolve()
    case = root / "examples/traffic-safety"
    original = json.loads((case / "postproduction.json").read_text())["published_video"]
    english = json.loads((case / "english-version.json").read_text())
    versions = [
        ("zh-CN", Path(video).resolve(), original["file"], original["sha256"]),
        ("en", Path(english_video).resolve(), english["file"], english["sha256"]),
    ]
    for language, source, name, expected in versions:
        if file_hash(source) != expected:
            raise ValueError("Film checksum did not match: " + language)
    if output.exists():
        raise FileExistsError("Choose an empty output directory.")
    output.mkdir(parents=True)
    for path in (root / "site").iterdir():
        if path.is_file():
            shutil.copyfile(path, output / path.name)
    shutil.copytree(root / "assets", output / "assets")
    (output / "media").mkdir()
    for language, source, name, expected in versions:
        shutil.copyfile(source, output / "media" / name)
    result = {
        "versions": [
            {"language": language, "file": "media/" + name, "sha256": expected}
            for language, source, name, expected in versions
        ],
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
    parser.add_argument("--english-video", required=True)
    parser.add_argument("--output", default="dist/showcase")
    arguments = parser.parse_args()
    print(
        json.dumps(
            build(arguments.video, arguments.english_video, arguments.output), indent=2
        )
    )
