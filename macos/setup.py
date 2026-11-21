# -*- coding: utf-8 -*-
"""py2app 打包配置：把图形界面版爬虫打包成自包含的 macOS .app"""
from setuptools import setup

APP = ['crawler_gui.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'packages': ['PIL', 'tkinter'],
    'includes': ['PIL', 'PIL.Image', 'tkinter', 'crawler_macos'],
    'excludes': ['matplotlib', 'numpy', 'PyQt5', 'PySide2', 'curses'],
    'plist': {
        'CFBundleName': '微信爬图',
        'CFBundleDisplayName': '微信爬图',
        'CFBundleIdentifier': 'com.baixiao.crawler',
        'CFBundleVersion': '2.0.0',
        'CFBundleShortVersionString': '2.0.0',
        'LSMinimumSystemVersion': '11.0',
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
    },
}

setup(
    app=APP,
    name='微信爬图',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
