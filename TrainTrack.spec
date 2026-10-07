# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets')]
binaries = []
hiddenimports = ['pdf_generator', 'cache_manager', 'image_manager', 'database', 'logger', 'formations', 'teams', 'ui_async', 'views', 'views.login_view', 'views.splash_view', 'views.dashboard_view', 'views.players_view', 'views.profile_view', 'views.calendar_view', 'views.stats_view', 'views.analysis_view', 'views.ratings_view', 'views.squad_view', 'views.scouting_view', 'views.finances_view', 'views.development_center_view', 'views.teams_view', 'customtkinter', 'PIL', 'PIL._tkinter_finder', 'supabase', 'postgrest', 'gotrue', 'realtime', 'storage3', 'dateutil', 'requests', 'reportlab', 'reportlab.pdfbase', 'reportlab.pdfbase.ttfonts', 'reportlab.standardfonts']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('reportlab')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TrainTrack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)
