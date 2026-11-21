#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信公众号文章原图爬虫 —— 图形界面前端。

底层抓图逻辑完全复用 crawler_macos.py，本文件只提供窗口与日志显示。
"""
import os
import sys
import queue
import threading
import contextlib
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

import crawler_macos as crawler


class GuiLog:
    """把 print 输出转发到队列，由主线程刷新到界面，避免多线程操作 Tk 组件。"""

    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(str(s))

    def flush(self):
        pass


class CrawlerApp:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.running = False

        root.title("微信爬图 · 公众号正文原图下载")
        root.geometry("780x580")
        root.minsize(660, 480)

        main = ttk.Frame(root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="微信文章链接（每行一条）：").pack(anchor=tk.W)
        self.url_text = tk.Text(main, height=4, wrap=tk.WORD)
        self.url_text.pack(fill=tk.X, pady=(4, 10))
        self.url_text.insert(tk.END, "\n".join(crawler.LINKS))

        dir_frame = ttk.Frame(main)
        dir_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(dir_frame, text="保存到：").pack(side=tk.LEFT)
        self.out_var = tk.StringVar(value=crawler.OUT_DIR)
        ttk.Entry(dir_frame, textvariable=self.out_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=6
        )
        ttk.Button(dir_frame, text="选择…", command=self.choose_dir, width=8).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        self.run_btn = ttk.Button(btn_frame, text="开始下载", command=self.start)
        self.run_btn.pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="打开保存目录", command=self.open_dir).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="清空日志", command=self.clear_log).pack(side=tk.LEFT)

        ttk.Label(main, text="运行日志：").pack(anchor=tk.W)
        self.log = scrolledtext.ScrolledText(main, height=16, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.status = tk.StringVar(value="就绪")
        ttk.Label(
            root, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3)
        ).pack(fill=tk.X)

        self.root.after(100, self.pump)

    def choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get())
        if d:
            self.out_var.set(d)

    def open_dir(self):
        path = self.out_var.get()
        os.makedirs(path, exist_ok=True)
        if sys.platform == "darwin":
            os.system('open "%s"' % path.replace('"', ''))

    def clear_log(self):
        self.log.delete("1.0", tk.END)

    def start(self):
        if self.running:
            return
        links = [x.strip() for x in self.url_text.get("1.0", tk.END).splitlines() if x.strip()]
        if not links:
            messagebox.showwarning("提示", "请先粘贴微信文章链接")
            return
        self.running = True
        self.run_btn.config(state=tk.DISABLED)
        self.status.set("正在下载…")
        self.clear_log()
        out = self.out_var.get().strip() or crawler.OUT_DIR
        threading.Thread(target=self.worker, args=(links, out), daemon=True).start()

    def worker(self, links, out):
        gui_log = GuiLog(self.q)
        try:
            os.makedirs(out, exist_ok=True)
            with contextlib.redirect_stdout(gui_log), contextlib.redirect_stderr(gui_log):
                seq = 1
                for url in links:
                    platform = crawler.platform_of(url)
                    print("[crawler] → 平台识别:", platform)
                    if platform == "wechat":
                        seq = crawler.crawl_wechat(url, out, crawler.MIN_BYTES, seq)
                    else:
                        print("[crawler] ⚠️ 暂不支持该链接，请提供微信公众号文章链接 (mp.weixin.qq.com/s/...)")
                print("[crawler] ✅ 完成，图片已保存到", out)
        except Exception as e:
            print("[crawler] ❌ 出错:", e)
        finally:
            self.q.put("__DONE__")

    def pump(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg == "__DONE__":
                    self.running = False
                    self.run_btn.config(state=tk.NORMAL)
                    self.status.set("完成")
                else:
                    self.log.insert(tk.END, msg)
                    self.log.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)


def main():
    root = tk.Tk()
    CrawlerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
