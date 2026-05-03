"""
队列服务 - 接收浏览器扩展发来的 URL，自动触发处理流程。
端口: 5679
收到 URL → 写入队列文件 → 后台线程自动处理（抓取 → 写飞书 → 发 IM）
"""
import os
import sys
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

QUEUE_FILE = os.path.expanduser("~/.claude/article-queue.txt")
PORT = 5679

# 确保 auto_process 可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def process_in_background(url):
    """后台线程处理 URL"""
    try:
        from auto_process import process
        process(url)
    except Exception as e:
        print(f"Error processing {url}: {e}", file=sys.stderr)
    finally:
        # 处理完清空队列
        try:
            with open(QUEUE_FILE, "w") as f:
                f.truncate(0)
        except Exception:
            pass


class QueueHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/queue":
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        url = body.get("url", "").strip()

        if not url:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "missing url"}).encode())
            return

        # 写入队列文件
        os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
        with open(QUEUE_FILE, "a") as f:
            entry = json.dumps({"url": url, "time": datetime.now().isoformat()}, ensure_ascii=False)
            f.write(entry + "\n")

        # 后台线程自动处理
        t = threading.Thread(target=process_in_background, args=(url,), daemon=True)
        t.start()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "auto": True}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}\n")


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), QueueHandler)
    print(f"Queue server running on http://127.0.0.1:{PORT}")
    print(f"Auto-process: enabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
