"""Local page for judging reviewer findings one by one.

    python3 services/judge/server.py --cases runs/x.cases.jsonl --findings runs/x.findings.jsonl \
        --out runs/x.judgments.jsonl [--notes runs/x.notes.json] [--port 8765]

Listens on 127.0.0.1 only. Every click is appended to --out at once.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import judge_lib  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("cases", "findings", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    items = judge_lib.load_items(args.cases, args.findings, args.notes)
    known = {item["id"] for item in items}
    page = (HERE / "page.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _allowed(self, method: str) -> bool:
            ok = judge_lib.request_allowed(method, self.headers.get("Host"), self.headers.get("Origin"),
                                           self.headers.get("Content-Type"), args.port)
            if not ok:
                self._json(403, {"error": "forbidden"})
            return ok

        def do_GET(self):
            if not self._allowed("GET"):
                return
            if self.path == "/":
                self._send(200, page, "text/html; charset=utf-8")
            elif self.path == "/api/items":
                verdicts = judge_lib.latest(args.out)
                self._json(200, {"items": items, "verdicts": verdicts, "summary": judge_lib.summarize(verdicts, len(items))})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self._allowed("POST"):
                return
            if self.path != "/api/judge":
                return self._json(404, {"error": "not found"})
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 10_000)))
                judge_lib.record(args.out, body["id"], body["verdict"], known, datetime.now().isoformat(timespec="seconds"))
            except (ValueError, KeyError, TypeError) as exc:
                return self._json(400, {"error": str(exc)})
            self._json(200, {"summary": judge_lib.summarize(judge_lib.latest(args.out), len(items))})

        def log_message(self, *_):
            pass

    print(f"judging {len(items)} findings at http://127.0.0.1:{args.port}/  (results: {args.out})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
