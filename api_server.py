#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V1.0.2 本地 HTTP API（可选启用，不影响小白界面）

仅监听 127.0.0.1，不对公网开放；无鉴权但仅限本机访问。
供高级用户 / 自动化工具调用，所有任务转交 GUI 主线程执行，线程安全。

接口：
  GET  /health                -> {"status":"ok","version":"1.0.2"}
  POST /crawl                 JSON: {"links":[...], "out":"", "min_bytes":20000}
                              -> {"ok":true,"saved":N,"out":"..."}
  GET  /openapi.json          -> OpenAPI 风格说明

启动：由 GUI 调用 start_server(port, queue) 在后台线程运行。
也可独立运行：python api_server.py --port 8765（独立模式直接用 crawler_core 抓取）。
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.0.2"


class _Handler(BaseHTTPRequestHandler):
    gui_queue = None     # 由 start_server 注入
    standalone = False   # 独立模式

    def log_message(self, fmt, *args):
        pass  # 静默，避免刷屏

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, {"status": "ok", "version": VERSION})
        elif self.path.startswith("/openapi.json"):
            self._send(200, {
                "openapi": "3.0.0",
                "info": {"title": "微信公众号图片爬虫本地 API", "version": VERSION},
                "paths": {
                    "/health": {"get": {"summary": "健康检查"}},
                    "/crawl": {"post": {"summary": "抓取文章图片",
                                        "body": {"links": ["微信文章链接"],
                                                 "out": "保存目录(可选)",
                                                 "min_bytes": 20000}}},
                },
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/crawl"):
            self._send(404, {"error": "not found"}); return
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            links = data.get("links", [])
            if isinstance(links, str):
                links = [links]
            if not links:
                self._send(400, {"error": "links 不能为空"}); return

            if self.standalone:
                import crawler_core as cc
                out = data.get("out") or cc.os.path.join(cc.os.path.expanduser("~"), "Desktop", "爬图")
                cc.os.makedirs(out, exist_ok=True)
                saved = 0
                for link in links:
                    if cc.platform_of(link) == "wechat":
                        r = cc.crawl_wechat_ex(link, out, int(data.get("min_bytes", 20000)))
                        saved += r["saved"]
                self._send(200, {"ok": True, "saved": saved, "out": out})
            else:
                import uuid
                task = {"links": links, "out": data.get("out", ""),
                        "min_bytes": data.get("min_bytes", 20000),
                        "event": threading.Event(), "result": None, "id": uuid.uuid4().hex}
                self.gui_queue.put(("api_task", task))
                if not task["event"].wait(timeout=300):
                    self._send(504, {"error": "任务超时"}); return
                self._send(200, task["result"] or {"ok": False, "error": "无结果"})
        except Exception as e:
            self._send(500, {"error": str(e)})


def start_server(port: int, gui_queue):
    """在后台线程启动本地服务器，返回 server 对象（可 .shutdown()）。"""
    handler = type("Handler", (_Handler,), {"gui_queue": gui_queue, "standalone": False})
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    srv.is_alive = lambda: t.is_alive()
    return srv


def main():
    import argparse
    ap = argparse.ArgumentParser(description="本地 API（独立模式）")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    handler = type("Handler", (_Handler,), {"standalone": True})
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    print(f"本地 API 已启动：http://127.0.0.1:{a.port}  (Ctrl+C 退出)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
