# KherveNote — release self-test
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""``KherveNote --self-test <report.json>``: what packaging/smoke_test.py
runs against a frozen build.

A freeze fails quietly — a module or data file PyInstaller missed only
shows when the code that needs it runs — so this runs the app's real
work without a user: the speech stack is imported and its voice
detector (an ONNX model shipped inside faster-whisper) runs on silence,
an example note is typeset by the bundled tectonic **from the bundled
cache only** (seeded into an empty cache, then ``--only-cached``), and the main window is built and closed.

Nothing touches the user's notes, settings or recordings: the library,
the settings file and the recovery folder are temporary.  Exits 0 when
every check passes; the JSON report says which failed.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path


def run(args: list[str]) -> int:
    report_path = Path(args[0]) if args else None
    work = Path(tempfile.mkdtemp(prefix="knote-selftest-"))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["KHERVENOTE_RECOVERY_DIR"] = str(work / "recovery")
    checks: dict[str, str] = {}
    report: dict = {"checks": checks, "frozen": bool(getattr(sys, "frozen", False))}

    def check(name, fn):
        try:
            checks[name] = str(fn() or "ok")
        except BaseException:  # noqa: BLE001 — every failure goes in the report
            checks[name] = "FAILED: " + traceback.format_exc(limit=4).strip()

    from .mainwindow import version_string
    report["version"] = version_string()

    def imports():
        import importlib
        for mod in ("faster_whisper", "ctranslate2", "onnxruntime", "av", "tokenizers",
                    "sounddevice", "soundfile", "pymupdf", "docx", "pptx",
                    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtNetwork"):
            importlib.import_module(mod)
        return "all imported"

    def voice_detector():
        import numpy as np
        from faster_whisper.vad import get_speech_timestamps
        found = get_speech_timestamps(np.zeros(16000 * 2, dtype=np.float32))
        return f"silero VAD ran, {len(found)} speech segments in silence"

    def tex():
        from . import compiler, examples
        from .serializer import to_latex
        tectonic = compiler.find_tectonic()
        if tectonic is None:
            raise RuntimeError("tectonic not found")
        if getattr(sys, "frozen", False) and not str(tectonic).startswith(str(sys._MEIPASS)):
            raise RuntimeError(f"not the bundled tectonic: {tectonic}")
        # An empty cache of its own: the compile below can only succeed
        # from what the build bundled (and the user's cache is untouched).
        os.environ["TECTONIC_CACHE_DIR"] = str(work / "tex-cache")
        seeded = compiler.seed_tectonic_cache()
        if getattr(sys, "frozen", False) and seeded < 20:
            raise RuntimeError(f"only {seeded} files seeded from the bundled TeX cache")
        build = work / "tex"
        build.mkdir()
        (build / "note.tex").write_text(to_latex(examples.build(examples.EXAMPLES[0])),
                                        encoding="utf-8")
        code, log = compiler._run([tectonic, "--only-cached", "--outdir", str(build),
                                   str(build / "note.tex")], 300)
        pdf = build / "note.pdf"
        if code != 0 or not pdf.is_file():
            raise RuntimeError(f"offline compile failed ({code}):\n{log[-1500:]}")
        heights = compiler.pdf_page_heights_mm(pdf)
        return (f"{tectonic}: {seeded} cache files seeded, offline PDF "
                f"{len(heights)} page(s), {heights[0]:.0f} mm tall")

    def window():
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from . import mainwindow
        app = QApplication.instance() or QApplication([])  # noqa: F841
        ini = str(work / "settings.ini")
        QSettings(ini, QSettings.IniFormat).setValue("library/root", str(work / "library"))
        mainwindow.QSettings = lambda *a: QSettings(ini, QSettings.IniFormat)
        win = mainwindow.MainWindow(None)
        win.show()
        app.processEvents()
        title = win.windowTitle()
        win.close()
        app.processEvents()
        return title

    check("imports", imports)
    check("voice_detector", voice_detector)
    check("tex", tex)
    check("window", window)
    report["ok"] = all(not v.startswith("FAILED") for v in checks.values())
    text = json.dumps(report, indent=2)
    if report_path:
        report_path.write_text(text, encoding="utf-8")
    print(text, flush=True)
    return 0 if report["ok"] else 1
