import numpy as np

from khervenote.audio import RATE, Chunker


def _tone(seconds, amp=0.2):
    t = np.arange(int(seconds * RATE)) / RATE
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def _silence(seconds):
    return np.zeros(int(seconds * RATE), np.float32)


def _feed(chunker, audio):
    out = []
    for i in range(0, len(audio), RATE // 10):
        out += chunker.feed(audio[i:i + RATE // 10])
    return out + chunker.flush()


def test_cuts_at_pauses():
    audio = np.concatenate([_tone(4), _silence(1), _tone(5), _silence(1)])
    chunks = _feed(Chunker(), audio)
    assert len(chunks) == 2
    assert chunks[0].start == 0
    assert abs(chunks[1].start_s - 4.6) < 0.5


def test_long_speech_is_cut_at_max_length():
    chunks = _feed(Chunker(max_s=10), _tone(25))
    assert len(chunks) >= 3
    assert all(len(c.audio) <= 10 * RATE + 480 for c in chunks)
    assert sum(len(c.audio) for c in chunks) == 25 * RATE


def test_silence_is_dropped():
    assert _feed(Chunker(), _silence(30)) == []
    noise = (np.random.default_rng(1).standard_normal(20 * RATE) * 0.001).astype(np.float32)
    assert _feed(Chunker(), noise) == []


def test_start_times_follow_dropped_silence():
    audio = np.concatenate([_silence(20), _tone(4), _silence(1)])
    chunks = _feed(Chunker(), audio)
    assert len(chunks) == 1 and chunks[0].start_s >= 14


def test_recording_format_round_trips(tmp_path):
    import soundfile as sf
    path = tmp_path / "rec.ogg"
    with sf.SoundFile(path, "w", RATE, 1, format="OGG", subtype="OPUS") as f:
        f.write(_tone(2))
    data, rate = sf.read(path, dtype="float32")
    assert rate == RATE and abs(len(data) - 2 * RATE) < RATE // 10
