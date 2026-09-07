#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


UPSTREAM_BASE = os.environ.get("QWENCODE_PROXY_UPSTREAM_BASE", "http://127.0.0.1:8844/v1").rstrip("/")
PORT_FILE = os.environ.get("QWENCODE_PROXY_PORT_FILE")
MAX_TOKENS = int(os.environ.get("QWENCODE_PROXY_MAX_TOKENS", "512"))


def resolve_upstream_auth(client_auth: str | None) -> str | None:
    """Use the client bearer token, or the canonical RassyMind key."""
    if client_auth:
        return client_auth
    key = os.environ.get("QWENCODE_PROXY_API_KEY", "").strip()
    return f"Bearer {key}" if key else None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("qwencode-proxy: " + (fmt % args) + "\n")

    def do_GET(self) -> None:
        self.forward(None)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        self.forward(raw)

    def forward(self, raw: bytes | None) -> None:
        body = raw
        if self.path == "/v1/chat/completions" and raw:
            body = self.normalize_chat_body(raw)

        upstream_path = self.path
        if upstream_path.startswith("/v1/"):
            upstream_path = upstream_path[3:]
        url = f"{UPSTREAM_BASE}{upstream_path}"

        headers = {
            "Accept": self.headers.get("Accept", "application/json"),
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "X-Rassy-Client": self.headers.get("X-Rassy-Client", "qwencode"),
        }
        for name in ("X-Rassy-Use-Case", "X-Rassy-Workload", "X-Rassy-Domain", "X-Rassy-Session-ID", "X-Rassy-Deadline-Ms"):
            value = self.headers.get(name)
            if value:
                headers[name] = value
        auth = resolve_upstream_auth(self.headers.get("Authorization"))
        if auth:
            headers["Authorization"] = auth

        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=self.command,
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/event-stream" in content_type:
                    self.stream_sse(resp)
                else:
                    payload = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", content_type or "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            payload = json.dumps({"error": {"message": str(exc), "type": "proxy_error"}}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def normalize_chat_body(self, raw: bytes) -> bytes:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        current = data.get("max_tokens")
        if isinstance(current, int) and current > MAX_TOKENS:
            data["max_tokens"] = MAX_TOKENS
        return json.dumps(data, separators=(",", ":")).encode("utf-8")

    def stream_sse(self, resp) -> None:
        self.send_response(resp.status)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        saw_done = False
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                self.wfile.write(b"\n")
                self.wfile.flush()
                continue
            if not line.startswith("data:"):
                self.wfile.write(raw)
                self.wfile.flush()
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                saw_done = True
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                self.wfile.write(raw)
                self.wfile.flush()
                continue
            if not event.get("choices"):
                continue
            self.wfile.write(b"data: " + json.dumps(event, separators=(",", ":")).encode("utf-8") + b"\n\n")
            self.wfile.flush()
        if not saw_done:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()


def main() -> int:
    parsed = urlsplit(UPSTREAM_BASE)
    if parsed.scheme not in {"http", "https"}:
        raise SystemExit(f"unsupported upstream base: {UPSTREAM_BASE}")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    if PORT_FILE:
        Path(PORT_FILE).write_text(str(port), encoding="utf-8")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
