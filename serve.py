#!/usr/bin/env python3
"""Local preview that follows GitHub Pages' URL rules, so the site's clean URLs work.

    python3 serve.py [port]        # default 8123, on 127.0.0.1 only

- /heroes serves heroes.html (as Pages does); / serves index.html.
- A miss gets 404.html with a 404 status (as Pages does), including /heroes/ with a slash.
- Everything else is Python's plain static file server, from this folder.
"""
import http.server
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".avif": "image/avif", ".vtt": "text/vtt", ".mp4": "video/mp4", ".svg": "image/svg+xml",
        ".js": "text/javascript", ".woff2": "font/woff2",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path):
        p = super().translate_path(path)
        if not os.path.exists(p) and os.path.isfile(p + ".html"):
            return p + ".html"          # /heroes -> heroes.html
        return p

    def send_error(self, code, message=None, explain=None):
        page = ROOT / "404.html"
        if code != 404 or not page.is_file():
            return super().send_error(code, message, explain)
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler) as httpd:
        print(f"Fauna Fantasy site on http://127.0.0.1:{port}/ (Ctrl-C stops it)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
