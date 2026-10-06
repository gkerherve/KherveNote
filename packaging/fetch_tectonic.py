"""Fetch the tectonic engine that ships inside KherveNote, and warm its cache.

    python packaging/fetch_tectonic.py            # binary -> packaging/bin/
    python packaging/fetch_tectonic.py --warm     # + khervenote/tectonic_cache/

The binary is the official release build for this machine (Windows x86_64
msvc, macOS arm64 / x86_64), the same pinned version KherveTeX ships.
``--warm`` typesets every example note in both layouts (continuous and
A4, with times and the transcript) into an EMPTY cache directory, then
copies that cache to ``khervenote/tectonic_cache``: so the bundle holds
what KherveNote's template needs and nothing else. The spec bundles it
and ``compiler.seed_tectonic_cache`` copies it to the user's tectonic
cache on start-up, so the first PDF export works offline.

Copyright (C) 2026 Gwilherm Kerherve
Licensed under the GNU General Public License v3.0 (see LICENSE).
"""

import argparse
import io
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

TECTONIC_VERSION = "0.17.0"
_ROOT = Path(__file__).resolve().parent.parent
_BIN = _ROOT / "packaging" / "bin"
_CACHE = _ROOT / "khervenote" / "tectonic_cache"


def _target() -> tuple[str, str]:
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "x86_64-pc-windows-msvc", "zip"
    if sys.platform == "darwin":
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        return f"{arch}-apple-darwin", "tar.gz"
    return "x86_64-unknown-linux-musl", "tar.gz"


def fetch() -> Path:
    triple, ext = _target()
    name = f"tectonic-{TECTONIC_VERSION}-{triple}.{ext}"
    url = ("https://github.com/tectonic-typesetting/tectonic/releases/download/"
           f"tectonic%40{TECTONIC_VERSION}/{name}")
    exe_name = "tectonic.exe" if sys.platform == "win32" else "tectonic"
    have = _BIN / exe_name
    if have.is_file():
        try:
            v = subprocess.run([str(have), "--version"], capture_output=True,
                               text=True, timeout=30).stdout
        except OSError:
            v = ""
        if TECTONIC_VERSION in v:
            return have
    print(f"Downloading {url}", flush=True)
    try:        # python.org's macOS Python has no CA bundle of its own
        import certifi
        import ssl
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = None
    data = urllib.request.urlopen(url, timeout=120, context=ctx).read()
    _BIN.mkdir(parents=True, exist_ok=True)
    out = _BIN / exe_name
    if ext == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            member = next(n for n in zf.namelist() if n.endswith(exe_name))
            out.write_bytes(zf.read(member))
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            member = next(m for m in tf.getmembers()
                          if m.isfile() and m.name.endswith(exe_name))
            out.write_bytes(tf.extractfile(member).read())
    out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"tectonic {TECTONIC_VERSION} -> {out} "
          f"({out.stat().st_size / 1e6:.1f} MB)", flush=True)
    return out


def warm(tectonic: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(_ROOT))
    from khervenote import examples
    from khervenote.serializer import to_latex

    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "cache"
        env = dict(os.environ, TECTONIC_CACHE_DIR=str(cache))
        failed = []
        for ex in examples.EXAMPLES:
            note = examples.build(ex)
            for layout in ("continuous", "paged"):
                work = Path(tmp) / "work"
                shutil.rmtree(work, ignore_errors=True)
                work.mkdir()
                tex = work / "note.tex"
                tex.write_text(to_latex(note, layout, show_times=True, transcript=True),
                               encoding="utf-8")
                proc = subprocess.run([str(tectonic), "--outdir", str(work), str(tex)],
                                      env=env, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace",
                                      stdin=subprocess.DEVNULL, timeout=900)
                ok = proc.returncode == 0 and (work / "note.pdf").is_file()
                print(f"  {ex.title[:50]!r} {layout}: {'ok' if ok else 'FAILED'}", flush=True)
                if not ok:
                    failed.append((ex.title, layout, (proc.stdout + proc.stderr)[-800:]))
        if failed:
            for f in failed:
                print(*f, sep="\n", flush=True)
            raise SystemExit(f"{len(failed)} example compiles failed")
        shutil.rmtree(_CACHE, ignore_errors=True)
        shutil.copytree(cache, _CACHE)
    size = sum(p.stat().st_size for p in _CACHE.rglob("*") if p.is_file())
    n = sum(1 for p in _CACHE.rglob("*") if p.is_file())
    print(f"warmed cache -> {_CACHE} ({n} files, {size / 1e6:.0f} MB)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--warm", action="store_true",
                    help="also build khervenote/tectonic_cache")
    args = ap.parse_args()
    exe = fetch()
    if args.warm:
        warm(exe)


if __name__ == "__main__":
    main()
