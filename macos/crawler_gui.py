#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
======================== 微信公众号文章图片爬虫 · macOS 桌面图形界面 ========================
微信公众号文章正文原图爬虫的 GUI 外壳（macOS 版，仅源码，无需打包）。

运行方式：  python3 crawler_gui.py
  1. 选择「保存目录」（默认：桌面/爬图）
  2. 把公众号文章链接粘贴到「文章链接」框（一行一个，可多条）
  3. 点「立即运行」，日志会实时显示在下方

底层爬虫逻辑全部复用同目录的 crawler.py，本文件只负责界面与调度。
=====================================================================
"""
import os
import sys
import io
import json
import queue
import subprocess
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "微信公众号文章图片爬虫 (macOS)"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".image_crawler_gui_config.json")
DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "Desktop", "爬图")

# macOS 系统自带中文字体（苹方）与等宽字体（Menlo）
FONT_UI = "PingFang SC"
FONT_MONO = "Menlo"


class AbortError(Exception):
    """用户点击停止时抛出，用于中断爬虫循环。"""


class QueueWriter(io.TextIOBase):
    """把 print 的内容按行送进队列，供 GUI 线程安全地显示。"""
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
            self.q.put(("log", self._buf))
            self._buf = ""

    def reconfigure(self, *a, **k):
        # 兼容原爬虫里的 sys.stdout.reconfigure(encoding="utf-8")
        return self

    def isatty(self):
        return False


def load_config():
    default = {"out": DEFAULT_OUT, "min_bytes": "20000", "subfolder": ""}
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
        self.worker = None
        self.cfg = load_config()

        root.title(APP_TITLE)
        root.geometry("900x680")
        root.minsize(760, 560)

        self._build_style()
        self._build_ui()
        self.root.after(120, self._poll)

    # ---------- 样式 ----------
    def _build_style(self):
        st = ttk.Style()
        try:
            st.theme_use("aqua")  # macOS 原生主题
        except Exception:
            try:
                st.theme_use("clam")
            except Exception:
                pass
        st.configure(".", font=(FONT_UI, 13))
        st.configure("Title.TLabel", font=(FONT_UI, 19, "bold"),
                     foreground="#1a6d3a")
        st.configure("Hint.TLabel", font=(FONT_UI, 11),
                     foreground="#777777")
        st.configure("Run.TButton", font=(FONT_UI, 14, "bold"))
        st.configure("Stop.TButton", font=(FONT_UI, 13, "bold"),
                     foreground="#b3261e")

    # ---------- 界面 ----------
    def _build_ui(self):
        root = self.root
        main = ttk.Frame(root, padding=(16, 12, 16, 12))
        main.pack(fill=tk.BOTH, expand=True)

        # 标题
        head = ttk.Frame(main)
        head.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(head, text="微信公众号文章图片爬虫", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(head, text="正文原图一键下载",
                  style="Hint.TLabel").pack(side=tk.LEFT, padx=(14, 0), pady=(6, 0))

        # ---- 保存目录 ----
        f_out = ttk.LabelFrame(main, text=" 第 1 步  保存目录 ", padding=(10, 8))
        f_out.pack(fill=tk.X, pady=(0, 10))
        self.var_out = tk.StringVar(value=self.cfg["out"])
        e_out = ttk.Entry(f_out, textvariable=self.var_out)
        e_out.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(f_out, text="浏览…", command=self._choose_dir, width=9).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(f_out, text="打开目录", command=self._open_dir, width=10).pack(side=tk.LEFT)

        # ---- 链接 ----
        f_link = ttk.LabelFrame(main, text=" 第 2 步  文章链接（一行一个，可多条） ", padding=(10, 8))
        f_link.pack(fill=tk.X, pady=(0, 10))
        self.txt_links = tk.Text(f_link, height=4, wrap=tk.WORD,
                                 font=(FONT_MONO, 13), relief=tk.SOLID, bd=1)
        self.txt_links.pack(fill=tk.X)
        ttk.Label(f_link, text="仅支持微信公众号文章链接，例如：https://mp.weixin.qq.com/s/...",
                  style="Hint.TLabel").pack(anchor=tk.W, pady=(5, 0))

        # ---- 高级选项（默认折叠） ----
        self.adv_visible = tk.BooleanVar(value=False)
        adv_head = ttk.Frame(main)
        adv_head.pack(fill=tk.X)
        ttk.Label(adv_head, text="高级选项", style="Hint.TLabel").pack(side=tk.LEFT)
        self.adv_btn = ttk.Label(adv_head, text="展开 ▾", style="Hint.TLabel", cursor="hand2")
        self.adv_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.adv_btn.bind("<Button-1>", self._toggle_adv)

        self.adv = ttk.LabelFrame(main, text=" 高级选项 ", padding=(10, 8))
        self.var_min = tk.StringVar(value=str(self.cfg["min_bytes"]))
        self.var_sub = tk.StringVar(value=self.cfg["subfolder"])

        row2 = ttk.Frame(self.adv); row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="图片最小大小(字节):", width=26).pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.var_min, width=12).pack(side=tk.LEFT)
        ttk.Label(row2, text="子文件夹名(选填):", width=18).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Entry(row2, textvariable=self.var_sub, width=18).pack(side=tk.LEFT)
        ttk.Label(self.adv, text="图片太小会被跳过（默认 20000 字节）；子文件夹留空则直接存到保存目录。",
                  style="Hint.TLabel").pack(anchor=tk.W, pady=(5, 0))

        # ---- 操作按钮 ----
        f_btn = ttk.Frame(main)
        f_btn.pack(fill=tk.X, pady=(10, 8))
        self.f_btn = f_btn
        self.btn_run = ttk.Button(f_btn, text="▶  立即运行", style="Run.TButton",
                                  command=self._run)
        self.btn_run.pack(side=tk.LEFT, ipadx=14, ipady=6)
        self.btn_stop = ttk.Button(f_btn, text="■  停止", style="Stop.TButton",
                                   command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(10, 0), ipadx=8, ipady=6)
        ttk.Button(f_btn, text="清空日志", command=self._clear_log).pack(side=tk.RIGHT, ipadx=6, ipady=4)
        self.lbl_status = ttk.Label(f_btn, text="就绪", style="Hint.TLabel")
        self.lbl_status.pack(side=tk.LEFT, padx=(14, 0))

        # ---- 日志区 ----
        f_log = ttk.LabelFrame(main, text=" 运行日志 ", padding=(6, 6))
        f_log.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(f_log, wrap=tk.WORD, state=tk.DISABLED,
                           font=(FONT_MONO, 12), bg="#fafafa", relief=tk.FLAT)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(f_log, command=self.log.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.configure(yscrollcommand=sb.set)
        self.log.tag_config("err", foreground="#c62828")
        self.log.tag_config("ok", foreground="#1b7f3a")
        self.log.tag_config("info", foreground="#1565c0")
        self.log.tag_config("dim", foreground="#888888")

        self._append_log("就绪。选择保存目录 → 粘贴链接 → 点击「立即运行」。", "dim")

    # ---------- 交互 ----------
    def _toggle_adv(self, event=None):
        if self.adv_visible.get():
            self.adv.pack_forget()
            self.adv_btn.configure(text="展开 ▾")
            self.adv_visible.set(False)
        else:
            self.adv.pack(fill=tk.X, pady=(6, 10), before=self.f_btn)
            self.adv_btn.configure(text="收起 ▴")
            self.adv_visible.set(True)

    def _choose_dir(self):
        d = filedialog.askdirectory(title="选择图片保存目录",
                                    initialdir=self.var_out.get() or DEFAULT_OUT)
        if d:
            self.var_out.set(d)

    def _open_dir(self):
        d = self.var_out.get()
        if d and os.path.isdir(d):
            try:
                subprocess.run(["open", d], check=False)  # macOS 用 open 命令打开目录
            except Exception as e:
                messagebox.showwarning("提示", f"无法打开目录：{e}")
        else:
            messagebox.showinfo("提示", "目录尚不存在，运行爬虫后会自动创建。")

    def _clear_log(self):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def _set_running(self, on):
        self.running = on
        self.btn_run.configure(state=tk.DISABLED if on else tk.NORMAL)
        self.btn_stop.configure(state=tk.NORMAL if on else tk.DISABLED)
        self.lbl_status.configure(text="正在运行…" if on else "就绪")

    # ---------- 运行 ----------
    def _run(self):
        if self.running:
            return
        links = [ln.strip() for ln in self.txt_links.get("1.0", tk.END).splitlines() if ln.strip()]
        if not links:
            messagebox.showwarning("提示", "请先粘贴至少一条文章链接。")
            return
        out = self.var_out.get().strip()
        if not out:
            messagebox.showwarning("提示", "请设置保存目录。")
            return
        try:
            min_bytes = int(self.var_min.get().strip() or "20000")
        except ValueError:
            messagebox.showwarning("提示", "「图片最小大小」需要填数字。")
            return

        self.cfg.update({
            "out": out,
            "min_bytes": str(min_bytes),
            "subfolder": self.var_sub.get().strip(),
        })
        save_config(self.cfg)

        self._clear_log()
        self._set_running(True)
        self.stop_event.clear()
        self.worker = threading.Thread(
            target=self._work,
            args=(links, out, min_bytes, self.var_sub.get().strip()),
            daemon=True,
        )
        self.worker.start()

    def _stop(self):
        if self.running:
            self.stop_event.set()
            self._append_log("⏹  已请求停止，正在中断…", "err")
            self.btn_stop.configure(state=tk.DISABLED)

    def _work(self, links, out, min_bytes, subfolder):
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = QueueWriter(self.q)
        sys.stderr = QueueWriter(self.q)
        try:
            import crawler as cw

            # 用带「停止检查」的 log 替换模块内的 log；爬虫每次打日志都会走到这里
            real_log = cw.log

            def guarded_log(*a):
                if self.stop_event.is_set():
                    raise AbortError()
                real_log(*a)

            cw.log = guarded_log

            save_dir = out
            if subfolder:
                save_dir = os.path.join(out, subfolder)
            os.makedirs(save_dir, exist_ok=True)

            cw.log(f"保存目录：{save_dir}")
            seq = 1
            for link in links:
                if self.stop_event.is_set():
                    raise AbortError()
                platform = cw.platform_of(link)
                if platform == "wechat":
                    cw.log(f"→ 微信公众号文章  {link[:70]}")
                    seq = cw.crawl_wechat(link, save_dir, min_bytes, seq)
                else:
                    cw.log(f"⚠️ 跳过：不是微信公众号文章链接  {link[:70]}")

            total = len([n for n in os.listdir(save_dir)
                         if n.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))])
            cw.log(f"✅ 全部完成！目录内现有图片 {total} 张：{save_dir}")
            self.q.put(("done", True, total, save_dir))
        except AbortError:
            self.q.put(("log", "⏹  已停止。"))
            self.q.put(("done", False, None, None))
        except Exception:
            self.q.put(("log", "❌ 运行出错：" + traceback.format_exc()))
            self.q.put(("done", False, None, None))
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    # ---------- 队列轮询（GUI 线程） ----------
    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._append_log(item[1], self._tag_of(item[1]))
                elif kind == "done":
                    self._set_running(False)
                    if item[1]:
                        messagebox.showinfo("完成", f"图片已保存到：\n{item[3]}")
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    @staticmethod
    def _tag_of(line):
        if any(k in line for k in ("❌", "失败", "出错", "异常", "停止")):
            return "err"
        if any(k in line for k in ("✅", "完成", "已保存")):
            return "ok"
        if any(k in line for k in ("→", "识别", "平台")):
            return "info"
        if line.startswith("["):
            return "dim"
        return None

    def _append_log(self, text, tag=None):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n", tag)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)


def _probe():
    """隐藏自检：验证爬虫依赖与抓图链路可用（正常启动不会触发）。"""
    report = os.path.join(os.path.expanduser("~"), ".image_crawler_probe.txt")
    lines = []
    logf = open(os.path.join(os.path.expanduser("~"), ".image_crawler_probe_log.txt"),
                "w", encoding="utf-8")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = logf
    try:
        import crawler as cw
        lines.append("IMPORT_OK")
        out = os.path.join(os.path.expanduser("~"), "_image_crawler_probe_out")
        os.makedirs(out, exist_ok=True)
        seq = cw.crawl_wechat("https://mp.weixin.qq.com/s/p5UsmtEvSMFoTd7drG_4OA",
                              out, 20000, 1)
        n = len([f for f in os.listdir(out)
                 if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))])
        lines.append(f"DOWNLOADED={n}")
        lines.append(f"SEQ={seq}")
    except Exception:
        lines.append("ERROR:\n" + traceback.format_exc())
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        logf.close()
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


def main():
    if "--probe" in sys.argv:
        _probe()
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
