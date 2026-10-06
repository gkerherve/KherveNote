"""Smoke-test a frozen KherveNote: start it, make it work, check the result.

    python packaging/smoke_test.py dist/KherveNote/KherveNote.exe --version 0.26.N
    python packaging/smoke_test.py dist/KherveNote.app/Contents/MacOS/KherveNote

A freeze fails quietly: a module or data file PyInstaller's analysis
missed is only found when the code that needs it runs. So this starts
the real executable with ``--self-test`` (khervenote/selftest.py) on Qt's
offscreen platform, which:

* reports the version stamped from git (checked against ``--version``);
* imports the speech stack (faster-whisper, CTranslate2, onnxruntime,
  PyAV, sounddevice, soundfile), the document readers and QtMultimedia,
  and runs the voice detector — an ONNX model inside faster-whisper;
* seeds the bundled TeX cache and typesets an example note with the
  BUNDLED tectonic in ``--only-cached`` mode: the PDF export works
  without the network;
* builds the main window on a throw-away library and settings with the
  MCP bridge on, then runs ``<exe> --mcp-server`` the way Claude Desktop
  does: initialize, tools/list, add_section, get_note;
* starts the bundled KhervePDF and hands it the PDF over its
  single-instance channel, waiting for its "ok".

The Whisper model is not bundled, so no speech is transcribed here.
Exits non-zero on the first failure.

Copyright (C) 2026 Gwilherm Kerherve
Licensed under the GNU General Public License v3.0 (see LICENSE).
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _fail(message: str):
    print(f"SMOKE TEST FAILED: {message}", flush=True)
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("exe", help="the frozen executable")
    parser.add_argument("--version", help="the <major>.<minor>.N it must report")
    parser.add_argument("--timeout", type=int, default=600,
                        help="give up after this many seconds (default 600)")
    args = parser.parse_args()

    exe = Path(args.exe).resolve()
    if not exe.is_file():
        _fail(f"{exe} not found")
    work = Path(tempfile.mkdtemp(prefix="knote_smoke_"))
    report = work / "report.json"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               KHERVENOTE_RECOVERY_DIR=str(work / "recovery"))
    try:
        proc = subprocess.run([str(exe), "--self-test", str(report)], env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=args.timeout)
    except subprocess.TimeoutExpired:
        _fail(f"the self-test did not finish within {args.timeout} s")
    if not report.is_file():
        print(proc.stdout[-3000:], proc.stderr[-3000:], sep="\n")
        _fail(f"no report written (exit code {proc.returncode})")
    data = json.loads(report.read_text(encoding="utf-8"))
    print(json.dumps(data, indent=2), flush=True)

    version = data.get("version", "")
    print(f"version reported: {version}", flush=True)
    if version.count(".") < 2 or "+" not in version:
        _fail(f"the frozen app reports {version!r} — khervenote/VERSION was not bundled")
    if args.version and version.split("+")[0] != args.version:
        _fail(f"expected version {args.version}, the app reports {version}")
    if not data.get("frozen"):
        _fail("the executable did not run as a frozen build")
    bad = {k: v for k, v in data["checks"].items() if v.startswith("FAILED")}
    if bad or not data.get("ok") or proc.returncode != 0:
        _fail(f"checks failed: {', '.join(bad) or 'exit code ' + str(proc.returncode)}")
    print("SMOKE TEST PASSED", flush=True)


if __name__ == "__main__":
    main()
