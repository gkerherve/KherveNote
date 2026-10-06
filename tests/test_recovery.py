import numpy as np
import soundfile as sf

from khervenote import recovery


def test_begin_label_pending_and_finish(monkeypatch, tmp_path):
    monkeypatch.setenv("KHERVENOTE_RECOVERY_DIR", str(tmp_path))
    audio = recovery.begin("id1", "", "", 30.0)
    tone = (0.2 * np.sin(np.arange(16000 * 3) / 16000 * 2 * np.pi * 220)).astype(np.float32)
    sf.write(audio, tone, 16000, format="OGG", subtype="OPUS")
    recovery.set_note(audio, "/notes/Lecture.knote", "Lecture")
    [p] = recovery.pending()
    assert (p.note_path, p.note_title, p.t0, p.note_id) == ("/notes/Lecture.knote", "Lecture",
                                                            30.0, "id1")
    assert abs(recovery.duration(p.audio) - 3.0) < 0.1
    assert recovery.pending(exclude=(audio,)) == []
    recovery.finish(audio)
    assert recovery.pending() == [] and not audio.parent.exists()


def test_empty_recordings_are_cleaned(monkeypatch, tmp_path):
    monkeypatch.setenv("KHERVENOTE_RECOVERY_DIR", str(tmp_path))
    audio = recovery.begin("id", "", "", 0.0)
    audio.write_bytes(b"")
    assert recovery.pending() == [] and not audio.parent.exists()


def test_finish_never_deletes_outside_the_recovery_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("KHERVENOTE_RECOVERY_DIR", str(tmp_path / "rec"))
    elsewhere = tmp_path / "notes" / "keep"
    elsewhere.mkdir(parents=True)
    recovery.finish(elsewhere / "x.ogg")
    assert elsewhere.exists()
