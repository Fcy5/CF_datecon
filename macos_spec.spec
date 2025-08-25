# -*- mode: python ; coding: utf-8 -*-
import os  # 仅添加必要的os模块用于路径处理

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath('.')],  # 添加当前目录为搜索路径，解决模块导入问题
    binaries=[],
    datas=[
        # 使用绝对路径确保资源正确打包
        (os.path.abspath('templates/*'), 'templates'),
    ],
    hiddenimports=[
        # 保留原有依赖，仅添加文件上传必需的缺失模块
        'flask',
        'flask.json',
        'http.client',
        'json',
        'datetime',
        'threading',
        'webview',
        'webview.platforms.cocoa',  # Mac平台WebView核心依赖
        'socket',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'werkzeug.middleware.dispatcher',
        'werkzeug.middleware.proxy_fix',
        'requests',
        'requests.packages.urllib3',
        'logging',
        'hashlib',
        'urllib.parse',
        'urllib3',
        'urllib3.contrib.appengine',  # 补充urllib3相关依赖
        'multipart',  # 表单文件上传处理模块
        'tempfile',
        'os',
        'sys',
        'time',
        'collections',
        'io',
        'json.decoder',
        'json.encoder',
        'concurrent',
        'concurrent.futures',
        'ssl',
        'certifi',
        'chardet',
        'idna',
        'email',
        'email.mime',
        'email.mime.multipart',  # 邮件MIME处理（文件上传需要）
        'email.mime.image',      # 图片MIME处理
        'http',
        'html',
        'xml',
        'xml.parsers',
        'zlib',
        'brotli',
        'cryptography',
        'pkg_resources',
        'importlib',
        'importlib.metadata',
        'importlib.resources',
        're',
        'calendar',
        'http.cookies',
        'http.cookiejar',
        'uuid',
        'base64',
        'binascii',
        'codecs',
        'csv',
        'functools',
        'itertools',
        'operator',
        'stat',
        'string',
        'struct',
        'textwrap',
        'unicodedata',
        'weakref',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
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
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    ),
    name='ClickFlare工具.app',
    bundle_identifier='com.qlapp.ClickFlareTool',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True
        },
        # 添加文件访问权限声明（解决闪退核心）
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSFileProviderDomainUsageDescription': '需要读取本地文件以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的临时文件',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Excel File',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': [
                    'org.openxmlformats.spreadsheetml.sheet',
                    'com.microsoft.excel.xls'
                ],
                'LSHandlerRank': 'Default'
            }
        ]
    },
)
