# 微信公众号原图下载器 · V1.0.2

<p align="center">
  <img src="docs/screenshot.png" alt="程序界面" width="720">
</p>

<p align="center">
  <b>零依赖 · 开箱即用 · 微信公众号正文原图一键下载</b><br>
  Windows 提供单文件 exe，macOS 提供 DMG 图形界面版，粘贴文章链接即可批量存图。<br>
  V1.0.2 新增：文章分组 / 智能整理 / 剪贴板监听 / 本地 HTTP API。
</p>

<p align="center">
  <a href="https://github.com/acejaiy/wechat-image-downloader/releases/latest"><img src="https://img.shields.io/badge/下载-Windows%20exe-blue?style=flat-square" alt="下载 exe"></a>
  <a href="https://github.com/acejaiy/wechat-image-downloader/tree/main/macos"><img src="https://img.shields.io/badge/macOS-DMG-blue?style=flat-square" alt="macOS DMG"></a>
  <a href="https://github.com/acejaiy/wechat-image-downloader/blob/main/LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green?style=flat-square" alt="MIT"></a>
</p>

---

## 为什么做这个

网上能搜到的公众号图片工具，大多需要你先装 Python、Playwright、浏览器内核或 Node.js，对只想「贴个链接存图」的普通用户门槛太高。

这个项目的目标是：**下载一个 exe，双击打开，贴链接，点运行**，就这么简单。

- 单个 exe 文件，无需安装 Python 或任何运行环境
- 原生桌面窗口，不起浏览器、不起本地网页服务
- 只依赖 Python 标准库 + Pillow，纯 HTTP 抓取，快且轻
- 特别处理了「图片消息类」文章 —— 这类文章的图内嵌在 JS 变量里，没有 `<img>` 标签，用浏览器走 DOM 反而抓空

## 功能特性

- **批量下载**：一次粘贴多条链接，一行一个，自动排队处理
- **正文原图**：优先取服务器原图（去掉 webp / 懒加载压缩参数），不是缩略图
- **智能过滤**：自动跳过头像、二维码、装饰图、过小图片、黑图/纯色占位图
- **自动去重**：按图片内容 MD5 去重，重复运行不会累积副本
- **灵活保存**：可自定义保存目录和子文件夹，图片按序号命名
- **实时日志**：运行过程实时显示在窗口里，成功/跳过/失败一目了然
- **可中断**：长任务可随时点「停止」

## V1.0.2 新增功能

在 v1.0.1 单文件 exe 的基础上，专注**批处理**与**减少用户决策**，界面仍是熟悉的 Tkinter，操作依旧傻瓜式：

- **文章分组**：按文章标题自动建文件夹，多篇文章不再混在一起；标题自动清洗 emoji、半角符号、特殊符号，避免文件夹名乱码或无法识别。
- **智能整理**：下载完自动分「原图 / 封面 / 动图」三类子目录，把过滤能力可视化。
- **剪贴板监听**（可关）：复制微信文章链接自动填入链接框。仅在本机内存比对链接格式（正则匹配 `mp.weixin.qq.com/s`），只提取微信链接，不落盘、不联网、不上传任何数据。
- **本地 HTTP API**（可关）：可选开启，仅监听 `127.0.0.1`，供自动化工具调用，不影响小白界面。

### 本地 HTTP API 用法

在「智能选项」勾选「开启本地 HTTP API」后：

```bash
curl http://127.0.0.1:8765/health
curl -X POST http://127.0.0.1:8765/crawl \
  -H "Content-Type: application/json" \
  -d '{"links":["https://mp.weixin.qq.com/s/..."],"out":"D:/爬图"}'
```

## 快速开始（推荐）

