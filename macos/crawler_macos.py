#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
======================== macOS 版 ========================
【纯 HTTP 版】微信公众号文章 图片爬虫
依赖: pillow（可选但强烈建议: pip install pillow，用于识别并丢弃「黑图/纯色占位图」）

【macOS 版说明】
  · 保存路径默认指向 macOS 桌面：~/Desktop/爬图
  · 仅提供源码，无需打包；用系统自带 Python 3 即可运行（见 README）
========================================================

【抓图原理】
  纯 HTTP 抓文章 HTML → 正则提取正文原图 → 带 Referer 逐张下载。
  不启动浏览器，不受无头检测 / 懒加载 / 页面结构变化影响。
  微信正文图内嵌在 JS 变量 picture_page_info_list 的 cdn_url 字段里，
  页面没有 <img> 标签也没有 #js_content 容器，走 DOM 会抓空，故用纯 HTTP。

【保存位置】默认存到 ~/Desktop/爬图（见配置区 OUT_DIR）。

【用法 - 直接在代码里贴链接】把链接填进 LINKS 列表，然后运行：python3 crawler_macos.py
【用法 - 命令行】python3 crawler_macos.py --url <链接> [--out 目录] [--min-bytes 20000]
"""
import os
import re
import gzip
import argparse
import hashlib
import urllib.request
import urllib.error
from io import BytesIO

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# ================= 配置区：在这里贴链接、改保存位置 =================
LINKS = [
    "https://mp.weixin.qq.com/s/p5UsmtEvSMFoTd7drG_4OA"
]

# 保存位置：默认 macOS 桌面「爬图」文件夹（~ 自动展开为当前用户主目录）
# 想改别处，直接换成自己的完整路径即可，例如 OUT_DIR = "/Users/你的名字/Pictures/微信"
OUT_DIR = os.path.expanduser("~/Desktop/爬图")

# 留空 = 图片直接躺在 OUT_DIR 根目录；填个名字则建子文件夹，
# 例如 SAVE_IN_SUBFOLDER = "微信图片" -> ~/desktop/爬图/微信图片/
SAVE_IN_SUBFOLDER = ""

MIN_BYTES = 20_000           # 微信正文图常被压到 20~80KB，100KB 会大量误杀，故降到 20KB
CHECK_SOLID = True           # 是否启用「黑图/纯色占位图」像素检测（需 pillow，强烈建议开启）
# =======================================================


def log(*a):
    print("[crawler]", *a)


PLACEHOLDER = b"\xe6\xad\xa4\xe5\x9b\xbe\xe7\x89\x87\xe6\x9d\xa5\xe8\x87\xaa"  # 此图片来自


def ext_of(ct: str) -> str:
    ct = ct.lower()
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
    """把图片 URL 路径末段的尺寸档位（如 /640）换成 /0，尝试请求服务器原图。
    微信图床 URL 形如 .../mmbiz_jpg/<HASH>/640?wx_fmt=jpeg，/0 通常返回未压缩原图
    （字节更大、更清晰）。只替换路径里的纯数字档位，不影响 query 参数。
    取不到时由调用方回退到原始 URL，保证单张失败不拖垮整篇。"""
    return re.sub(r"/(\d+)(?=[?#]|$)", "/0", url)


def is_solid_or_black(body: bytes) -> bool:
    """用 pillow 判断图片是否「近全黑」或「几乎纯色」(占位/黑图)。无 pillow 时返回 False。"""
    if not CHECK_SOLID:
        return False
    try:
        from PIL import Image  # pyright: ignore[reportMissingImports]
    except Exception:
        return False
    try:
        img = Image.open(BytesIO(body)).convert("RGB")
        w, h = img.size
        if w <= 0 or h <= 0:
            return False
        n, black = 0, 0
        colors = set()
        step = max(1, (w * h) // 2000)
        for i, (r, g, b) in enumerate(img.getdata()):  # pyright: ignore[reportArgumentType]
            if i % step:
                continue
            n += 1
            if r < 16 and g < 16 and b < 16:
                black += 1
            colors.add((r // 16, g // 16, b // 16))
        if n == 0:
            return False
        if black / n > 0.92:
            return True
        if len(colors) <= 2:
            return True
        return False
    except Exception:
        return False


def platform_of(url: str) -> str:
    """只识别微信公众号链接，其余返回 other 以便调用方给出提示。"""
    u = url.lower()
    if "weixin" in u or "mp.weixin" in u:
        return "wechat"
    return "other"


def next_index(out_dir: str, start: int) -> int:
    n = start
    while any(os.path.exists(os.path.join(out_dir, f"{n:03d}.{e}"))
              for e in ("jpg", "jpeg", "png", "gif", "webp")):
        n += 1
    return n


def existing_hashes(out_dir: str) -> set:
    """扫描输出目录里已有的图片 md5，重复运行据此跳过，避免累积副本。"""
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


# ============ 微信公众号专用抓取：纯 HTTP 抓 HTML + 正则提取正文图（不依赖浏览器）============
def _http_get(url: str, referer: str = "", timeout: int = 45, retries: int = 1):
    """带完整浏览器请求头的 GET，返回 (bytes, content-type)。自动处理 gzip。
    - 合并连接的超时与读取：单次 timeout 默认 45s（冷抓取 3MB+ 页面可能需要十几秒）
    - 网络类失败（超时 / 连接中断 / 5xx）自动重试 retries 次
    - SSL 证书校验失败降级为免校验重试（兼容证书链缺失 / 代理拦截）
    - 重试采用短退避，避免瞬时抖动导致的连续失败"""
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

    def _once(ctx=None):
        return urllib.request.urlopen(req, timeout=timeout, context=ctx) if ctx else urllib.request.urlopen(req, timeout=timeout)

    for attempt in range(retries + 1):
        resp = None
        try:
            resp = _once()
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            # 证书链缺失 / 代理拦截：降级免校验重试（不占用网络重试次数）
            if "CERTIFICATE_VERIFY_FAILED" in str(e) or isinstance(reason, ssl.SSLError):
                log("  SSL 证书校验失败，已降级为免校验重试:", url[:60])
                try:
                    resp = _once(ssl._create_unverified_context())
                except Exception as e2:
                    if attempt < retries:
                        time.sleep(0.6 * (attempt + 1))
                        continue
                    raise e2
            elif attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            else:
                raise
        except (socket.timeout, TimeoutError):
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            raise
        if resp is None:
            raise RuntimeError("empty response")
        with resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                body = gzip.decompress(body)
            return body, resp.headers.get("Content-Type", "")


def extract_wechat_images(html: str):
    """从微信文章 HTML 里按优先级提取正文原图 URL（保序、去重）。

    微信目前主要有两类文章：
      A. 图片消息/贴图文：图片内嵌在 JS 变量 picture_page_info_list 的 cdn_url 字段，
         每图还附带 watermark_info.cdn_url（水印版，要排除）。这里只取正文 cdn_url。
      B. 普通图文：正文在 #js_content 里，图片在 data-src / src 属性。
    兜底：以上都取不到时，扫描全文 qpic 链接，排除头像/二维码/og:image。
    """
    def uniq(seq):
        seen, out = set(), []
        for u in seq:
            u = u.replace("\\/", "/")
            if u.startswith("//"):
                u = "https:" + u
            # 微信图床域名有多个：mmbiz / mmecoa / mmbizappmsg ... 只要是 *.qpic.cn 都算
            if u not in seen and re.search(r"[A-Za-z0-9.-]*qpic\.cn", u):
                seen.add(u)
                out.append(u)
        return out

    # ---- A. 图片消息类：picture_page_info_list 里的 cdn_url（排除 watermark_info 的）----
    key = "picture_page_info_list"
    if key in html:
        seg = html[html.find(key): html.find(key) + 200000]
        results = []
        for m in re.finditer(r"cdn_url:\s*'([^']*[A-Za-z0-9.-]*qpic\.cn[^']*)'", seg):
            before = seg[max(0, m.start() - 80): m.start()]
            if "watermark_info" in before:         # 跳过水印版（前面字段是 watermark_info）
                continue
            results.append(m.group(1))
        got = uniq(results)
        if got:
            return got, "picture_page_info_list(图片消息)"

    # ---- B. 普通图文：<img data-src/src> 属性 ----
    imgs = re.findall(r"<img[^>]*?\b(?:data-src|data-original|src)\s*=\s*['\"]([^'\"]*[A-Za-z0-9.-]*qpic\.cn[^'\"]*)['\"]", html)
    got = uniq(imgs)
    if got:
        return got, "img标签(普通图文)"

    # ---- 兜底：全文 qpic 链接，排除 og:image / 头像 / 二维码 ----
    allq = re.findall(r"https?://[A-Za-z0-9.-]*qpic\.cn/[A-Za-z0-9_/\-]+", html)
    og = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    og_url = og.group(1) if og else ""
    bad = ("headimg", "qrcode", "round_head", "logo", "avatar")
    fallback = []
    for u in allq:
        if og_url and u.replace("http://", "https://") in og_url.replace("http://", "https://"):
            continue
        if any(b in u.lower() for b in bad):
            continue
        if u not in fallback:
            fallback.append(u)
    return fallback, "全文兜底"


def crawl_wechat(link: str, out_dir: str, min_bytes: int, start_index: int = 1) -> int:
    """微信专用：纯 HTTP 抓文章 HTML → 正则提取正文原图 → 带 Referer 逐张下载。
    不启动浏览器，因此不受无头检测 / 懒加载 / js_content 容器变化影响。"""
    seq = start_index
    seen = existing_hashes(out_dir)

    log("抓取微信文章 HTML(纯 HTTP):", link[:90])
    try:
        html_bytes, _ = _http_get(link, referer="https://mp.weixin.qq.com/")
    except Exception as e:
        log("❌ 文章页面抓取失败:", e)
        return start_index
    html = html_bytes.decode("utf-8", "ignore")
    if len(html) < 5000:
        log("❌ 文章页面内容异常(可能被反爬)，长度:", len(html))
        return start_index

    urls, how = extract_wechat_images(html)
    log(f"通过 [{how}] 识别到正文原图 {len(urls)} 张")

    if not urls:
        log("⚠️ 未能从文章中提取到任何正文图片链接")
        return start_index

    ok = 0
    for u in urls:
        u = wechat_clean(u)                       # 去 webp/lazy 参数
        orig = wechat_original(u)                 # /640 → /0，尝试取真正原图
        body = ct = None
        if orig != u:
            try:
                body, ct = _http_get(orig, referer="https://mp.weixin.qq.com/")
            except Exception as e:
                log("  原图(/0)获取失败，回退压缩版:", str(e)[:50])
        if body is None:                          # 原图失败 / 无档位：用原始 URL
            try:
                body, ct = _http_get(u, referer="https://mp.weixin.qq.com/")
            except Exception as e:
                log("  下载失败:", str(e)[:60], u[-40:])
                continue
        if "webp" in ct or "avif" in ct:
            log("  跳过 webp/avif:", u[-40:])
            continue
        if not body or len(body) < min_bytes:
            log("  跳过小图:", len(body), "bytes")
            continue
        if PLACEHOLDER in body or is_solid_or_black(body):
            log("  跳过占位/纯色/黑图:", u[-40:])
            continue
        digest = hashlib.md5(body).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        seq = next_index(out_dir, seq)
        ext = ext_of(ct)
        with open(os.path.join(out_dir, f"{seq:03d}.{ext}"), "wb") as f:
            f.write(body)
        ok += 1
        log(f"  已保存 {seq:03d}.{ext}  ({len(body) // 1024} KB)")

    log(f"微信文章完成：识别 {len(urls)} 张，成功下载 {ok} 张，"
        f"已存在跳过 {len(urls) - ok} 张")
    return seq


def main():
    ap = argparse.ArgumentParser(description="微信公众号文章正文原图爬虫")
    ap.add_argument("--url", default=None, help="临时覆盖代码内 LINKS 的单条链接")
    ap.add_argument("--out", default=None, help="保存目录（默认取代码内 OUT_DIR）")
    ap.add_argument("--min-bytes", type=int, default=MIN_BYTES, help="正文原图最小字节数")
    a = ap.parse_args()

    out = a.out or OUT_DIR
    if SAVE_IN_SUBFOLDER:
        out = os.path.join(out, SAVE_IN_SUBFOLDER)
    os.makedirs(out, exist_ok=True)

    targets = [a.url] if a.url else LINKS
    if not targets:
        log("LINKS 为空且未传 --url。请在文件顶部 LINKS 列表里贴链接后重试。")
        return

    log(f"保存位置: {out}")
    seq = 1
    for url in targets:
        platform = platform_of(url)
        log(f"→ 平台识别: {platform}")
        if platform == "wechat":
            seq = crawl_wechat(url, out, a.min_bytes, seq)
        else:
            log("⚠️ 暂不支持该链接，请提供微信公众号文章链接(mp.weixin.qq.com/s/...)")
    log(f"✅ 完成，图片已保存到 {out}")


if __name__ == "__main__":
    main()
