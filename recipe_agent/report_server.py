"""Local HTTP endpoint the n8n workflow calls to compile the dataset.

    python -m recipe_agent.report_server   # http://127.0.0.1:8765

GET /summary      dataset summary (JSON) for drafting the email
GET /report.pdf   the compiled PDF (also saved to output/recipe_dataset.pdf)
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import OUTPUT_DIR
from .report import build_pdf, load_dataset, summarize


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/summary":
            self._send(200, json.dumps(summarize(load_dataset())).encode(), "application/json")
        elif self.path == "/report.pdf":
            pdf = build_pdf(load_dataset())
            (OUTPUT_DIR / "recipe_dataset.pdf").write_bytes(pdf)
            self._send(200, pdf, "application/pdf",
                       {"Content-Disposition": 'attachment; filename="recipe_dataset.pdf"'})
        elif self.path == "/health":
            self._send(200, b'{"ok": true}', "application/json")
        else:
            self._send(404, b'{"error": "not found"}', "application/json")

    def log_message(self, fmt, *args):  # keep the console quiet; no request bodies are logged
        pass


def main() -> None:
    port = int(os.environ.get("REPORT_PORT", "8765"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
