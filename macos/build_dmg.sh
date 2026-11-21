#!/bin/bash
# 由 Xcode 的 Run Script 构建阶段调用：py2app 打包 .app -> 补齐 Tcl/Tk 运行时 -> hdiutil 生成 DMG
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUTPUT_DIR="$PROJECT_DIR/output"
STAGE_DIR="$OUTPUT_DIR/dmg_stage"
DMG_PATH="$OUTPUT_DIR/微信爬图.dmg"
APP="$PROJECT_DIR/dist/微信爬图.app"

cd "$PROJECT_DIR"

echo "==> [1/4] 清理旧产物"
rm -rf build dist "$OUTPUT_DIR"

echo "==> [2/4] 构建 .app（py2app + Xcode 工具链）"
"$PYTHON_BIN" setup.py py2app

echo "==> [3/4] 补齐 Tcl/Tk 运行时（py2app 不会自动打包 tkinter 的 dylib/数据）"
PY_LIB="$("$PYTHON_BIN" -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')"
if [ ! -d "$PY_LIB" ]; then
    PY_LIB="$("$PYTHON_BIN" -c 'import sys,os; print(os.path.join(os.path.dirname(os.path.dirname(sys.executable)),"lib"))')"
fi
# _tkinter.so 的 @rpath 解析到 Contents/Resources/lib/，dylib 必须放在那里
cp "$PY_LIB/libtcl9.0.dylib" "$PY_LIB/libtcl9tk9.0.dylib" "$APP/Contents/Resources/lib/"
# Tcl/Tk 的脚本资源目录
cp -R "$PY_LIB/tcl9.0" "$APP/Contents/Resources/lib/"
cp -R "$PY_LIB/tk9.0" "$APP/Contents/Resources/lib/"
# 改动 bundle 内容后重新 ad-hoc 签名
codesign --force --deep --sign - "$APP" 2>/dev/null

echo "==> [4/4] 生成 DMG"
mkdir -p "$STAGE_DIR"
cp -R "$APP" "$STAGE_DIR/"
cp "$PROJECT_DIR/README.txt" "$STAGE_DIR/使用说明.txt"
ln -s /Applications "$STAGE_DIR/Applications"

hdiutil create -volname "微信爬图" -srcfolder "$STAGE_DIR" -ov -format UDZO "$DMG_PATH"

echo "==> 完成: $DMG_PATH"
