import json

import pytest
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import QApplication

from khervenote import khervepdf_link


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_a_running_khervepdf_gets_the_file(app, monkeypatch, tmp_path):
    name = f"knote-test-{tmp_path.name}"
    monkeypatch.setenv("KHERVEPDF_IPC_NAME", name)
    server = QLocalServer()
    assert server.listen(name)
    got = []

    def accept():
        sock = server.nextPendingConnection()
        buf = bytearray()

        def read():
            buf.extend(bytes(sock.readAll()))
            if b"\n" in buf and not got:
                got.append(json.loads(bytes(buf).partition(b"\n")[0].decode()))
                sock.write(b"ok\n")
                sock.flush()
        sock.readyRead.connect(read)
        read()                     # the request may already be there
    server.newConnection.connect(accept)
    pdf = tmp_path / "Manual.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    import threading
    result = []
    t = threading.Thread(target=lambda: result.append(khervepdf_link.send_to_running([str(pdf)])))
    t.start()
    while t.is_alive():
        app.processEvents()
    app.processEvents()
    assert result == [True]
    assert got == [{"cmd": "open", "paths": [str(pdf)]}]
    server.close()


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
