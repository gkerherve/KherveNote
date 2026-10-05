import json
import urllib.error

import pytest

from khervenote import local_ai


class _Resp:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_chat_strips_thinking_and_sends_think_false(monkeypatch):
    sent = []

    def fake(req, timeout):
        sent.append(json.loads(req.data))
        return _Resp({"message": {"content": "<think>hmm</think>\n- key point"}})
    monkeypatch.setattr(local_ai.urllib.request, "urlopen", fake)
    assert local_ai.summarise("m", "notes") == "- key point"
    assert sent[0]["think"] is False and sent[0]["model"] == "m"
    assert sent[0]["messages"][0]["content"] == local_ai.SUMMARISE


def test_old_server_without_think_flag_is_retried(monkeypatch):
    calls = []

    def fake(req, timeout):
        body = json.loads(req.data)
        calls.append(body)
        if "think" in body:
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, _Body(b'{"error":"unknown field think"}'))
        return _Resp({"message": {"content": "ok"}})
    monkeypatch.setattr(local_ai.urllib.request, "urlopen", fake)
    assert local_ai.rephrase("m", "x") == "ok"
    assert len(calls) == 2 and "think" not in calls[1]


class _Body:
    def __init__(self, data):
        self.data = data

    def read(self, *a):
        return self.data

    def close(self):
        pass


def test_not_running_gives_a_clear_error(monkeypatch):
    def fake(req, timeout):
        raise urllib.error.URLError("refused")
    monkeypatch.setattr(local_ai.urllib.request, "urlopen", fake)
    with pytest.raises(local_ai.OllamaError, match="not running"):
        local_ai.list_models()


def test_host_from_environment(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:9999")
    assert local_ai.base_url() == "http://127.0.0.1:9999"


def test_pick_default():
    assert local_ai.pick_default(["a", "b"], "b") == "b"
    assert local_ai.pick_default(["a", "b"], "gone") == "a"
    installed = ["granite4:micro-h", "qwen3.5:4b", "xps-expert-fast:latest"]
    assert local_ai.pick_default(installed) == "qwen3.5:4b"
    assert local_ai.pick_default(["xps-expert:latest"]) == "xps-expert:latest"
    assert local_ai.pick_default([], "x") == ""


def test_summarise_each_section_groups_and_reports_progress(monkeypatch):
    from khervenote.documents import DocSection, Document
    doc = Document("m.pdf", "pdf", [DocSection("A", "alpha " * 30, 1), DocSection("A.1", "sub " * 30, 2),
                                    DocSection("B", "beta " * 30, 1), DocSection("C", "tiny", 1)])
    asked = []
    monkeypatch.setattr(local_ai, "chat",
                        lambda model, system, text, **k: (asked.append(text), "- point")[1])
    steps = []
    out = local_ai.summarise_each_section("m", doc, steps.append)
    assert out == "## A\n- point\n\n## B\n- point"
    assert "A.1" in asked[0] and len(asked) == 2
    assert steps[0].startswith("Summarising section 1 of 3")
    many = Document("p", "pdf", [DocSection(f"Page {i}", "x " * 50, 1, i) for i in range(1, 61)])
    assert len(local_ai._section_groups(many, 24)) <= 24
