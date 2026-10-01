# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
a = Analysis(['backend/main.py'], pathex=['.'], binaries=[], datas=[('frontend_dist','frontend_dist')], hiddenimports=collect_submodules('uvicorn')+['sqlalchemy.ext.baked','sqlite3'], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='EmailOutreachManager', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name='EmailOutreachManager')
