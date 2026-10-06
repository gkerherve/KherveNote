"""Claude over MCP: the tool table, the executor on a live window, and the
real stdio server -> bridge path an MCP host takes."""
import json
import os
import subprocess
import sys
import threading
import time

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from khervenote import examples, mcp_bridge, mcp_schema
from khervenote.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, monkeypatch, tmp_path):
    from khervenote import mainwindow
    monkeypatch.setenv("KHERVENOTE_STATE_DIR", str(tmp_path / "state"))
    ini = str(tmp_path / "settings.ini")
    QSettings(ini, QSettings.IniFormat).setValue("library/root", str(tmp_path / "lib"))
    monkeypatch.setattr(mainwindow, "QSettings", lambda *a: QSettings(ini, QSettings.IniFormat))
    paths = examples.install(tmp_path / "lib")
    w = mainwindow.MainWindow(str(paths[4]))       # Surface analysis — XPS
    yield w
    if w.bridge is not None:
        w.bridge.stop()
    w._mark_clean()
    w.close()


def test_every_tool_has_a_handler():
    handlers = {n[3:] for n in dir(McpToolExecutor) if n.startswith("_t_")}
    assert handlers == set(mcp_schema.TOOL_NAMES)
    assert mcp_bridge._READ_ONLY_TOOLS <= set(mcp_schema.TOOL_NAMES)
    assert mcp_bridge._FILE_TOOLS <= set(mcp_schema.TOOL_NAMES)
    from khervenote.mcp_server import _INSTRUCTIONS
    for name in mcp_schema.TOOL_NAMES:
        if name not in ("new_note", "save_note"):
            assert name in _INSTRUCTIONS, name


def test_access_levels():
    assert mcp_bridge.tool_allowed("get_transcript", "read")
    assert not mcp_bridge.tool_allowed("fill_section", "read")
    assert mcp_bridge.tool_allowed("fill_section", "edit")
    assert mcp_bridge._names_a_path("export_pdf", {"path": "/x.pdf"})
    assert not mcp_bridge._names_a_path("open_note", {"path": "/x.knote"})


def test_check_args():
    assert mcp_schema.check_args("fill_section", {"section": 1}) != ""
    assert mcp_schema.check_args("fill_section", {"section": 1, "body": "x"}) == ""
    assert "one of" in mcp_schema.check_args("export_pdf", {"path": "/a", "layout": "x"})
    assert "unknown" in mcp_schema.check_args("get_note", {"zz": 1})


def test_read_the_note_and_its_speech(win):
    ex = McpToolExecutor(win)
    note = ex.execute("get_note", {})
    assert note["title"].startswith("Surface analysis")
    titles = [s["title"] for s in note["sections"]]
    assert titles[:2] == ["Principle", "Chemical shifts"]
    first = note["sections"][0]["paragraphs"]
    assert any(p["kind"] == "important" for p in first)
    assert note["speech_lines"] == len(win.note.transcript) > 0
    all_speech = ex.execute("get_transcript", {})
    assert all_speech["total"] == note["speech_lines"]
    part = ex.execute("get_transcript", {"section": 1})
    assert 0 < part["total"] < all_speech["total"]
    assert part["window"]["title"] == "Chemical shifts"
    assert "No section 99" in ex.execute("get_transcript", {"section": 99})["error"]


