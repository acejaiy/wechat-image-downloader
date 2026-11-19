#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
======================== V1.0.2 增强核心 ========================
微信公众号文章正文原图爬虫 · 核心模块（纯 HTTP，不启动浏览器）
GUI / 本地 API 共用此核心。

相对基础版新增：
  · extract_article_title()  提取文章标题
  · sanitize_title()         清洗标题：去除 emoji / 半角符号 / 特殊符号，仅留中文/字母/数字/常用中文标点
  · classify_image()         图片智能分类：原图 / 封面 / 动图
  · crawl_wechat_ex()        增强抓取：支持文章分组(按标题建目录)、智能整理(原图/封面/动图子目录)
                             返回结构化结果，供 GUI / Web / API 共用

依赖: pillow（可选但建议，用于黑图/纯色过滤与 gif 判定）
隐私: 纯本地运行，所有网络请求仅指向微信文章页与微信图床(qpic.cn)，不上传任何数据。
============================================================
"""
import os
import re
import sys
import gzip
import hashlib
import urllib.request
import urllib.error
from io import BytesIO

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore
        sys.stderr.reconfigure(encoding="utf-8")  # pyright: ignore
    except Exception:
        try:
            os.environ["PYTHONIOENCODING"] = "utf-8"
        except Exception:
            pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
REFERER = "https://mp.weixin.qq.com/"

MIN_BYTES = 20_000
CHECK_SOLID = True
PLACEHOLDER = b"\xe6\xad\xa4\xe5\x9b\xbe\xe7\x89\x87\xe6\x9d\xa5\xe8\x87\xaa"  # 此图片来自

# 智能整理子目录名
KIND_ORIGINAL = "原图"
KIND_COVER = "封面"
KIND_GIF = "动图"


def log(*a):
    print("[core]", *a)


# ------------------------------------------------------------------ 标题清洗
_FULLWIDTH_PUNCT = set("（）【】《》、，。！？：；—·-— ")
_KEEP_PUNCT = set("（）【】《》、，。！？：；—· ")


def sanitize_title(title: str, max_len: int = 60) -> str:
    """清洗文章标题，去除系统/本地无法识别的字符。
    规则：仅保留 中文 / 字母 / 数字 / 常用中文标点；丢弃 emoji、半角符号、特殊符号。
    连续空白合并为单空格，超长截断。结果为空时返回 '未命名文章'。
    """
    if not title:
        return "未命名文章"
    chars = []
    for ch in title:
        cp = ord(ch)
        # emoji 与各类符号平面：直接丢弃
        if 0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF or 0xFE00 <= cp <= 0xFE0F:
            continue
        if ("\u4e00" <= ch <= "\u9fff") or ch.isalnum():
            chars.append(ch)
        elif ch in _KEEP_PUNCT:
            chars.append(ch)
        # 其余（半角标点、特殊符号、不可见字符）一律丢弃
    s = "".join(chars)
    s = re.sub(r"\s+", " ", s).strip(" -—")
    s = s[:max_len].rstrip()
    return s or "未命名文章"


def extract_article_title(html: str) -> str:
    """从微信文章 HTML 提取标题，多来源按优先级回退。"""
    patterns = [
        r"var\s+msg_title\s*=\s*['\"](.*?)['\"]",
        r"msg_title\s*[:=]\s*['\"](.*?)['\"]",
        r'<meta\s+property="og:title"\s+content="([^"]+)"',
        r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>',
        r"<title>(.*?)</title>",
    ]
    for p in patterns:
        m = re.search(p, html, re.S | re.I)
        if m:
            t = re.sub(r"<[^>]+>", "", m.group(1))
            t = (t.replace("&amp;", "&").replace("&quot;", '"')
                  .replace("&#39;", "'").replace("&nbsp;", " ").strip())
            if t:
                return t
    return ""


# ------------------------------------------------------------------ URL 工具
def ext_of(ct: str) -> str:
    ct = (ct or "").lower()
    if "png" in ct:
        return "png"
    if "gif" in ct:
        return "gif"
    return "jpg"


def wechat_clean(url: str) -> str:
    """去掉 webp / 懒加载参数，强制服务器返回 jpg/png 原图。"""
    u = re.sub(r"[?&]tp=(webp|avif)", "", url, flags=re.I)
    u = re.sub(r"[?&]wx_lazy=\d+", "", u, flags=re.I)
    u = re.sub(r"[?&]retryload=\d+", "", u, flags=re.I)
    u = re.sub(r"\?&", "?", u).rstrip("?&")
    return u


def wechat_original(url: str) -> str:
    """/640 → /0，尝试请求服务器原图。"""
    return re.sub(r"/(\d+)(?=[?#]|$)", "/0", url)


def is_solid_or_black(body: bytes) -> bool:
    """用 pillow 判断近全黑 / 几乎纯色的占位图。无 pillow 返回 False。"""
    if not CHECK_SOLID:
        return False
    try:
        from PIL import Image  # pyright: ignore
    except Exception:
        return False
    try:
        img = Image.open(BytesIO(body)).convert("RGB")
        w, h = img.size
        if w <= 0 or h <= 0:
            return False
        black, n = 0, 0
        colors = set()
        step = max(1, (w * h) // 2000)
        for i, (r, g, b) in enumerate(img.getdata()):  # pyright: ignore
            if i % step:
                continue
            n += 1
            if r < 16 and g < 16 and b < 16:
                black += 1
            colors.add((r // 16, g // 16, b // 16))
        if n == 0:
            return False
        return black / n > 0.92 or len(colors) <= 2
    except Exception:
        return False


def classify_image(url: str, ct: str, og_url: str = "") -> str:
    """智能分类：动图(gif) / 封面(与 og:image 一致) / 原图(其余)。"""
    if "gif" in (ct or "").lower() or re.search(r"wx_fmt=gif|\.gif", url, re.I):
        return KIND_GIF
    if og_url and _same_image(url, og_url):
        return KIND_COVER
    return KIND_ORIGINAL


def _same_image(a: str, b: str) -> bool:
    def norm(u):
        return re.sub(r"/\d+(?=[?#]|$)", "/0", u.replace("http://", "https://")).split("?")[0]
    return norm(a) == norm(b)


def platform_of(url: str) -> str:
    u = url.lower()
    if "weixin" in u or "mp.weixin" in u:
        return "wechat"
    return "other"


# ------------------------------------------------------------------ 网络
def _http_get(url: str, referer: str = REFERER, timeout: int = 45, retries: int = 1):
    """带浏览器请求头的 GET，返回 (bytes, content-type)。gzip 解压、超时重试、SSL 降级。"""
    import ssl
    import socket
    import time
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/jpeg,image/png,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)

    def once(ctx=None):
        return urllib.request.urlopen(req, timeout=timeout, context=ctx) if ctx else urllib.request.urlopen(req, timeout=timeout)

    for attempt in range(retries + 1):
        resp = None
        try:
            resp = once()
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if "CERTIFICATE_VERIFY_FAILED" in str(e) or isinstance(reason, ssl.SSLError):
                log("SSL 校验失败，降级免校验重试")
                try:
                    resp = once(ssl._create_unverified_context())
                except Exception as e2:
                    if attempt < retries:
                        time.sleep(0.6 * (attempt + 1)); continue
                    raise e2
            elif attempt < retries:
                time.sleep(0.6 * (attempt + 1)); continue
            else:
                raise
        except (socket.timeout, TimeoutError):
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1)); continue
            raise
        if resp is None:
            raise RuntimeError("empty response")
        with resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                body = gzip.decompress(body)
            return body, resp.headers.get("Content-Type", "")


# ------------------------------------------------------------------ 图片提取
def extract_wechat_images(html: str):
    """从文章 HTML 提取正文原图 URL（保序去重）+ 封面 og:image。
    返回 (urls: list[str], og_url: str, how: str)
    """
    def uniq(seq):
        seen, out = set(), []
        for u in seq:
            u = u.replace("\\/", "/")
            if u.startswith("//"):
                u = "https:" + u
            if u not in seen and re.search(r"[A-Za-z0-9.-]*qpic\.cn", u):
                seen.add(u); out.append(u)
        return out

    og = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    og_url = og.group(1).replace("\\/", "/") if og else ""

    key = "picture_page_info_list"
    if key in html:
        seg = html[html.find(key): html.find(key) + 200000]
        results = []
        for m in re.finditer(r"cdn_url:\s*'([^']*[A-Za-z0-9.-]*qpic\.cn[^']*)'", seg):
            if "watermark_info" in seg[max(0, m.start() - 80):m.start()]:
                continue
            results.append(m.group(1))
        got = uniq(results)
        if got:
            return got, og_url, "picture_page_info_list(图片消息)"

    imgs = re.findall(r"<img[^>]*?\b(?:data-src|data-original|src)\s*=\s*['\"]([^'\"]*[A-Za-z0-9.-]*qpic\.cn[^'\"]*)['\"]", html)
    got = uniq(imgs)
    if got:
        return got, og_url, "img标签(普通图文)"

    allq = re.findall(r"https?://[A-Za-z0-9.-]*qpic\.cn/[A-Za-z0-9_/\-]+", html)
    bad = ("headimg", "qrcode", "round_head", "logo", "avatar")
    fallback = [u for u in allq if not any(b in u.lower() for b in bad)]
    return uniq(fallback), og_url, "全文兜底"


def existing_hashes(out_dir: str) -> set:
    hashes = set()
    try:
        for name in os.listdir(out_dir):
            if not name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                continue
            try:
                with open(os.path.join(out_dir, name), "rb") as f:
                    hashes.add(hashlib.md5(f.read()).hexdigest())
            except Exception:
                pass
    except Exception:
        pass
    return hashes


def _next_index(out_dir: str, start: int) -> int:
    n = start
    while any(os.path.exists(os.path.join(out_dir, f"{n:03d}.{e}"))
              for e in ("jpg", "jpeg", "png", "gif", "webp")):
        n += 1
    return n


# ------------------------------------------------------------------ 增强抓取主函数
def crawl_wechat_ex(
    link: str,
    out_dir: str,
    min_bytes: int = MIN_BYTES,
    *,
    group_by_article: bool = True,
    smart_organize: bool = True,
    sanitize: bool = True,
    stop_event=None,
    start_index: int = 1,
    on_log=None,
) -> dict:
    """增强抓取。返回结构化结果 dict：
    {
      'ok': bool, 'title': str, 'folder': str, 'found': int,
      'saved': int, 'skipped': int, 'by_kind': {'原图':n,'封面':n,'动图':n},
      'files': [相对路径...], 'error': str|''
    }
    """
    emit = on_log or log

    def _stopped():
        return bool(stop_event and stop_event.is_set())

    result = {"ok": False, "title": "", "folder": "", "found": 0, "saved": 0,
              "skipped": 0, "by_kind": {KIND_ORIGINAL: 0, KIND_COVER: 0, KIND_GIF: 0},
              "files": [], "error": ""}
    try:
        emit(f"抓取文章 HTML：{link[:90]}")
        html_bytes, _ = _http_get(link)
        html = html_bytes.decode("utf-8", "ignore")
        if len(html) < 5000:
            result["error"] = "文章页面内容异常(可能被反爬)"
            emit("❌ " + result["error"]); return result

        raw_title = extract_article_title(html)
        title = sanitize_title(raw_title) if sanitize else (raw_title or "未命名文章")
        result["title"] = title
        emit(f"文章标题：{title}")

        urls, og_url, how = extract_wechat_images(html)
        result["found"] = len(urls)
        emit(f"通过 [{how}] 识别正文图 {len(urls)} 张")
        if not urls:
            result["error"] = "未提取到正文图片"
            emit("⚠️ " + result["error"]); return result

        # 目录结构：out_dir / [文章标题/] / [原图|封面|动图/]
        article_dir = os.path.join(out_dir, title) if group_by_article else out_dir
        kind_dirs = {}
        for kind in (KIND_ORIGINAL, KIND_COVER, KIND_GIF):
            d = os.path.join(article_dir, kind) if smart_organize else article_dir
            kind_dirs[kind] = d
            os.makedirs(d, exist_ok=True)
        if not smart_organize:
            os.makedirs(article_dir, exist_ok=True)
        result["folder"] = article_dir

        seen = set()
        for d in set(kind_dirs.values()):
            seen |= existing_hashes(d)

        seq = start_index
        for u in urls:
            if _stopped():
                result["error"] = "用户停止"; emit("⏹ 已停止"); return result
            u = wechat_clean(u)
            orig = wechat_original(u)
            body = ct = None
            if orig != u:
                try:
                    body, ct = _http_get(orig)
                except Exception as e:
                    emit(f"  原图(/0)失败，回退压缩版：{str(e)[:40]}")
            if body is None:
                try:
                    body, ct = _http_get(u)
                except Exception as e:
                    emit(f"  下载失败：{str(e)[:50]}")
                    result["skipped"] += 1; continue
            if "webp" in (ct or "") or "avif" in (ct or ""):
                emit("  跳过 webp/avif"); result["skipped"] += 1; continue
            if not body or len(body) < min_bytes:
                emit(f"  跳过小图({len(body)}B)"); result["skipped"] += 1; continue
            if PLACEHOLDER in body or is_solid_or_black(body):
                emit("  跳过占位/黑图"); result["skipped"] += 1; continue
            digest = hashlib.md5(body).hexdigest()
            if digest in seen:
                result["skipped"] += 1; continue
            seen.add(digest)

            kind = classify_image(u, ct, og_url)
            d = kind_dirs[kind]
            seq = _next_index(d, seq)
            ext = ext_of(ct)
            fname = f"{seq:03d}.{ext}"
            with open(os.path.join(d, fname), "wb") as f:
                f.write(body)
            rel = os.path.relpath(os.path.join(d, fname), out_dir)
            result["files"].append(rel)
            result["by_kind"][kind] += 1
            result["saved"] += 1
            emit(f"  已保存 [{kind}] {rel} ({len(body)//1024}KB)")

        result["ok"] = True
        emit(f"✅ 文章完成：识别 {result['found']} 张，保存 {result['saved']} 张，"
             f"跳过 {result['skipped']} 张")
    except Exception as e:
        result["error"] = str(e)
        emit("❌ 运行出错：" + str(e))
    return result


# ------------------------------------------------------------------ 兼容旧接口
def crawl_wechat(link, out_dir, min_bytes, start_index=1) -> int:
    """兼容 v1.0 调用签名（GUI 旧版用），返回下一个序号。"""
    r = crawl_wechat_ex(link, out_dir, min_bytes, group_by_article=False,
                        smart_organize=False, start_index=start_index)
    return start_index + r["saved"]
