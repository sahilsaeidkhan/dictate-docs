"""Web UI for dictate-docs. Stdlib only (http.server).

Routes:
    GET  /            -> the single-page app
    GET  /api/status  -> {"backend", "model", "engine", "version"}
    POST /api/process -> {"output", "backend", "backend_info"}
                       body: {"mode": "commit|readme|polish",
                              "text": "...", "diff": "...",
                              "readme": "...", "project_name": "..."}
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _json(handler: BaseHTTPRequestHandler, payload: dict,
          status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "dictate-docs-web/0.1.0"

    def log_message(self, *args):  # quieter logs
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = (HERE / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif self.path == "/api/status":
            from dictate_docs import __version__, llm
            info = llm.backend_info()
            _json(self, {
                "version": __version__,
                "backend": info["backend"],
                "model": info["model"],
                "engine": info["engine"],
                "llm_configured": llm.is_llm_configured(),
            })
        else:
            self.send_error(404, "not found")

    def do_POST(self):
        if self.path != "/api/process":
            self.send_error(404, "not found")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            _json(self, {"error": "invalid JSON"}, 400)
            return
        mode = data.get("mode", "polish")
        try:
            from dictate_docs import pipeline
            result = pipeline.run(
                mode,
                data.get("text", ""),
                diff=data.get("diff"),
                readme_text=data.get("readme"),
                project_name=data.get("project_name"),
                backend=data.get("backend", "auto"),
            )
        except ValueError as e:
            _json(self, {"error": str(e)}, 400)
            return
        except Exception as e:  # never leak a traceback to the UI
            _json(self, {"error": f"processing failed: {e}"}, 500)
            return
        _json(self, result)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE.parent))
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"dictate-docs web UI on http://127.0.0.1:{port}")
    run_server(port=port)
