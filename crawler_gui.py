#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================ V1.0.2 · Tkinter 增强版 =================
微信公众号文章图片爬虫 · 桌面图形界面

V1.0.2 新增：
  · 文章分组：按文章标题自动建文件夹
  · 智能整理：下载图自动分 原图/封面/动图
  · 标题清洗：自动去除 emoji / 特殊符号
  · 剪贴板监听：复制公众号链接后自动填入链接框（纯本地，不上传）
  · HTTP API：可一键开启本地 API 供自动化工具调用（不影响主界面）

底层逻辑复用 crawler_core.py。
"""
import os
import sys
import io
import json
import queue
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "微信公众号文章图片爬虫 V1.0.2"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".image_crawler_v102_config.json")
DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "Desktop", "爬图")


class AbortError(Exception):
    pass


class QueueWriter(io.TextIOBase):
    encoding = "utf-8"

    def __init__(self, q):
        self.q = q
        self._buf = ""

    def write(self, s):
        if not s:
            return 0
        self._buf += str(s)
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self.q.put(("log", line))
        return len(s)

    def flush(self):
        if self._buf:
            self.q.put(("log", self._buf)); self._buf = ""

    def reconfigure(self, *a, **k):
        return self

    def isatty(self):
        return False


def load_config():
    default = {
        "out": DEFAULT_OUT, "min_bytes": "20000", "subfolder": "",
        "group": "1", "organize": "1", "clipboard": "0", "api": "0", "api_port": "8765",
    }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            default.update(json.load(f))
    except Exception:
        pass
    return default


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.running = False
        self.stop_event = threading.Event()
        self.cfg = load_config()
        self.api_server = None
        self.last_clip = ""

        root.title(APP_TITLE)
        root.geometry("940x760")
        root.minsize(780, 620)
        self._build_style()
        self._build_ui()
        self._apply_clipboard_setting()
        self.root.after(120, self._poll)

    def _build_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", font=("Microsoft YaHei UI", 10))
        st.configure("Title.TLabel", font=("Microsoft YaHei UI", 16, "bold"), foreground="#1a6d3a")
        st.configure("Ver.TLabel", font=("Microsoft YaHei UI", 9), foreground="#888888")
        st.configure("Hint.TLabel", font=("Microsoft YaHei UI", 9), foreground="#777777")
        st.configure("Run.TButton", font=("Microsoft YaHei UI", 11, "bold"))
        st.configure("Stop.TButton", font=("Microsoft YaHei UI", 10, "bold"), foreground="#b3261e")

    def _build_ui(self):
        root = self.root
        main = ttk.Frame(root, padding=(16, 12))
        main.pack(fill=tk.BOTH, expand=True)

        head = ttk.Frame(main); head.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(head, text="微信公众号文章图片爬虫", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(head, text="V1.0.2 增强版", style="Ver.TLabel").pack(side=tk.LEFT, padx=(12, 0), pady=(8, 0))

        f_out = ttk.LabelFrame(main, text=" 第 1 步  保存目录 ", padding=(10, 8))
        f_out.pack(fill=tk.X, pady=(0, 10))
        self.var_out = tk.StringVar(value=self.cfg["out"])
        ttk.Entry(f_out, textvariable=self.var_out).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(f_out, text="浏览…", command=self._choose_dir, width=9).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(f_out, text="打开目录", command=self._open_dir, width=10).pack(side=tk.LEFT)

        f_link = ttk.LabelFrame(main, text=" 第 2 步  文章链接（一行一个，可多条） ", padding=(10, 8))
        f_link.pack(fill=tk.X, pady=(0, 10))
        self.txt_links = tk.Text(f_link, height=4, wrap=tk.WORD, font=("Consolas", 10), relief=tk.SOLID, bd=1)
        self.txt_links.pack(fill=tk.X)
        self.txt_links.bind("<Control-Return>", self._ctrl_enter_newline)
        ttk.Label(f_link, text="仅支持微信公众号文章链接。一行一个，按 Ctrl+Enter 换行；开启剪贴板监听后复制链接会自动填入。",
                  style="Hint.TLabel").pack(anchor=tk.W, pady=(5, 0))

        # 智能选项
        f_opt = ttk.LabelFrame(main, text=" 智能选项 ", padding=(10, 8))
        f_opt.pack(fill=tk.X, pady=(0, 10))
        self.var_group = tk.StringVar(value=self.cfg["group"])
        self.var_organize = tk.StringVar(value=self.cfg["organize"])
        self.var_clip = tk.StringVar(value=self.cfg["clipboard"])
        self.var_api = tk.StringVar(value=self.cfg["api"])
        self.var_port = tk.StringVar(value=self.cfg["api_port"])
        row = ttk.Frame(f_opt); row.pack(fill=tk.X, pady=2)
        self._tick(row, "按文章标题分文件夹", self.var_group).pack(side=tk.LEFT)
        self._tick(row, "智能整理(原图/封面/动图)", self.var_organize).pack(side=tk.LEFT, padx=(16, 0))
        self._tick(row, "剪贴板监听(纯本地)", self.var_clip,
                   command=self._apply_clipboard_setting).pack(side=tk.LEFT, padx=(16, 0))
        row2 = ttk.Frame(f_opt); row2.pack(fill=tk.X, pady=2)
        self._tick(row2, "开启本地 HTTP API", self.var_api,
                   command=self._toggle_api).pack(side=tk.LEFT)
        ttk.Label(row2, text="端口:").pack(side=tk.LEFT, padx=(16, 0))
        ttk.Entry(row2, textvariable=self.var_port, width=8).pack(side=tk.LEFT)
        self.lbl_api = ttk.Label(row2, text="", style="Hint.TLabel")
        self.lbl_api.pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(f_opt, text="剪贴板监听仅在本机内存比对链接格式，不落盘、不联网、不上传任何数据。",
                  style="Hint.TLabel").pack(anchor=tk.W, pady=(5, 0))

        # 高级
        self.adv = ttk.LabelFrame(main, text=" 高级 ", padding=(10, 8))
        self.var_min = tk.StringVar(value=self.cfg["min_bytes"])
        self.var_sub = tk.StringVar(value=self.cfg["subfolder"])
        r = ttk.Frame(self.adv); r.pack(fill=tk.X)
        ttk.Label(r, text="图片最小字节:", width=18).pack(side=tk.LEFT)
        ttk.Entry(r, textvariable=self.var_min, width=10).pack(side=tk.LEFT)
        ttk.Label(r, text="固定子文件夹(选填):", width=20).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Entry(r, textvariable=self.var_sub, width=16).pack(side=tk.LEFT)

        f_btn = ttk.Frame(main); f_btn.pack(fill=tk.X, pady=(10, 8))
        self.btn_run = ttk.Button(f_btn, text="▶  立即运行", style="Run.TButton", command=self._run)
        self.btn_run.pack(side=tk.LEFT, ipadx=14, ipady=6)
        self.btn_stop = ttk.Button(f_btn, text="■  停止", style="Stop.TButton", command=self._stop,
                                   state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(10, 0), ipadx=8, ipady=6)
        ttk.Button(f_btn, text="清空日志", command=self._clear_log).pack(side=tk.RIGHT, ipadx=6, ipady=4)
        self.lbl_status = ttk.Label(f_btn, text="就绪", style="Hint.TLabel")
        self.lbl_status.pack(side=tk.LEFT, padx=(14, 0))

        f_log = ttk.LabelFrame(main, text=" 运行日志 ", padding=(6, 6))
        f_log.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(f_log, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 10),
                           bg="#fafafa", relief=tk.FLAT)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(f_log, command=self.log.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.configure(yscrollcommand=sb.set)
        self.log.tag_config("err", foreground="#c62828")
        self.log.tag_config("ok", foreground="#1b7f3a")
        self.log.tag_config("info", foreground="#1565c0")
        self.log.tag_config("dim", foreground="#888888")
        self._append_log("就绪。设置目录 → 粘贴链接 → 点「立即运行」。", "dim")

    @staticmethod
    def _tick(parent, label, var, command=None):
        """自定义勾选标签：选中显示 ✅，未选显示空白框 ☐（规避 ttk 主题勾标记渲染异常）。"""
        textvar = tk.StringVar()

        def refresh():
            textvar.set(("✅ " if var.get() == "1" else "☐ ") + label)

        def toggle(_event=None):
            var.set("0" if var.get() == "1" else "1")
            refresh()
            if command:
                command()

        var.trace_add("write", lambda *_: refresh())
        refresh()
        lbl = ttk.Label(parent, textvariable=textvar, cursor="hand2")
        lbl.bind("<Button-1>", toggle)
        return lbl

    def _ctrl_enter_newline(self, event):
        """Ctrl+Enter 在链接框插入换行。"""
        self.txt_links.insert(tk.INSERT, "\n")
        return "break"

    # ---------------- 交互 ----------------
    def _choose_dir(self):
        d = filedialog.askdirectory(title="选择图片保存目录", initialdir=self.var_out.get() or DEFAULT_OUT)
        if d:
            self.var_out.set(d)

    def _open_dir(self):
        d = self.var_out.get()
        if d and os.path.isdir(d):
            try:
                os.startfile(d)
            except Exception as e:
                messagebox.showwarning("提示", f"无法打开：{e}")
        else:
            messagebox.showinfo("提示", "目录尚不存在，运行后会自动创建。")

    def _clear_log(self):
        self.log.configure(state=tk.NORMAL); self.log.delete("1.0", tk.END); self.log.configure(state=tk.DISABLED)

    def _append_log(self, text, tag=None):
        self.log.configure(state=tk.NORMAL); self.log.insert(tk.END, text + "\n", tag)
        self.log.see(tk.END); self.log.configure(state=tk.DISABLED)

    def _set_running(self, on):
        self.running = on
        self.btn_run.configure(state=tk.DISABLED if on else tk.NORMAL)
        self.btn_stop.configure(state=tk.NORMAL if on else tk.DISABLED)
        self.lbl_status.configure(text="正在运行…" if on else "就绪")

    # ---------------- 剪贴板监听（纯本地） ----------------
    def _apply_clipboard_setting(self):
        if self.var_clip.get() == "1":
            self.last_clip = self._read_clipboard()
            self.root.after(800, self._check_clipboard)
            self._append_log("剪贴板监听已开启（纯本地，不上传）", "info")
        else:
            self._append_log("剪贴板监听已关闭", "dim")

    def _read_clipboard(self):
        try:
            return self.root.clipboard_get()
        except Exception:
            return ""

    def _check_clipboard(self):
        if self.var_clip.get() != "1":
            return
        txt = self._read_clipboard()
        if txt and txt != self.last_clip:
            self.last_clip = txt
            # 只识别微信公众号链接，纯本地正则匹配
            links = [ln.strip() for ln in txt.splitlines()
                     if "mp.weixin.qq.com/s" in ln and ln.strip()]
            if links:
                cur = self.txt_links.get("1.0", tk.END)
                added = [x for x in links if x not in cur]
                if added:
                    if cur.strip():
                        self.txt_links.insert(tk.END, "\n")
                    self.txt_links.insert(tk.END, "\n".join(added))
                    self._append_log(f"剪贴板检测到 {len(added)} 条微信链接，已自动填入", "info")
                    self.root.lift()
        self.root.after(800, self._check_clipboard)

    # ---------------- HTTP API ----------------
    def _toggle_api(self):
        if self.var_api.get() == "1":
            self._start_api()
        else:
            self._stop_api()

    def _start_api(self):
        if self.api_server and self.api_server.is_alive():
            return
        try:
            port = int(self.var_port.get().strip() or "8765")
            from api_server import start_server
            self.api_server = start_server(port, self.q)
            self.lbl_api.configure(text=f"已启动 :{port}")
            self._append_log(f"本地 API 已启动：http://127.0.0.1:{port}", "info")
        except Exception as e:
            self.var_api.set("0")
            self.lbl_api.configure(text="启动失败")
            messagebox.showwarning("API 启动失败", str(e))

    def _stop_api(self):
        if self.api_server:
            try:
                self.api_server.shutdown()
            except Exception:
                pass
            self.api_server = None
        self.lbl_api.configure(text="")
        self._append_log("本地 API 已停止", "dim")

    # ---------------- 运行 ----------------
    def _run(self):
        if self.running:
            return
        links = [ln.strip() for ln in self.txt_links.get("1.0", tk.END).splitlines() if ln.strip()]
        if not links:
            messagebox.showwarning("提示", "请先粘贴至少一条文章链接。"); return
        out = self.var_out.get().strip()
        if not out:
            messagebox.showwarning("提示", "请设置保存目录。"); return
        try:
            min_bytes = int(self.var_min.get().strip() or "20000")
        except ValueError:
            messagebox.showwarning("提示", "「图片最小字节」需填数字。"); return

        self.cfg.update({
            "out": out, "min_bytes": str(min_bytes), "subfolder": self.var_sub.get().strip(),
            "group": self.var_group.get(), "organize": self.var_organize.get(),
            "clipboard": self.var_clip.get(), "api": self.var_api.get(), "api_port": self.var_port.get(),
        })
        save_config(self.cfg)
        self._clear_log(); self._set_running(True); self.stop_event.clear()
        threading.Thread(
            target=self._work,
            args=(links, out, min_bytes, self.var_sub.get().strip(),
                  self.var_group.get() == "1", self.var_organize.get() == "1"),
            daemon=True,
        ).start()

    def _stop(self):
        if self.running:
            self.stop_event.set()
            self._append_log("⏹ 已请求停止，正在中断…", "err")
            self.btn_stop.configure(state=tk.DISABLED)

    def _work(self, links, out, min_bytes, subfolder, group, organize):
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = QueueWriter(self.q); sys.stderr = QueueWriter(self.q)
        total_saved = 0
        try:
            import crawler_core as cc
            save_dir = os.path.join(out, subfolder) if subfolder else out
            os.makedirs(save_dir, exist_ok=True)
            cc.log(f"保存目录：{save_dir}")
            for link in links:
                if self.stop_event.is_set():
                    raise AbortError()
                if cc.platform_of(link) != "wechat":
                    cc.log(f"⚠️ 跳过非微信链接：{link[:60]}")
                    continue
                cc.log(f"→ {link[:70]}")
                r = cc.crawl_wechat_ex(link, save_dir, min_bytes,
                                       group_by_article=group, smart_organize=organize,
                                       stop_event=self.stop_event)
                total_saved += r["saved"]
            self.q.put(("done", True, total_saved, save_dir))
        except AbortError:
            self.q.put(("log", "⏹ 已停止")); self.q.put(("done", False, None, None))
        except Exception:
            self.q.put(("log", "❌ 运行出错：" + traceback.format_exc()))
            self.q.put(("done", False, None, None))
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "log":
                    self._append_log(item[1], self._tag_of(item[1]))
                elif item[0] == "done":
                    self._set_running(False)
                    if item[1]:
                        messagebox.showinfo("完成", f"共保存 {item[2]} 张图片。\n目录：{item[3]}")
                elif item[0] == "api_task":
                    self._handle_api_task(item[1])
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def _handle_api_task(self, task):
        """处理来自本地 API 的抓取任务（线程安全：写回队列结果）。"""
        import crawler_core as cc
        links = task.get("links", [])
        out = task.get("out") or self.var_out.get().strip()
        try:
            min_bytes = int(task.get("min_bytes", 20000))
        except Exception:
            min_bytes = 20000
        saved = 0
        for link in links:
            if cc.platform_of(link) == "wechat":
                r = cc.crawl_wechat_ex(link, out, min_bytes, group_by_article=True, smart_organize=True)
                saved += r["saved"]
        task["result"] = {"ok": True, "saved": saved, "out": out}
        task["event"].set()

    @staticmethod
    def _tag_of(line):
        if any(k in line for k in ("❌", "失败", "出错", "异常", "停止")):
            return "err"
        if any(k in line for k in ("✅", "完成", "已保存")):
            return "ok"
        if any(k in line for k in ("→", "识别", "标题", "平台")):
            return "info"
        if line.startswith("["):
            return "dim"
        return None


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
