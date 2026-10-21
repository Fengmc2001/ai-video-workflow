"""Serve the gallery locally, including byte-range requests for video seeking."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import re


class VideoHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        self.remaining = None
        header = self.headers.get("Range")
        path = Path(self.translate_path(self.path))
        if not header or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
        start = stop = None
        if match and (match[1] or match[2]) and size:
            if match[1]:
                start = int(match[1])
                stop = min(int(match[2]), size - 1) if match[2] else size - 1
            elif int(match[2]) > 0:
                start = max(0, size - int(match[2]))
                stop = size - 1
        if start is None or stop is None or start > stop or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        handle = path.open("rb")
        handle.seek(start)
        self.remaining = stop - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{stop}/{size}")
        self.send_header("Content-Length", str(self.remaining))
        self.end_headers()
        return handle

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def copyfile(self, source, destination):
        try:
            if self.remaining is None:
                return super().copyfile(source, destination)
            remaining = self.remaining
            while remaining:
                block = source.read(min(remaining, 64 * 1024))
                if not block:
                    break
                destination.write(block)
                remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default="dist/showcase")
    parser.add_argument("--port", default=8766, type=int)
    args = parser.parse_args()
    handler = partial(VideoHandler, directory=args.directory)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Showcase: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
