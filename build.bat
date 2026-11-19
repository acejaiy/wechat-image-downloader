@echo off
chcp 936 >nul
echo ============================================
echo   打包 V1.0.2 Tkinter 增强版为单文件 exe
echo ============================================
echo.

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [提示] 未找到 pyinstaller，正在安装...
    pip install pyinstaller
)

echo.
echo [1/2] 语法自检...
python -m py_compile crawler_core.py crawler_gui.py api_server.py
if errorlevel 1 (
    echo [错误] 语法检查未通过，已中止打包。
    pause
    exit /b 1
)

echo.
echo [2/2] 开始 PyInstaller 打包...
pyinstaller --onefile --windowed --collect-all PIL --name "微信公众号文章图片爬虫 V1.0.2" crawler_gui.py

echo.
echo ============================================
echo   完成！exe 位于 dist\ 目录
echo ============================================
pause
