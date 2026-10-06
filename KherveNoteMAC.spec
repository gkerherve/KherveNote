# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for KherveNote on macOS.
#
#   .venv/bin/pip install pyinstaller
#   .venv/bin/pyinstaller KherveNoteMAC.spec --noconfirm
#     -> dist/KherveNote.app
#
# Builds for the Mac it runs on (Apple Silicon or Intel). PyInstaller signs
# the bundle ad hoc, which Apple Silicon needs to run it at all; it is not
# notarised, so on another Mac the first launch is right-click > Open.
#
# Info.plist carries the microphone and camera usage strings Qt needs.
#
# The Windows build is KherveNote.spec; both share packaging/spec_common.py.
#
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH) / "packaging"))
import spec_common as common  # noqa: E402

FULL_VERSION, SHORT_VERSION = common.stamp_version()
_ICO, ICNS = common.icons()
datas, binaries, hiddenimports = common.analysis_inputs()
print(f"Building {common.APP_NAME} v{FULL_VERSION} for macOS")

a = Analysis(
    [common.ENTRY],
    pathex=[str(common.ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=common.EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KherveNote",
    icon=ICNS,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,           # the build Mac's own architecture
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KherveNote",
)

app = BUNDLE(
    coll,
    name="KherveNote.app",
    icon=ICNS,
    bundle_identifier="com.kerherve.khervenote",
    # CFBundleShortVersionString must be dot-separated digits: no '+sha'.
    version=SHORT_VERSION,
    info_plist={
        "CFBundleName": "KherveNote",
        "CFBundleDisplayName": "KherveNote",
        "CFBundleShortVersionString": SHORT_VERSION,
        "CFBundleVersion": SHORT_VERSION,
        "CFBundleGetInfoString": f"KherveNote {FULL_VERSION}",
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.education",
        "NSHighResolutionCapable": True,          # sharp text on Retina
        "NSRequiresAquaSystemAppearance": False,
        "NSHumanReadableCopyright":
            "Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0.",
        # Without these two strings Qt's permission API refuses the
        # microphone AND the camera at once (khervenote/permissions.py).
        "NSMicrophoneUsageDescription":
            "KherveNote listens to the talk and writes what is said beside "
            "your notes. Speech recognition runs on this Mac; the audio "
            "never leaves it.",
        "NSCameraUsageDescription":
            "KherveNote takes pictures of a whiteboard, a slide or a handout "
            "and puts them in your note.",
        "UTExportedTypeDeclarations": [{
            "UTTypeIdentifier": "com.kerherve.khervenote.note",
            "UTTypeDescription": "KherveNote note",
            "UTTypeConformsTo": ["public.zip-archive", "public.data"],
            "UTTypeTagSpecification": {"public.filename-extension": ["knote"]},
        }],
    },
)
