import json
import os
import sys

import pytest
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import QApplication

from khervenote import khervepdf_link


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


_FAKE_KHERVEPDF = r"""
import json, sys
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtNetwork import QLocalServer
app = QCoreApplication([])
server = QLocalServer()
QLocalServer.removeServer(sys.argv[1])
assert server.listen(sys.argv[1])
bufs = {}
def consume(sock):
    buf = bufs.setdefault(id(sock), bytearray())
    buf.extend(bytes(sock.readAll()))
    if b"\n" in buf:
        print(bytes(buf).partition(b"\n")[0].decode(), flush=True)
        sock.write(b"ok\n")
        sock.flush()
        QTimer.singleShot(300, app.quit)
def accept():
    while server.hasPendingConnections():
        sock = server.nextPendingConnection()
        sock.readyRead.connect(lambda s=sock: consume(s))
        consume(sock)        # the request may already be there (Windows)
server.newConnection.connect(accept)
print("ready", flush=True)
QTimer.singleShot(20000, app.quit)
app.exec()
"""


def test_a_running_khervepdf_gets_the_file(app, monkeypatch, tmp_path):
    """KhervePDF runs in a process of its own, as in real use.  (A server
    in this same process could not answer while the client waits: the
    client's blocking wait holds the interpreter, so the request was only
    read after it gave up — and on Windows a named pipe drops what was
    not read when the client hangs up.)"""
    import subprocess
    import time
    name = f"knote-test-{os.getpid()}-{tmp_path.name}"[:60]
    monkeypatch.setenv("KHERVEPDF_IPC_NAME", name)
    proc = subprocess.Popen([sys.executable, "-c", _FAKE_KHERVEPDF, name],
                            stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "ready"
        pdf = tmp_path / "Manual.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        t = time.time()
        assert khervepdf_link.send_to_running([str(pdf)]) is True
        assert time.time() - t < 3            # the answer came, no 5 s timeout
        got = json.loads(proc.stdout.readline())
        assert got == {"cmd": "open", "paths": [str(pdf)]}
    finally:
        proc.wait(timeout=30)


def test_nothing_running(monkeypatch):
    monkeypatch.setenv("KHERVEPDF_IPC_NAME", "knote-test-nobody-listens")
    assert khervepdf_link.send_to_running(["/x.pdf"], timeout_ms=100) is False


def test_launch_command_finds_a_checkout_and_its_venv(tmp_path, monkeypatch):
    repo = tmp_path / "KhervePDF"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / "KhervePDF.py").write_text("")
    (repo / ".venv" / "bin" / "python").write_text("")
    monkeypatch.setattr(khervepdf_link, "_sibling_checkout", lambda: None)
    cmd = khervepdf_link.launch_command(["/n/Manual.pdf"], str(repo))
    assert cmd == [str(repo / ".venv/bin/python"), str(repo / "KhervePDF.py"), "/n/Manual.pdf"]


def test_missing_when_nowhere(tmp_path, monkeypatch):
    monkeypatch.setenv("KHERVEPDF_IPC_NAME", "knote-test-nobody-listens")
    monkeypatch.setattr(khervepdf_link, "_sibling_checkout", lambda: None)
    monkeypatch.setattr(khervepdf_link.sys, "platform", "linux")
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    assert khervepdf_link.open_pdf(str(pdf)) == "missing"


def test_the_bundled_copy_is_found_in_a_release_build(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(khervepdf_link, "_sibling_checkout", lambda: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "none"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "none"))
    if sys.platform == "darwin":
        app = tmp_path / "KherveNote.app" / "Contents"
        exe = app / "MacOS" / "KherveNote"
        nested = app / "Helpers" / "KhervePDF.app"
        (nested / "Contents" / "MacOS").mkdir(parents=True)
        (nested / "Contents" / "MacOS" / "KhervePDF").write_text("")
        monkeypatch.setattr(khervepdf_link, "Path", _NoAppsPath)
    else:
        exe = tmp_path / "KherveNote" / "KherveNote.exe"
        name = "KhervePDF.exe" if sys.platform == "win32" else "KhervePDF"
        nested = exe.parent / "KhervePDF" / name
        nested.parent.mkdir(parents=True)
        nested.write_text("")
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("")
    monkeypatch.setattr(sys, "executable", str(exe))
    assert khervepdf_link.bundled_khervepdf() == nested
    assert khervepdf_link.bundled_executable().is_file()
    cmd = khervepdf_link.launch_command(["/x/a.pdf"])
    assert cmd is not None and str(nested) in cmd and cmd[-1] == "/x/a.pdf"


class _NoAppsPath(type(__import__("pathlib").Path())):
    """Path, except that no KhervePDF is installed in /Applications."""
    def is_dir(self):
        if str(self).endswith("Applications/KhervePDF.app"):
            return False
        return super().is_dir()