1. 到 [Releases 页面](https://github.com/acejaiy/wechat-image-downloader/releases/latest) 下载 `wechat-image-crawler.exe`（即「微信公众号文章图片爬虫」）
2. 双击运行（首次启动会解压几秒，属正常现象）
3. 在「保存目录」选择图片要存的位置（默认是桌面的 `爬图` 文件夹）
4. 把公众号文章链接粘贴到「文章链接」框，一行一个
5. 点击「▶ 立即运行」，等待完成提示

> 支持形如 `https://mp.weixin.qq.com/s/xxxxxx` 的文章链接。

## macOS 用户

macOS 版提供 **DMG 安装包（图形界面）**，双击即用，无需安装 Python。下载 [`macos/`](macos/) 目录下的 `wechat-image-downloader-macos-v2.0.0.dmg`，把 App 拖进应用程序即可。

- 内置 Python 3.13 / Pillow / Tk，arm64，macOS 11.0+
- 双击弹出窗口，粘贴链接、点「开始下载」，日志实时显示
- 默认保存到 `~/Desktop/爬图`

想从源码自行构建（py2app + Xcode）或了解已知问题，详见 [macos/README.md](macos/README.md)。

## 从源码运行（Windows）

如果你不想用 exe，也可以跑 Windows 版源码：

```bash
# 环境：Python 3.8+（已验证 3.14）
pip install pillow
python crawler_gui.py        # 图形界面
```

命令行模式（无需界面）：

```bash
python crawler_windows.py --url "https://mp.weixin.qq.com/s/xxxxxx" --out "D:/图片" --min-bytes 20000
```

参数说明：

| 参数 | 说明 |
| --- | --- |
| `--url` | 单篇文章链接（不填则用代码里 `LINKS` 列表） |
| `--out` | 保存目录（默认桌面 `爬图` 文件夹） |
| `--min-bytes` | 图片最小字节数，小于此值跳过（默认 20000） |

## 自己打包 exe（Windows）

Windows 下双击 `build.bat`，会自动安装依赖并用 PyInstaller 生成单文件 exe，输出在 `dist/` 目录（名为「微信公众号文章图片爬虫 V1.0.2.exe」）。

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed \
  --name "微信公众号文章图片爬虫 V1.0.2" --collect-all PIL \
  crawler_gui.py
```

## 工作原理

微信目前主要有两类文章：

- **图片消息 / 图集类**：图片内嵌在页面 JS 变量 `picture_page_info_list` 的 `cdn_url` 字段里，页面没有 `<img>` 标签，也没有 `#js_content` 容器。浏览器 DOM 抓取会失败，因此本项目对这类文章直接抓 HTML + 正则提取原图。
- **普通图文类**：正文在 `#js_content` 里，图片在 `data-src` / `data-original` 属性中，同样走 HTML 解析。

提取到图片 URL 后，带上 `Referer: https://mp.weixin.qq.com/` 逐张下载以绕过图床防盗链，再做体积、像素、去重过滤后落盘。整个过程不启动浏览器。

原图与稳定性处理：

- **原图优先**：微信图片 URL 常带压缩档位（如 `/640`），程序会尝试把档位替换为 `/0` 请求服务器原图（通常更清晰、字节更大）；失败时自动回退到原 URL，单张异常不影响整篇。
- **超时与重试**：单次请求超时 45 秒，网络类失败自动重试一次并带短退避，兼容弱网与微信页面偶发慢加载。
- **证书降级**：SSL 证书校验失败时自动免校验重试，兼容证书链缺失或代理拦截环境。

## 目录结构

```
wechat-image-downloader/
├── crawler_gui.py          # Windows 图形界面（GUI 外壳，V1.0.2 增强版）
├── crawler_core.py         # V1.0.2 增强核心（提取/下载/分组/分类/清洗），GUI 与 API 共用
├── crawler_windows.py      # 命令行入口（基础版核心，保留兼容）
├── api_server.py           # V1.0.2 本地 HTTP API（可选）
├── build.bat               # Windows 一键打包脚本
├── requirements.txt        # 依赖
├── LICENSE                 # MIT 许可证
├── docs/
│   └── screenshot.png      # 界面截图
└── macos/                  # macOS 专用版（DMG 图形界面 + 构建工程）
    ├── crawler_macos.py    # macOS 爬虫核心逻辑
    ├── crawler_gui.py      # Tkinter 图形界面
    ├── setup.py            # py2app 打包配置
    ├── build_dmg.sh        # 一键构建脚本
    ├── CrawlerDMG.xcodeproj/  # Xcode 工程
    ├── wechat-image-downloader-macos-v2.0.0.dmg  # DMG 安装包
    └── README.md           # macOS 使用与构建说明
```

## 常见问题

**Q：双击 exe 没反应 / 启动慢？**
A：单文件 exe 首次启动需要把内容解压到临时目录，约几秒钟，请稍等。若杀毒软件误报，可加入白名单。

**Q：抓取失败或图片数为 0？**
A：确认链接是有效的公众号文章链接且能正常在浏览器打开；部分临时分享链接会过期。若文章被反爬拦截，日志会提示 HTML 内容异常。

**Q：图片顺序是按文章顺序吗？**
A：是的，按正文中出现的顺序从 `001.jpg` 开始编号。

**Q：支持抖音、小红书吗？**
A：不支持，本项目专注微信公众号文章。

## 合规与免责声明

- 本项目仅用于**个人学习和研究**，请勿用于任何商业用途或大规模抓取。
- 仅用于下载你有权访问的公开文章内容，遵守著作权与平台条款，勿作商业分发。
- 使用时请遵守微信公众平台的相关服务条款和 robots 协议，尊重原作者版权。
- 请勿高频、批量抓取他人内容，避免对相关服务造成影响；由此产生的任何后果由使用者自行承担。
- 剪贴板监听与本地 API 均为可选功能，纯本机运行；不落盘、不联网、不上传任何数据到任何平台。
- 作者不对使用本软件造成的任何损失或法律责任负责。

## 许可证

[MIT](LICENSE) © 2026 wechat-image-downloader contributors
