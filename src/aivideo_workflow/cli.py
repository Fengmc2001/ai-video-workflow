"""Command-line entry points for a short-film project."""

from __future__ import annotations
import argparse, json, sys
from .common import verify
from .media import watermark, patch_audio, assemble


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="aivideo", description="Plan an AI short film and finish it locally."
    )
    sp = p.add_subparsers(dest="command", required=True)
    a = sp.add_parser("init", help="Create a film planning folder.")
    a.add_argument("directory")
    a.add_argument("--title", default="我的动画短片")
    a = sp.add_parser("check", help="Check character, dialogue and shot references.")
    a.add_argument("project")
    a = sp.add_parser("prompts", help="Export prompts and reference upload lists.")
    a.add_argument("project")
    a.add_argument("--output", required=True)
    a = sp.add_parser(
        "inspect", help="Inspect a video and optionally decode all frames."
    )
    a.add_argument("input")
    a.add_argument("--fps", type=float)
    a.add_argument("--frames", action="store_true")
    a.add_argument("--decode", action="store_true")
    a = sp.add_parser(
        "watermark", help="Burn an author name into a video; copy its audio."
    )
    a.add_argument("input")
    a.add_argument("--output", required=True)
    a.add_argument("--text", default="Fengmc")
    a.add_argument("--font")
    a.add_argument("--size", type=int, default=34)
    a.add_argument("--margin", type=int, default=40)
    a = sp.add_parser(
        "patch-audio",
        help="Replace a selected interval with native recorded/generated audio.",
    )
    a.add_argument("input")
    a.add_argument("replacement")
    a.add_argument("--output", required=True)
    a.add_argument("--start", type=float, required=True)
    a.add_argument("--end", type=float, required=True)
    a.add_argument("--crossfade-ms", type=float, default=0)
    a = sp.add_parser(
        "assemble", help="Assemble already interpolated clips with native audio."
    )
    a.add_argument("timeline")
    a.add_argument("--output", required=True)
    a.add_argument("--allow-frame-repeat", action="store_true")
    a = sp.add_parser(
        "upscale", help="Apply RealESRGAN x2plus spatial super-resolution."
    )
    a.add_argument("input")
    a.add_argument("--output", required=True)
    a.add_argument("--weights", default="weights/RealESRGAN_x2plus.pth")
    a.add_argument("--device", choices=["cuda", "cpu", "mps"], default="cuda")
    a.add_argument("--width", type=int, default=1920)
    a.add_argument("--height", type=int, default=1080)
    a.add_argument("--strength", type=float, default=0.85)
    a.add_argument("--tile", type=int, default=1024)
    args = p.parse_args(argv)
    try:
        if args.command in ["init", "check", "prompts"]:
            from .project import init_project, check_project, export_prompts

            if args.command == "init":
                result = init_project(args.directory, args.title)
            elif args.command == "check":
                result = check_project(args.project)
            else:
                result = export_prompts(args.project, args.output)
        elif args.command == "inspect":
            result = verify(args.input, args.fps, args.decode, args.frames)
        elif args.command == "watermark":
            result = watermark(
                args.input, args.output, args.text, args.font, args.size, args.margin
            )
        elif args.command == "patch-audio":
            result = patch_audio(
                args.input,
                args.replacement,
                args.output,
                args.start,
                args.end,
                args.crossfade_ms,
            )
        elif args.command == "assemble":
            result = assemble(args.timeline, args.output, args.allow_frame_repeat)
        else:
            from .upscale import upscale

            result = upscale(
                args.input,
                args.output,
                args.weights,
                args.device,
                args.width,
                args.height,
                args.strength,
                args.tile,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
