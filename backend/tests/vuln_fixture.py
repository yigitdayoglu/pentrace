"""Test fixture — kasitli savunmasiz mini HTTP sunucusu (yalnizca localhost test icin).

vulnscan kontrollerini deterministik dogrulamak icin stdlib http.server kullanir.
  /                       -> parametreli link + form iceren ana sayfa (guvenlik basligi yok)
  /listproducts?cat=...   -> tek tirnak varsa SQL hata mesaji yansitir (SQLi error-based)
  /search?q=...           -> q parametresini kodlamadan yansitir (reflected XSS)
  /go?next=...            -> next degerine 302 yonlendirme (open redirect)
  /.env, /backup          -> 200 hassas dosya (dir brute)
"""
from __future__ import annotations

import http.server
import socketserver
from urllib.parse import parse_qs, urlparse

PORT = 8099


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # sessiz
        pass

    def _send(self, code: int, body: str, headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if path == "/":
            self._send(200,
                '<html><body><h1>Vuln Test</h1>'
                '<a href="/listproducts?cat=1">products</a>'
                '<a href="/search?q=hello">search</a>'
                '<a href="/go?next=/home">go</a>'
                '<form action="/search" method="get"><input name="q"></form>'
                '</body></html>')
        elif path == "/listproducts":
            cat = q.get("cat", "")
            if "'" in cat:
                self._send(200, "You have an error in your SQL syntax near '" + cat + "'")
            else:
                self._send(200, f"<html>Products in cat {cat}</html>")
        elif path == "/search":
            self._send(200, f"<html>Results for: {q.get('q','')}</html>")
        elif path == "/go":
            nxt = q.get("next", "/")
            self._send(302, "redirecting", {"Location": nxt})
        elif path in ("/.env", "/backup"):
            self._send(200, "SECRET=topsecret\nDB_PASSWORD=hunter2")
        else:
            self._send(404, "not found")


if __name__ == "__main__":
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"fixture listening on http://127.0.0.1:{PORT}")
        httpd.serve_forever()
