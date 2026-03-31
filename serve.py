"""
serve.py — HTTP 서버 실행 + 브라우저 자동 오픈
집계 재실행 없이 브라우저만 열고 싶을 때 사용
"""

import os
import sys
import webbrowser
import http.server
import socketserver
from pathlib import Path

PORT = 8000
ROOT = Path(__file__).parent


class SilentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        pass  # 콘솔 로그 최소화

    def address_string(self):
        # 역방향 DNS 조회 비활성화 → 응답 속도 정상화
        return self.client_address[0]


def serve(port: int = PORT, open_browser: bool = True) -> None:
    url = f"http://127.0.0.1:{port}/dashboard/"
    if open_browser:
        webbrowser.open(url)

    print(f"[서버 시작] {url}")
    print("종료: Ctrl+C")

    with socketserver.TCPServer(("127.0.0.1", port), SilentHandler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[서버 종료]")


if __name__ == '__main__':
    port = PORT
    if '--port' in sys.argv:
        idx = sys.argv.index('--port')
        port = int(sys.argv[idx + 1])
    serve(port)