def test_write_sections_and_undo(win):
    ex = McpToolExecutor(win)
    before = win._sync_note().plain_text()
    r = ex.execute("fill_section", {"section": 1,
                                    "body": "- Oxidised silicon: Si 2p moves up ~4 eV"})
    assert r["ok"] and r["heading"].startswith("From the speech (")
    sec = ex.execute("get_note", {})["sections"][1]
    texts = [p["text"] for p in sec["paragraphs"]]
    assert r["heading"] in texts
    assert "Oxidised silicon: Si 2p moves up ~4 eV" in texts
    assert sec["paragraphs"][-1]["kind"] == "bullet item"
    win.editor.document().undo()                       # one Ctrl+Z takes it all back
    assert win._sync_note().plain_text() == before

    ex.execute("append_to_section", {"section": 0, "body": "Ask about charging.",
                                     "kind": "question"})
    last = ex.execute("get_note", {})["sections"][0]["paragraphs"][-1]
    assert last == {**last, "kind": "question", "text": "Ask about charging."}
    ex.execute("set_paragraph", {"section": 0, "paragraph": len(
        ex.execute("get_note", {})["sections"][0]["paragraphs"]) - 1,
        "text": "Ask about sample charging.", "kind": "important"})
    last = ex.execute("get_note", {})["sections"][0]["paragraphs"][-1]
    assert (last["kind"], last["text"]) == ("important", "Ask about sample charging.")

    n = len(ex.execute("get_note", {})["sections"])
    r = ex.execute("add_section", {"title": "Notes from the speech",
                                   "body": "## Calibration\n\nUse $E_B = h\\nu - E_K$."})
    secs = ex.execute("get_note", {})["sections"]
    assert len(secs) == n + 1 and secs[-1]["title"] == "Notes from the speech"
    assert secs[-1]["paragraphs"][0] == {**secs[-1]["paragraphs"][0],
                                         "kind": "subheading", "text": "Calibration"}

    ex.execute("set_header", {"speaker": "Dr L. Moreau (guest)", "summary": "Short."})
    win._sync_note()
    assert win.note.meta.speaker == "Dr L. Moreau (guest)" and win.note.summary == "Short."
    assert win.dirty


def test_library_and_export(win, tmp_path):
    ex = McpToolExecutor(win)
    notes = ex.execute("list_notes", {})["notes"]
    assert len(notes) == len(examples.EXAMPLES)
    assert sum(n["open"] for n in notes) == 1
    other = next(n for n in notes if n["title"].startswith("Linear algebra"))
    assert ex.execute("open_note", {"path": other["path"]})["title"].startswith("Linear")
    stray = tmp_path / "elsewhere" / "x.knote"
    stray.parent.mkdir()
    stray.write_bytes(b"")
    assert "not in the notes library" in ex.execute("open_note", {"path": str(stray)})["error"]
    out = tmp_path / "out" / "note.tex"
    assert ex.execute("export_latex", {"path": str(out), "layout": "paged"})["ok"]
    assert "\\begin{document}" in out.read_text(encoding="utf-8")
    assert "absolute" in ex.execute("export_latex", {"path": "rel.tex"})["error"]


def test_stdio_server_through_bridge(win, app):
    bridge = win._ensure_bridge()
    bridge.set_access("edit")
    assert bridge.start()
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "get_transcript", "arguments": {"section": 0}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "export_pdf", "arguments": {"path": "/tmp/x.pdf"}}},
    ]
    env = dict(os.environ)
    proc = subprocess.Popen([sys.executable, "-m", "khervenote.mcp_server"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env)
    proc.stdin.write(("\n".join(json.dumps(m) for m in msgs) + "\n").encode())
    proc.stdin.close()
    lines = []
    reader = threading.Thread(target=lambda: lines.extend(
        proc.stdout.read().decode().splitlines()))
    reader.start()
    deadline = time.time() + 60
    while reader.is_alive() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    replies = {r["id"]: r for r in map(json.loads, lines)}
    assert replies[1]["result"]["serverInfo"]["name"] == "khervenote"
    assert replies[1]["result"]["serverInfo"]["version"].startswith("0.")
    assert len(replies[2]["result"]["tools"]) == len(mcp_schema.TOOLS)
    got = json.loads(replies[3]["result"]["content"][0]["text"])
    assert got["window"]["title"] == "Principle" and got["total"] > 0
    # Exporting to a path of its own needs Full access.
    assert replies[4]["result"]["isError"]
    assert "Full" in replies[4]["result"]["content"][0]["text"]
    assert [e["outcome"] for e in bridge.log][-1] == "refused"


def test_bridge_is_off_until_enabled(win):
    assert win.bridge is None
