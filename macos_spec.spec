# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates/*', 'templates'),  # 包含模板文件夹
    ],
    hiddenimports=[
        'flask',
        'http.client',
        'json',
        'datetime',
        'threading',
        'webview',
        'socket',
        'jinja2',  # Flask模板引擎
        'werkzeug',  # Flask依赖
        'requests',
        'logging'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# macOS 专用配置 - 创建应用包
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
        upx=True,
        console=False,  # 不显示控制台
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    ),
    name='ClickFlare工具.app',  # 应用包名称
    # 移除图标配置
    bundle_identifier='com.qlapp.ClickFlareTool',  # 应用标识符
)