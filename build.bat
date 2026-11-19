@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   微信公众号原图下载器 - 一键打包
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+ 并加入 PATH。
    pause
    exit /b 1
)

echo [1/2] 安装依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败。
    pause
    exit /b 1
)

echo.
echo [2/2] 打包 exe...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "微信公众号文章图片爬虫" --collect-all PIL --icon=NONE crawler_gui.py
if errorlevel 1 (
    echo [错误] 打包失败。
    pause
    exit /b 1
)

echo.
echo ============================================
echo   打包完成！exe 在 dist\微信公众号文章图片爬虫.exe
echo ============================================
pause
