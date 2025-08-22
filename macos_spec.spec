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
        'flask.json',
        'http.client',
        'json',
        'datetime',
        'threading',
        'webview',
        'socket',
        'jinja2',           # Flask模板引擎
        'jinja2.ext',       # Jinja2扩展
        'werkzeug',         # Flask依赖
        'werkzeug.middleware.dispatcher',
        'werkzeug.middleware.proxy_fix',
        'requests',
        'requests.packages.urllib3',
        'logging',
        'hashlib',          # 加密相关
        'urllib.parse',     # URL解析
        'urllib3',          # URL处理
        'tempfile',         # 临时文件处理
        'os',               # 操作系统接口
        'sys',              # 系统相关功能
        'time',             # 时间相关
        'collections',      # 集合类
        'io',               # 输入输出
        'json.decoder',     # JSON解码
        'json.encoder',     # JSON编码
        'concurrent',       # 并发处理
        'concurrent.futures', # 线程池
        'ssl',              # SSL支持
        'certifi',          # SSL证书
        'chardet',          # 字符编码检测
        'idna',             # 国际化域名
        'email',            # 电子邮件处理
        'email.mime',       # MIME类型
        'http',             # HTTP协议
        'html',             # HTML处理
        'xml',              # XML处理
        'xml.parsers',      # XML解析
        'zlib',             # 压缩
        'brotli',           # Brotli压缩
        'cryptography',     # 加密库
        'pkg_resources',    # 包资源管理
        'importlib',        # 导入库
        'importlib.metadata', # 元数据
        'importlib.resources', # 资源
        're',               # 正则表达式
        'calendar',         # 日历功能
        'http.cookies',     # Cookie处理
        'http.cookiejar',   # Cookie jar
        'uuid',             # UUID生成
        'base64',           # Base64编码
        'binascii',         # 二进制和ASCII转换
        'codecs',           # 编解码器
        'csv',              # CSV处理
        'functools',        # 函数工具
        'itertools',        # 迭代工具
        'operator',         # 操作符
        'stat',             # 文件状态
        'string',           # 字符串操作
        'struct',           # 结构体
        'textwrap',         # 文本包装
        'unicodedata',      # Unicode数据
        'weakref',          # 弱引用
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],   # 排除不需要的模块以减少体积
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

    bundle_identifier='com.qlapp.ClickFlareTool',  # 应用标识符
    info_plist={
        'NSHighResolutionCapable': 'True',
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True  # 允许任意HTTP加载
        },
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
