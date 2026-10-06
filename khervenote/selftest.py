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
        if getattr(sys, "frozen", False):
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

    def khervepdf():
        """The KhervePDF the installer ships starts, and takes a PDF over
        its single-instance channel (the way KherveNote hands it one)."""
        import subprocess
        import time
        from PySide6.QtNetwork import QLocalSocket
        from PySide6.QtWidgets import QApplication
        from . import khervepdf_link
        app = QApplication.instance() or QApplication([])  # noqa: F841
        exe = khervepdf_link.bundled_executable()
        if exe is None:
            if getattr(sys, "frozen", False):
                raise RuntimeError("no KhervePDF inside this build")
            return "skipped (run from source)"
        name = f"knote-selftest-{os.getpid()}"
        env = dict(os.environ, KHERVEPDF_IPC_NAME=name, QT_QPA_PLATFORM="offscreen")
        pdf = next((work / "tex").glob("*.pdf"), None)
        proc = subprocess.Popen([str(exe)], env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + 120
            while True:
                if proc.poll() is not None:
                    raise RuntimeError(f"KhervePDF exited with code {proc.returncode}")
                sock = QLocalSocket()
                sock.connectToServer(name)
                if sock.waitForConnected(500):
                    break
                if time.time() > deadline:
                    raise RuntimeError("KhervePDF did not open its channel in 120 s")
                time.sleep(0.5)
            req = {"cmd": "open", "paths": [str(pdf)] if pdf else []}
            sock.write((json.dumps(req) + "\n").encode())
            sock.flush()
            sock.waitForBytesWritten(2000)
            reply = b""
            while b"\n" not in reply and sock.waitForReadyRead(10000):
                reply += bytes(sock.readAll())
            sock.disconnectFromServer()
            if reply.strip() != b"ok":
                raise RuntimeError(f"KhervePDF answered {reply!r}")
            return f"{exe}: started, took {'a PDF' if pdf else 'the request'}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

    def window():
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from . import mainwindow
        app = QApplication.instance() or QApplication([])  # noqa: F841
        ini = str(work / "settings.ini")
        QSettings(ini, QSettings.IniFormat).setValue("library/root", str(work / "library"))
        mainwindow.QSettings = lambda *a: QSettings(ini, QSettings.IniFormat)
        os.environ["KHERVENOTE_STATE_DIR"] = str(work / "state")
        os.environ["KHERVENOTE_MCP"] = "edit"
        win = mainwindow.MainWindow(None)
        win.show()
        app.processEvents()
        title = win.windowTitle()
        try:
            mcp = _mcp_round_trip(app)
        finally:
            win._mark_clean()
            win.close()
            app.processEvents()
        return f"{title}; MCP: {mcp}"

    check("imports", imports)
    check("voice_detector", voice_detector)
    check("tex", tex)
    check("window", window)
    check("khervepdf", khervepdf)
    report["ok"] = all(not v.startswith("FAILED") for v in checks.values())
    text = json.dumps(report, indent=2)
    if report_path:
        report_path.write_text(text, encoding="utf-8")
    print(text, flush=True)
    return 0 if report["ok"] else 1


def _mcp_round_trip(app) -> str:
    """What Claude Desktop does: start ``<exe> --mcp-server`` (or the
    module from source), initialize, list the tools, call one — through
    the bridge of the window that is open."""
    import subprocess
    import threading
    import time
    cmd = ([sys.executable, "--mcp-server"] if getattr(sys, "frozen", False)
           else [sys.executable, "-m", "khervenote.mcp_server"])
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "add_section",
                    "arguments": {"title": "From Claude", "body": "- it works"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "get_note", "arguments": {}}},
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=dict(os.environ))
    proc.stdin.write(("\n".join(json.dumps(m) for m in msgs) + "\n").encode())
    proc.stdin.close()
    lines: list = []
    reader = threading.Thread(target=lambda: lines.extend(
        proc.stdout.read().decode().splitlines()), daemon=True)
    reader.start()
    deadline = time.time() + 120
    while reader.is_alive() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    if reader.is_alive():
        proc.kill()
        raise RuntimeError("the MCP server did not answer within 120 s")
    replies = {r.get("id"): r for r in map(json.loads, lines)}
    info = replies[1]["result"]["serverInfo"]
    tools = replies[2]["result"]["tools"]
    if replies[3]["result"].get("isError"):
        raise RuntimeError(replies[3]["result"]["content"][0]["text"])
    note = json.loads(replies[4]["result"]["content"][0]["text"])
    if note["sections"][-1]["title"] != "From Claude":
        raise RuntimeError(f"add_section did not reach the page: {note['sections']}")
    return f"{info['name']} {info['version']}, {len(tools)} tools, add_section + get_note ok"
