# 微信公众号原图下载器 · macOS 版（源码）

这是 macOS 专用版，**只提供命令行源码 `crawler_macos.py`，不提供打包程序（无 .dmg / .app），也没有图形界面**。抓图功能与仓库根目录的 Windows 版完全一致（纯微信公众号正文原图下载），仅针对 macOS 做了路径与运行方式适配。

## 运行环境

- macOS 10.15 及以上
- Python 3.8+（macOS 通常自带 Python 3，或用 Homebrew 安装）
- 无需 tkinter（本版为纯命令行，不依赖图形界面）

## 运行

在 `macos/` 目录下打开终端：

```bash
cd macos

# 安装依赖（仅黑图过滤需要；不装也能跑，只是不过滤纯色占位图）
python3 -m pip install pillow

# 命令行运行
python3 crawler_macos.py --url "https://mp.weixin.qq.com/s/xxxxxx" --out "~/Desktop/爬图"
```

也可以直接把链接填进脚本顶部的 `LINKS` 列表，然后运行 `python3 crawler_macos.py`。

命令行参数：

| 参数 | 说明 |
| --- | --- |
| `--url` | 单篇文章链接（不填则用 `crawler_macos.py` 里 `LINKS` 列表） |
| `--out` | 保存目录（默认 `~/Desktop/爬图`） |
| `--min-bytes` | 图片最小字节数，小于此值跳过（默认 20000） |

## 与 Windows 版的区别

| 项目 | Windows 版 | macOS 版 |
| --- | --- | --- |
| 交付形式 | 单文件 exe（Release 下载）+ 图形界面 | 仅命令行源码，自行用 `python3` 运行 |
| 爬虫文件名 | `crawler_windows.py` | `crawler_macos.py` |
| 默认保存目录 | `C:\Users\<用户名>\Desktop\爬图` | `~/Desktop/爬图` |
| 界面字体 | 微软雅黑 / Consolas | 无（无图形界面） |

抓图核心逻辑与过滤规则完全一致。

## 常见问题

**Q：SSL 证书报错？**
A：脚本已内置证书校验失败后的免校验重试，一般可自动处理。

**Q：支持抖音、小红书吗？**
A：不支持，本项目专注微信公众号文章。

## 合规声明

仅用于个人学习和研究，请遵守微信公众平台服务条款、尊重原作者版权，勿用于高频或大规模抓取。作者不对使用本软件产生的任何后果负责。

## 许可证

MIT © wechat-image-downloader contributors
