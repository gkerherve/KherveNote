"""Build the KhervePDF that ships inside KherveNote.

    python packaging/build_khervepdf.py             # -> build/khervepdf-dist/
    python packaging/build_khervepdf.py --deps      # also pip-install its requirements

KherveNote opens PDFs in KhervePDF (``khervenote/khervepdf_link.py``) and
never imports it, so the installers carry KhervePDF as a program of its
own: ``KhervePDF/KhervePDF.exe`` beside ``KherveNote.exe`` on Windows,
``KherveNote.app/Contents/Helpers/KhervePDF.app`` on a Mac.

The source is ``gkerherve/KhervePDF`` at ``KHERVEPDF_REF`` (pinned below:
a commit with the single-instance channel KherveNote talks to, v0.75),
cloned into ``build/khervepdf-src``. ``KHERVEPDF_SRC`` points at a local
checkout instead. It is frozen with KhervePDF's own ``KhervePDF.spec``;
on a Mac a ``BUNDLE`` step is appended (that spec is Windows-only) so the
result is a real ``KhervePDF.app`` that can be signed and opened.

Copyright (C) 2026 Gwilherm Kerherve
Licensed under the GNU General Public License v3.0 (see LICENSE).
"""

import argparse
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_BUILD = _ROOT / "build"
_SRC = _BUILD / "khervepdf-src"
_DIST = _BUILD / "khervepdf-dist"
REPO = "https://github.com/gkerherve/KhervePDF.git"
#: v0.75 — "opening a PDF while KhervePDF runs adds a tab to that window"
KHERVEPDF_REF = os.environ.get("KHERVEPDF_REF", "e8fff0c")


def _run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def source() -> Path:
    if os.environ.get("KHERVEPDF_SRC"):
        return Path(os.environ["KHERVEPDF_SRC"]).resolve()
    if not (_SRC / ".git").is_dir():
        shutil.rmtree(_SRC, ignore_errors=True)
        _run(["git", "clone", "--quiet", REPO, _SRC])
    _run(["git", "-C", _SRC, "fetch", "--quiet", "origin"])
    _run(["git", "-C", _SRC, "checkout", "--quiet", "--force", KHERVEPDF_REF])
    return _SRC


def _icns(src: Path, out: Path) -> Path:
    """KhervePDF's own PNG icons, wrapped as an .icns (PNG payloads)."""
    chunks = (("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128),
              ("ic08", 256), ("ic09", 512), ("ic10", 1024))
    body = b""
    for kind, size in chunks:
        png = src / "packaging" / "icons" / f"khervepdf_{size}.png"
        if png.is_file():
            data = png.read_bytes()
            body += kind.encode() + struct.pack(">I", len(data) + 8) + data
    out.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)
    return out


def spec(src: Path) -> Path:
    """KhervePDF.spec, plus a BUNDLE on a Mac.

    One change to it: no ``collect_all("PySide6")``. That sweeps every Qt
    module (WebEngine, Quick 3D, QML…) into the build — 720 MB on a Mac,
    and nested frameworks codesign refuses — while PyInstaller's own
    PySide6 hooks collect exactly the modules KhervePDF imports.
    """
    text = (src / "KhervePDF.spec").read_text(encoding="utf-8")
    sweep = '    ("PySide6", False),\n'
    if sweep not in text:
        raise SystemExit("KhervePDF.spec changed: no PySide6 collect_all line to drop")
    text = text.replace(sweep, "")
    if sys.platform == "darwin":
        icns = _icns(src, _BUILD / "KhervePDF.icns")
        version = _khervepdf_version(src)
        text += f'''

# ---- added by KherveNote's packaging/build_khervepdf.py (macOS) --------
app = BUNDLE(
    coll,
    name="KhervePDF.app",
    icon={str(icns)!r},
    bundle_identifier="com.kerherve.khervepdf",
    version={version!r},
    info_plist={{
        "CFBundleName": "KhervePDF",
        "CFBundleDisplayName": "KhervePDF",
        "CFBundleShortVersionString": {version!r},
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "NSHumanReadableCopyright": "Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0.",
        "CFBundleDocumentTypes": [{{
            "CFBundleTypeName": "PDF document", "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Alternate", "LSItemContentTypes": ["com.adobe.pdf"]}}],
    }},
)
'''
    out = src / "KhervePDF.knote-build.spec"
    out.write_text(text, encoding="utf-8")
    return out


def _khervepdf_version(src: Path) -> str:
    import re
    text = (src / "khervepdf" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def build(deps: bool = False) -> Path:
    src = source()
    if deps:
        _run([sys.executable, "-m", "pip", "install", "--quiet", "-r",
              src / "requirements.txt"])
    shutil.rmtree(_DIST, ignore_errors=True)
    _run([sys.executable, "-m", "PyInstaller", spec(src), "--noconfirm", "--clean",
          "--distpath", _DIST, "--workpath", _BUILD / "khervepdf-work"], cwd=src)
    out = _DIST / ("KhervePDF.app" if sys.platform == "darwin" else "KhervePDF")
    if not out.exists():
        raise SystemExit(f"KhervePDF was not built: {out} missing")
    if sys.platform == "darwin":
        # PyInstaller also leaves the bare one-folder build; only the .app ships.
        shutil.rmtree(_DIST / "KhervePDF", ignore_errors=True)
    print(f"KhervePDF {_khervepdf_version(src)} ({KHERVEPDF_REF}) -> {out}", flush=True)
    return out


def install_into(target: Path) -> Path:
    """Copy the built KhervePDF into a frozen KherveNote: the one-folder
    ``dist/KherveNote`` (Windows) or ``dist/KherveNote.app`` (Mac)."""
    if sys.platform == "darwin":
        src = _DIST / "KhervePDF.app"
        dest = target / "Contents" / "Helpers" / "KhervePDF.app"
    else:
        src = _DIST / "KhervePDF"
        dest = target / "KhervePDF"
    if not src.exists():
        raise SystemExit(f"{src} missing — run packaging/build_khervepdf.py first")
    shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        # ditto keeps the framework symlinks a plain copy would flatten
        _run(["ditto", src, dest])
    else:
        shutil.copytree(src, dest)
    print(f"bundled KhervePDF -> {dest}", flush=True)
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deps", action="store_true",
                    help="pip-install KhervePDF's requirements first")
    build(ap.parse_args().deps)
