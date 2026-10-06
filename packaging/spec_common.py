"""What KherveNote.spec (Windows) and KherveNoteMAC.spec (macOS) share,
and the version stamp both build scripts use.

Both specs import this, so the module list, the data files and the
excludes cannot drift apart between the two platforms.

What ships inside the build, and what is fetched on first use
(the decision is also in CLAUDE.md, "Packaging"):

* **tectonic** (pinned official release, ~25-40 MB) and a **warmed TeX
  cache** of exactly what KherveNote's template needs (built by
  ``fetch_tectonic.py --warm`` from the example notes, both layouts):
  bundled, so PDF export works out of the box and offline.
* **faster-whisper + CTranslate2 + onnxruntime** (the speech engine and
  its voice detector): bundled — they are code.
* **The Whisper model** itself: NOT bundled. Downloaded once from
  Hugging Face the first time Listen is used (the app already says so
  and keeps recording meanwhile), then offline. Small, the default, is
  ~480 MB; bundling it would more than double the installer for users
  who may never listen, and a user who picks another size would carry a
  dead one.
* **Ollama** and its models: never bundled (separate install, GBs).
* **KhervePDF**: not bundled yet — found when installed beside it.

Copyright (C) 2026 Gwilherm Kerherve
Licensed under the GNU General Public License v3.0 (see LICENSE).
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "KherveNote"
ENTRY = str(ROOT / "KherveNote.py")
VERSION_FILE = ROOT / "khervenote" / "VERSION"
TEX_CACHE = ROOT / "khervenote" / "tectonic_cache"

#: Other Qt bindings / toolkits and heavy packages KherveNote never uses.
#: faster-whisper runs on CTranslate2, so torch / transformers must not
#: be dragged in by an optional import of huggingface_hub or onnxruntime.
EXCLUDES = [
    "PyQt5", "PyQt6", "PySide2", "tkinter", "_tkinter",
    "torch", "torchaudio", "tensorflow", "transformers", "jax",
    "scipy", "matplotlib", "pandas", "IPython", "jedi", "notebook",
    "pytest", "_pytest", "setuptools", "pip",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtBluetooth",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSql",
    "PySide6.QtDesigner", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
]


def git_version() -> str:
    """``<major>.<minor>.<commits>+<sha7>`` — ``__version__`` plus git."""
    text = (ROOT / "khervenote" / "__init__.py").read_text(encoding="utf-8")
    base = re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)
    try:
        run = lambda *a: subprocess.check_output(  # noqa: E731
            ["git", *a], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
        count, sha = run("rev-list", "--count", "HEAD"), run("rev-parse", "--short=7", "HEAD")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"could not read the version from git: {exc}")
    if not count or not sha or (ROOT / ".git" / "shallow").exists():
        raise SystemExit("could not read the version from git "
                         "(shallow clone? use fetch-depth: 0)")
    return f"{base}.{count}+{sha}"


def stamp_version():
    """Write khervenote/VERSION (a frozen build has no .git) and return
    (full, short): '0.26.N+sha' and '0.26.N'."""
    full = git_version()
    VERSION_FILE.write_text(full, encoding="ascii")
    return full, full.split("+")[0]


def icons():
    """(ico, icns) under build/, rendered from the app's own mark."""
    ico = ROOT / "build" / f"{APP_NAME}.ico"
    icns = ROOT / "build" / f"{APP_NAME}.icns"
    if not (ico.is_file() and icns.is_file()):
        sys.path.insert(0, str(ROOT / "packaging"))
        from make_icons import build_icons
        build_icons(ROOT / "build")
    return str(ico), str(icns)


def tectonic():
    """The pinned tectonic binary and the warmed cache; stops the build
    when either is missing (a build without them cannot export a PDF)."""
    sys.path.insert(0, str(ROOT / "packaging"))
    import fetch_tectonic
    exe = fetch_tectonic.fetch()
    if not TEX_CACHE.is_dir():
        print("tectonic_cache missing - warming it now (needs internet)")
        fetch_tectonic.warm(exe)
    n = sum(1 for p in TEX_CACHE.rglob("*") if p.is_file())
    if n < 20:
        raise SystemExit(f"khervenote/tectonic_cache has only {n} files - run "
                         "python packaging/fetch_tectonic.py --warm")
    print(f"bundling tectonic {exe} and tectonic_cache ({n} files)")
    return exe


def analysis_inputs():
    """(datas, binaries, hiddenimports) for Analysis()."""
    from PyInstaller.utils.hooks import (collect_data_files, collect_dynamic_libs,
                                         collect_submodules)
    exe = tectonic()
    datas = [
        (str(ROOT / "khervenote" / "manual.md"), "khervenote"),   # Help > User manual
        (str(ROOT / "LICENSE"), "."),
        (str(VERSION_FILE), "khervenote"),
        (str(TEX_CACHE), "khervenote/tectonic_cache"),
    ]
    # compiler.find_tectonic looks in sys._MEIPASS
    binaries = [(str(exe), ".")]
    # The speech stack: the VAD's ONNX model is package data of
    # faster-whisper; CTranslate2 and the audio libraries are native.
    datas += collect_data_files("faster_whisper")
    datas += collect_data_files("sounddevice") + collect_data_files("soundfile")
    datas += collect_data_files("_sounddevice_data") + collect_data_files("_soundfile_data")
    binaries += collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")
    binaries += collect_dynamic_libs("_sounddevice_data") + collect_dynamic_libs("_soundfile_data")
    datas += collect_data_files("docx") + collect_data_files("pptx")
    # Dialogs, the speech stack and the document readers are imported
    # lazily (inside functions), so static analysis alone would miss them.
    hiddenimports = collect_submodules("khervenote") + collect_submodules("faster_whisper") + [
        "ctranslate2", "onnxruntime", "av", "tokenizers", "huggingface_hub",
        "sounddevice", "soundfile", "pymupdf", "fitz", "docx", "pptx",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtNetwork",
    ]
    return datas, binaries, hiddenimports
