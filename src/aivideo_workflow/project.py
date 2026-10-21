"""A portable planning file and plain Markdown reference packs."""

from __future__ import annotations
from pathlib import Path
import json, math, re, shutil
from .common import save_json


def unique(rows, label):
    seen = set()
    for row in rows:
        key = row.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            raise ValueError(f"{label}: use a non-empty letter/number ID.")
        if key in seen:
            raise ValueError(f"Duplicate {label} ID: {key}")
        seen.add(key)
    return seen


def init_project(directory, title):
    root = Path(directory)
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True)
    for name in ["references", "prompts", "media", "exports"]:
        (root / name).mkdir()
    data = {
        "schema_version": 1,
        "title": title,
        "brief": {
            "topic": "",
            "audience": "",
            "takeaway": "",
            "duration_seconds": [45, 60],
            "aspect_ratio": "16:9",
            "style": "电影感三维动画",
            "audio_mode": "native",
        },
        "characters": [],
        "scenes": [],
        "references": {},
        "dialogue": [],
        "segments": [],
    }
    save_json(root / "project.json", data)
    save_json(
        root / "timeline.json", {"width": 1920, "height": 1080, "fps": 60, "clips": []}
    )
    return {
        "directory": str(root),
        "next": "Fill project.json, then run aivideo check.",
    }


def check_project(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Use schema_version 1.")
    if not data.get("title"):
        raise ValueError("Give the film a title.")
    characters = unique(data.get("characters", []), "character")
    scenes = unique(data.get("scenes", []), "scene")
    lines = unique(data.get("dialogue", []), "dialogue")
    segments = unique(data.get("segments", []), "segment")
    if not characters or not segments:
        raise ValueError("Add characters and at least one segment.")
    dialogue = {row["id"]: row for row in data.get("dialogue", [])}
    for row in dialogue.values():
        if row["speaker"] not in characters:
            raise ValueError(f"Unknown speaker in {row['id']}.")
        if not row.get("text", "").strip():
            raise ValueError(f"Add dialogue text to {row['id']}.")
    references = data.get("references", {})
    for key, value in references.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            raise ValueError("Use simple reference IDs.")
        if value["type"] not in ["image", "audio", "video"]:
            raise ValueError(f"Unknown reference type: {key}")
        if not (path.parent / value["path"]).is_file():
            raise ValueError(f"Reference file missing: {key}")
    for segment in data["segments"]:
        duration = float(segment["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Use a positive segment duration.")
        for ref in segment.get("references", []):
            if ref not in references:
                raise ValueError(f"Unknown reference {ref}.")
        if not (path.parent / segment["prompt_file"]).is_file():
            raise ValueError(f"Prompt file missing for {segment['id']}.")
        end = 0.0
        for shot in segment.get("shots", []):
            start = float(shot["start"])
            stop = float(shot["end"])
            if (
                not all(math.isfinite(x) for x in [start, stop])
                or start < end - 1e-6
                or not start < stop <= duration + 1e-6
            ):
                raise ValueError(f"Shot boundaries overlap or exceed {segment['id']}.")
            speaker = shot.get("speaker")
            if speaker is not None and speaker not in characters:
                raise ValueError("Unknown shot speaker.")
            for line in shot.get("lines", []):
                if line not in lines:
                    raise ValueError(f"Unknown dialogue ID {line}.")
                if dialogue[line]["speaker"] != speaker:
                    raise ValueError(f"Dialogue {line} belongs to a different speaker.")
            if shot.get("scene") and shot["scene"] not in scenes:
                raise ValueError("Unknown scene.")
            end = stop
    return {
        "title": data["title"],
        "characters": len(characters),
        "scenes": len(scenes),
        "dialogue_lines": len(lines),
        "segments": len(segments),
        "references": len(references),
        "valid": True,
    }


def export_prompts(project, output):
    project = Path(project).resolve()
    check_project(project)
    root = Path(output)
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True)
    (root / "references").mkdir()
    data = json.loads(project.read_text(encoding="utf-8"))
    copied = set()
    files = []
    for segment in data["segments"]:
        table = [
            "# " + segment["id"],
            "",
            data["title"],
            "",
            "## 上传参考",
            "",
            "| ID | 类型 | 文件 |",
            "| --- | --- | --- |",
        ]
        for ref in segment["references"]:
            value = data["references"][ref]
            src = (project.parent / value["path"]).resolve()
            name = ref + src.suffix.lower()
            if name not in copied:
                shutil.copyfile(src, root / "references" / name)
                copied.add(name)
            table.append(f"| {ref} | {value['type']} | [查看](references/{name}) |")
        body = (project.parent / segment["prompt_file"]).read_text(encoding="utf-8")
        text = "\n".join(table) + "\n\n## 提示词\n\n" + body.rstrip() + "\n"
        target = root / (segment["id"] + ".md")
        target.write_text(text, encoding="utf-8")
        files.append(target.name)
    return {"directory": str(root), "prompts": files, "reference_files": len(copied)}
