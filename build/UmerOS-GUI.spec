# -*- mode: python ; coding: utf-8 -*-
#
# =============================================================================
#  UmerOS frozen-GUI build spec  [TODAY]
#  License: GPL-3.0 (GNU General Public License v3)
#  SPDX-License-Identifier: GPL-3.0-or-later
#
#  Frozen PyInstaller build for the UmerOS desktop GUI. Produces a signed,
#  zero-trust bundle that launches the canonical Flutter frontend via
#  ui/launch_gui.py (per H11/H25, §4.8). [FIX H45] adds the canonical GPL-3.0
#  license header (H7/H30 mandate) — the [TODAY] tier label was already present
#  at line 3; `build/__init__.py` is an intentional 0-byte package marker.
# =============================================================================
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
#
# [FIX H41] The frozen "UmerOS-GUI" binary must launch the CANONICAL frontend
# (Flutter, ui/flutter_ui/) — not the retired legacy PyQt6 desktop shell
# (ui/umeros_gui.py, superseded by Flutter per H11/H25, §4.8). _ENTRY now points
# at ui/launch_gui.py, the thin Python host that boots flutter_ui. The spec still
# fails closed if that entry file is missing.

import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))
_ENTRY = os.path.join(_REPO_ROOT, "ui", "launch_gui.py")
if not os.path.isfile(_ENTRY):
    raise SystemExit(f"[spec] entrypoint missing: {_ENTRY}")

# [FIX H44] `_ENTRY` is a thin stdlib-only host (ui/launch_gui.py) that shells out to
# the Flutter SDK; the Flutter app is produced separately by `flutter build` and is NOT
# bundled here. Hence datas/binaries/hiddenimports stay empty (nothing extra for
# PyInstaller to collect). optimize raised 0->1 (smaller/faster bytecode, per the
# build-hygiene mandate). Codified build + signing live in build/build_umeros_gui.py.
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
    optimize=1,
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