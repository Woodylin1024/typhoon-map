# typhoon-map.spec
block_cipher = None
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('data', 'data'),   # 把已產生的全球快取一起帶進去
    ],
    hiddenimports=[],       # 執行期用不到 pandas，保持精簡
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name='typhoon-map',
    console=False,   # 若要看 log，可改 True
    icon=None
)
