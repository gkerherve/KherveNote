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


def test_pending_is_the_speech_in_progress():
    c = Chunker()
    assert c.pending() is None
    c.feed(_silence(0.5))
    assert c.pending() is None
    c.feed(_tone(1.0))
    p = c.pending()
    assert p is not None and 0.2 < p.start_s < 0.5
    assert len(p.audio) < 1.5 * RATE


class _FakeStream:
    opened = []

    def __init__(self, device=None, callback=None, **kw):
        self.device = device
        self.callback = callback
        self.started = self.closed = False
        _FakeStream.opened.append(self)

    def start(self):
        if self.device == "broken":
            raise RuntimeError("busy")
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


def _fake_sd(monkeypatch, devices, default_input=0):
    import sys
    import types
    sd = types.ModuleType("sounddevice")
    sd.InputStream = _FakeStream
    sd.rescans = 0

    def query_devices(kind=None):
        if kind == "input":
            return devices[default_input]
        return devices
    sd.query_devices = query_devices
    sd._terminate = lambda: None
    sd._initialize = lambda: setattr(sd, "rescans", sd.rescans + 1)
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    return sd


def test_input_devices_one_host_api_and_unique_names(monkeypatch):
    from khervenote.audio import find_input, input_devices
    sd = _fake_sd(monkeypatch, [
        {"name": "Mic", "max_input_channels": 1, "hostapi": 0},
        {"name": "Speakers", "max_input_channels": 0, "hostapi": 0},
        {"name": "USB Mic", "max_input_channels": 1, "hostapi": 0},
        {"name": "USB Mic", "max_input_channels": 2, "hostapi": 0},
        {"name": "Mic", "max_input_channels": 1, "hostapi": 1},      # same mic, WASAPI
    ])
    assert input_devices() == [(0, "Mic"), (2, "USB Mic"), (3, "USB Mic (2)")]
    assert find_input("USB Mic (2)") == 3
    assert find_input("") is None and find_input("Unplugged") is None
    input_devices(refresh=True)
    assert sd.rescans == 1


def test_recorder_switches_microphone_into_the_same_file(monkeypatch, tmp_path):
    from khervenote.audio import RATE, Recorder
    _fake_sd(monkeypatch, [{"name": "Mic", "max_input_channels": 1, "hostapi": 0}])
    _FakeStream.opened = []
    heard = []
    rec = Recorder(str(tmp_path / "rec.ogg"), heard.append, lambda v: None, device=1)
    rec.start()
    first = _FakeStream.opened[-1]
    first.callback(np.ones((RATE // 10, 1), np.float32) * 0.1, RATE // 10, None, None)
    rec.switch(2)
    second = _FakeStream.opened[-1]
    assert first.closed and second.started and second.device == 2 and rec.device == 2
    second.callback(np.ones((RATE // 10, 1), np.float32) * 0.1, RATE // 10, None, None)
    # A device that cannot start leaves the one in use recording.
    try:
        rec.switch("broken")
    except RuntimeError:
        pass
    assert rec._stream.started and rec._stream.device == 2 and rec.device == 2
    rec.stop()
    assert rec.frames_written == 2 * (RATE // 10)
    assert len(heard) == 2
