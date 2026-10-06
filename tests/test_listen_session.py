import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from khervenote.audio import RATE
from khervenote.transcriber import ListenSession


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeEngine:
    def __init__(self, label):
        self.label, self.calls = label, []

    def transcribe(self, audio, language="", prompt="", fast=False, vocabulary=""):
        self.calls.append((len(audio) / RATE, fast))
        self.vocabulary = vocabulary
        return f"{self.label}:{len(audio) / RATE:.1f}", "en"


def test_previews_while_speaking_then_final_text(app):
    main, preview = FakeEngine("final"), FakeEngine("preview")
    s = ListenSession("unused.ogg", 10.0, engine=main, preview=preview,
                      vocabulary="LLZO, ToF-SIMS")
    partials, finals = [], []
    s.partial.connect(partials.append)
    s.text.connect(lambda t, at: finals.append((t, at)))
    tone = (0.2 * np.sin(np.arange(2 * RATE) / RATE * 2 * np.pi * 220)).astype(np.float32)
    for i in range(0, len(tone), RATE // 10):
        s.feed(tone[i:i + RATE // 10])
        s._maybe_preview()
    assert any(p.startswith("preview:") for p in partials)
    assert all(fast for _, fast in preview.calls)
    assert preview.vocabulary == "LLZO, ToF-SIMS"
    s.stop()
    s._transcribe_loop()
    assert finals and finals[0][0].startswith("final:") and finals[0][1] >= 10.0
    assert main.vocabulary == "LLZO, ToF-SIMS"
    assert partials[-1] == ""
