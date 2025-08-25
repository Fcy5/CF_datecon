# -*- mode: python ; coding: utf-8 -*-
import os
from glob import glob  # 引入glob用于可靠的文件匹配

block_cipher = None

# 修复模板文件路径匹配（兼容GitHub Actions环境）
templates_files = []
templates_dir = os.path.abspath('templates')
if os.path.exists(templates_dir):
    # 递归获取所有文件，确保路径正确
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            src_path = os.path.join(root, file)
            # 计算相对路径，确保打包后目录结构正确
            rel_path = os.path.relpath(root, templates_dir)
            dest_path = os.path.join('templates', rel_path)
            templates_files.append((src_path, dest_path))

a = Analysis(
    ['app.py'],  # 主程序入口
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=templates_files,  # 使用动态生成的模板文件列表
    hiddenimports=[
        # Flask及Web相关依赖
        'flask', 'flask.json', 'jinja2', 'jinja2.ext',
        'werkzeug', 'werkzeug.middleware.dispatcher',
        'requests', 'urllib3',
        
        # Mac原生交互依赖（解决闪退）
        'objc', 'Foundation', 'Cocoa', 'WebKit',
        'webview', 'webview.platforms.cocoa',
        
        # 系统及文件处理依赖
        'multipart', 'tempfile', 'os', 'sys', 'io',
        'json', 'datetime', 'threading', 'socket',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
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
        upx=False,  # 关闭压缩避免原生库损坏
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=['x86_64', 'arm64'],  # 兼容Intel和M芯片
        codesign_identity=None,
        entitlements_file=None,
    ),
    name='ClickFlare工具.app',
    bundle_identifier='com.qlapp.ClickFlareTool',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
        # 文件访问权限（解决文件选择闪退）
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的文件',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹',
        'LSMinimumSystemVersion': '10.15',  # 最低系统版本
    },
)
    
