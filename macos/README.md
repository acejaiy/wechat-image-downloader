# 微信公众号原图下载器 · macOS 版

macOS 版从 v2.0.0 起提供**图形界面 App 与 DMG 安装包**，双击即可使用，无需在 Mac 上安装 Python。抓图功能与仓库根目录的 Windows 版一致（纯微信公众号正文原图下载）。

## 下载与安装

1. 下载本目录下的 `wechat-image-downloader-macos-v2.0.0.dmg`。
2. 双击挂载，把「微信爬图.app」拖进「应用程序」文件夹。
3. 首次打开若被 Gatekeeper 拦截，到 **系统设置 → 隐私与安全性 → 仍要打开**。

App 内置 Python 3.13、Pillow 与 Tk，arm64 架构，macOS 11.0+，ad-hoc 签名。

## 使用

1. 双击打开 App，会弹出窗口。
2. 在「微信文章链接」框粘贴公众号文章链接，每行一条（已预填示例）。
3. 可点「选择…」更改保存目录（默认 `~/Desktop/爬图`）。
4. 点「开始下载」，日志实时显示在窗口下方。
5. 点「打开保存目录」查看下载好的图片。

重复运行会按图片内容 MD5 自动去重，不会累积副本。仅支持微信公众号文章链接（`mp.weixin.qq.com/s/...`）。

## 源码与自行构建

本目录包含完整构建工程：

| 文件 | 说明 |
| --- | --- |
| `crawler_macos.py` | 抓图核心逻辑（纯标准库 + 可选 Pillow） |
| `crawler_gui.py` | Tkinter 图形界面前端，复用核心逻辑 |
| `setup.py` | py2app 打包配置 |
| `build_dmg.sh` | 一键构建脚本（py2app → 补齐 Tcl/Tk 运行时 → hdiutil 生成 DMG） |
| `CrawlerDMG.xcodeproj` | Xcode 工程，Aggregate Target「Build DMG」调用 `build_dmg.sh` |

用 Xcode 构建：

```bash
xcodebuild -project CrawlerDMG.xcodeproj -target "Build DMG" -configuration Release
```

或直接跑脚本：

```bash
./build_dmg.sh
```

产物在 `output/微信爬图.dmg`。

### 构建依赖与已知问题

- 需要 Python 3.13 + `py2app`、`Pillow`（`pip install py2app pillow`）。
- **Python 3.13** 中 `zlib` 是冻结内置模块，没有 `__file__`。py2app 0.28.10 在 `build_app.py:2443` 直接 `copy_file(zlib.__file__)` 会报 `AttributeError`。需修补为仅当 `__file__` 存在且文件存在时才复制；升级 py2app 后如仍报错，检查该处。
- py2app 不会自动打包 Tkinter 运行时。`build_dmg.sh` 会从 Python 的 lib 目录复制 `libtcl9.0.dylib`、`libtcl9tk9.0.dylib` 到 `Contents/Resources/lib/`，并带上 `tcl9.0/`、`tk9.0/` 数据目录，然后重新 ad-hoc 签名。缺少这些会导致启动时报 "Launch error"。

## 合规声明

仅用于个人学习和研究，请遵守微信公众平台服务条款、尊重原作者版权，勿用于高频或大规模抓取。作者不对使用本软件产生的任何后果负责。

## 许可证

MIT © wechat-image-downloader contributors
