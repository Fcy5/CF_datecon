# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['app.py'],  # 你的主程序入口
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        # 递归打包 templates 文件夹所有内容（包括子目录）
        (os.path.abspath('templates/**/*'), 'templates'),
    ],
    hiddenimports=[
        # 基础 Flask 与网络依赖
        'flask', 'flask.json', 'jinja2', 'jinja2.ext',
        'werkzeug', 'werkzeug.middleware.dispatcher',
        'requests', 'requests.packages.urllib3', 'urllib3',
        
        # Mac 原生交互核心依赖（解决闪退关键）
        'objc', 'Foundation', 'Cocoa', 'WebKit',
        'webview', 'webview.platforms.cocoa',  # WebView Mac 实现
        
        # 文件处理与系统依赖
        'multipart', 'tempfile', 'os', 'sys', 'io',
        'json.decoder', 'json.encoder', 'datetime',
        'threading', 'socket', 'logging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],  # 排除无用的 GUI 库
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

app = BUNDLE(
    EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        name='ClickFlare工具',
        debug=False,
        strip=False,
        upx=False,  # 关闭压缩，避免原生库损坏
        console=True,  # 保留控制台输出，方便调试
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=['x86_64', 'arm64'],  # 同时支持 Intel 和 M 系列芯片
        codesign_identity=None,
        entitlements_file=None,
    ),
    name='ClickFlare工具.app',
    bundle_identifier='com.qlapp.ClickFlareTool',
    info_plist={
        # 高分辨率支持
        'NSHighResolutionCapable': 'True',
        # 网络访问权限
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
        # 文件访问权限声明（解决文件选择闪退）
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的文件',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹',
        'NSFileProviderDomainUsageDescription': '需要读取本地文件',
        # 最低系统版本要求
        'LSMinimumSystemVersion': '10.15',
        # 支持的文件类型
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Excel File',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': [
                    'org.openxmlformats.spreadsheetml.sheet',
                    'com.microsoft.excel.xls'
                ]
            }
        ]
    },
)
