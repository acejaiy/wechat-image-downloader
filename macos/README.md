# 微信公众号原图下载器 · macOS 版（源码）

这是 macOS 专用版，**只提供源码，不提供打包程序（无 .dmg / .app）**。功能与仓库根目录的 Windows 版完全一致（纯微信公众号正文原图下载），仅针对 macOS 做了路径、字体和运行方式适配。

## 运行环境

- macOS 10.15 及以上
- Python 3.8+（macOS 通常自带 Python 3，或用 Homebrew 安装）

## 运行

在 `macos/` 目录下打开终端：

```bash
cd macos

# 安装依赖（仅黑图过滤需要；不装也能跑，只是不过滤纯色占位图）
python3 -m pip install pillow

# 方式一：图形界面（推荐）
python3 crawler_gui.py

# 方式二：命令行
python3 crawler.py --url "https://mp.weixin.qq.com/s/xxxxxx" --out "~/Desktop/爬图"
```

图形界面用法与 Windows 版相同：选保存目录 → 粘贴文章链接（一行一个）→ 点「立即运行」。

命令行参数：

| 参数 | 说明 |
| --- | --- |
| `--url` | 单篇文章链接（不填则用 `crawler.py` 里 `LINKS` 列表） |
| `--out` | 保存目录（默认 `~/Desktop/爬图`） |
| `--min-bytes` | 图片最小字节数，小于此值跳过（默认 20000） |

## 与 Windows 版的区别

| 项目 | Windows 版 | macOS 版 |
| --- | --- | --- |
| 交付形式 | 单文件 exe（Release 下载） | 仅源码，自行用 `python3` 运行 |
| 爬虫文件名 | `crawler_windows.py` | `crawler.py` |
| 默认保存目录 | `C:\Users\<用户名>\Desktop\爬图` | `~/Desktop/爬图` |
| 界面字体 | 微软雅黑 / Consolas | 苹方 / Menlo |
| 打开目录 | `os.startfile` | `open` 命令 |

抓图核心逻辑、过滤规则、GUI 功能完全一致。

## 常见问题

**Q：提示缺少 tkinter？**
A：macOS 自带 Python 可能没装 tkinter。用 Homebrew 安装：`brew install python-tk`，或用 [python.org 官方安装包](https://www.python.org/downloads/macos/)（自带 tkinter）。

**Q：SSL 证书报错？**
A：脚本已内置证书校验失败后的免校验重试，一般可自动处理。

**Q：支持抖音、小红书吗？**
A：不支持，本项目专注微信公众号文章。

## 合规声明

仅用于个人学习和研究，请遵守微信公众平台服务条款、尊重原作者版权，勿用于高频或大规模抓取。作者不对使用本软件产生的任何后果负责。

## 许可证

MIT © wechat-image-downloader contributors
