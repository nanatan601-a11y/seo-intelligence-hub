#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from seo_hub.core import (
    ROOT,
    backfill_sources,
    dashboard_data,
    experts_data,
    generate_weekly_report,
    init_db,
    list_articles,
    refresh_sources,
    save_source,
    source_list,
    update_article,
    update_source,
)


STATIC_DIR = ROOT / "static"
MAX_BODY_BYTES = 64 * 1024


class HubHandler(BaseHTTPRequestHandler):
    server_version = "SEOIntelligenceHub/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            if parsed.path == "/api/refresh":
                source_id = payload.get("source_id")
                result = refresh_sources(int(source_id) if source_id else None)
                self.send_json(result)
            elif parsed.path == "/api/sources":
                self.send_json(save_source(payload), HTTPStatus.CREATED)
            elif parsed.path == "/api/weekly":
                self.send_json(generate_weekly_report(bool(payload.get("use_ai", False))))
            else:
                self.send_json({"error": "API endpoint not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - last-resort API boundary
            traceback.print_exc()
            self.send_json({"error": f"Server error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_PATCH(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = self.read_json()
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 3 and parts[:2] == ["api", "sources"]:
                self.send_json(update_source(int(parts[2]), payload))
            elif len(parts) == 3 and parts[:2] == ["api", "articles"]:
                self.send_json(update_article(int(parts[2]), payload))
            else:
                self.send_json({"error": "API endpoint not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            self.send_json({"error": f"Server error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_api_get(self, parsed: urllib.parse.ParseResult) -> None:
        try:
            params = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/api/dashboard":
                self.send_json(dashboard_data())
            elif parsed.path == "/api/articles":
                self.send_json({"items": list_articles(params)})
            elif parsed.path == "/api/sources":
                self.send_json({"items": source_list()})
            elif parsed.path == "/api/experts":
                self.send_json({"items": experts_data()})
            elif parsed.path == "/api/health":
                self.send_json({"status": "ok"})
            else:
                self.send_json({"error": "API endpoint not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            self.send_json({"error": f"Server error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        length = int(raw_length)
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large")
        if length == 0:
            return {}
        body = self.rfile.read(length)
        value = json.loads(body.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, url_path: str) -> None:
        if url_path in {"", "/"}:
            path = STATIC_DIR / "index.html"
        else:
            relative = Path(urllib.parse.unquote(url_path).lstrip("/"))
            if ".." in relative.parts:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            path = STATIC_DIR / relative
            if not path.exists() or not path.is_file():
                path = STATIC_DIR / "index.html"
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Intelligence Hub")
    parser.add_argument("--host", default=os.environ.get("SEO_HUB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SEO_HUB_PORT", "8765")))
    parser.add_argument("--refresh", action="store_true", help="Refresh all enabled sources and exit")
    parser.add_argument("--weekly", action="store_true", help="Generate the local weekly brief and exit")
    parser.add_argument("--ai", action="store_true", help="Use OpenAI analysis with --weekly")
    parser.add_argument("--backfill-days", type=int, help="Backfill available feed history for N days and exit")
    args = parser.parse_args()

    init_db()
    if args.refresh:
        print(json.dumps(refresh_sources(), ensure_ascii=False, indent=2))
        return
    if args.weekly:
        print(json.dumps(generate_weekly_report(args.ai), ensure_ascii=False, indent=2))
        return
    if args.backfill_days:
        print(json.dumps(backfill_sources(args.backfill_days), ensure_ascii=False, indent=2))
        return

    server = ThreadingHTTPServer((args.host, args.port), HubHandler)
    print(f"SEO Intelligence Hub is running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
