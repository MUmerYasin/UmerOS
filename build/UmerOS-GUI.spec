# -*- mode: python ; coding: utf-8 -*-

# UmerOS frozen-GUI build spec  [TODAY]
# =====================================
# [FIX H42] Zero-trust signed-artifact mandate:
#   * Windows: PyInstaller cannot sign PE binaries itself (codesign_identity
#     is macOS-only). Signing is therefore a MANDATORY post-build gate — run
#     `python build/sign_artifact.py dist/UmerOS-GUI.exe` which fails the
#     build (non-zero exit) unless a real Authenticode signature is applied
#     and verified. Set UMEROS_ALLOW_UNSIGNED=1 ONLY for throwaway local
#     dev builds.
#   * macOS: set codesign_identity below to your Developer ID Application
#     identity; leaving None is rejected by sign_artifact.py on darwin too.
#
# [FIX H43] The hardcoded absolute dev-machine entrypoint path was replaced
# with a repo-relative resolution that refuses silently-missing files.

import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))
_ENTRY = os.path.join(_REPO_ROOT, "ui", "umeros_gui.py")
if not os.path.isfile(_ENTRY):
    raise SystemExit(f"[spec] entrypoint missing: {_ENTRY}")

a = Analysis(
    [_ENTRY],
    pathex=[_REPO_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    name='UmerOS-GUI',
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
    codesign_identity=None,   # macOS-only; see [FIX H42] note above
    entitlements_file=None,
)