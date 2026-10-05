# KherveNote — tectonic compiler
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile a note's LaTeX to PDF with tectonic.

Trimmed from KherveTeX's ``compiler.py``: the same binary search, the
same cache-first run with one online retry when the cache lacks a file
or font, and stdin closed so a TeX error can never wait for input.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_MISSING_FILE_RE = re.compile(r"File `([^']+)' not found")
_MISSING_FONT_RE = re.compile(
    r"Font [^=\s]+=\[?([^\]:;\s]+)[^\n]* not loadable: Metric \(TFM\) file"
    r"|Could not locate a virtual/physical font named ([^\s.]+)"
    r"|Cannot proceed without \.vf or \"physical\" font for (\S+)")
_NETWORK_ERROR_RE = re.compile(
    r"error sending request|failed to (?:fetch|connect)|dns error|"
    r"tcp connect error|Connection refused|network is unreachable|"
    r"timed out|failed to lookup address", re.IGNORECASE)


@dataclass
class CompileResult:
    ok: bool
    pdf_path: Path | None
    log: str
    error: str | None


def find_tectonic() -> str | None:
    if getattr(sys, "frozen", False):
        for name in ("tectonic.exe", "tectonic"):
            bundled = Path(sys._MEIPASS) / name
            if bundled.exists():
                return str(bundled)
    found = shutil.which("tectonic")
    if found:
        return found
    for c in (Path.home() / "bin" / "tectonic.exe",
              Path.home() / "bin" / "tectonic",
              Path.home() / ".cargo" / "bin" / "tectonic",
              Path.home() / "scoop" / "shims" / "tectonic.exe",
              Path("/opt/homebrew/bin/tectonic"),
              Path("/usr/local/bin/tectonic")):
        if c.exists():
            return str(c)
    return None


def _run(cmd: list[str], timeout: float) -> tuple[int, str]:
    kw: dict = dict(stdin=subprocess.DEVNULL, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=timeout)
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.run(cmd, **kw)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def compile_tex(tex_source: str, build_dir: Path, asset_dir: Path | None = None,
                basename: str = "note") -> CompileResult:
    """Write *tex_source* into *build_dir* and compile it there.

    The note's ``assets/`` are copied next to the ``.tex`` because
    tectonic resolves ``\\includegraphics`` relative to the source file.
    """
    tectonic = find_tectonic()
    if tectonic is None:
        return CompileResult(False, None, "",
                             "tectonic is not installed. Install it from "
                             "https://tectonic-typesetting.github.io/")
    build_dir.mkdir(parents=True, exist_ok=True)
    if asset_dir is not None and (asset_dir / "assets").is_dir():
        shutil.copytree(asset_dir / "assets", build_dir / "assets",
                        dirs_exist_ok=True)
    tex_path = build_dir / f"{basename}.tex"
    tex_path.write_text(tex_source, encoding="utf-8")
    pdf_path = build_dir / f"{basename}.pdf"
    pdf_path.unlink(missing_ok=True)

    def run(only_cached: bool) -> tuple[int, str]:
        cmd = [tectonic] + (["--only-cached"] if only_cached else []) + [
            "--keep-logs", "--outdir", str(build_dir), str(tex_path)]
        # Cache-only takes seconds; a run that downloads may need minutes.
        return _run(cmd, 120 if only_cached else 900)

    try:
        code, log = run(True)
        missing = _MISSING_FILE_RE.findall(log) + [
            next(g for g in m if g)
            for m in _MISSING_FONT_RE.findall(log.replace("\n", ""))]
        if code != 0 or missing or not pdf_path.exists():
            cached_log = log
            code, log = run(False)
            if code != 0 and _NETWORK_ERROR_RE.search(log):
                names = ", ".join(sorted(set(missing))) or "some TeX files"
                return CompileResult(
                    False, None, cached_log + "\n--- online retry ---\n" + log,
                    f"Offline, and {names} not in the local TeX cache yet. "
                    "Connect once to compile this note.")
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, "", "tectonic timed out")

    if code == 0 and pdf_path.exists():
        return CompileResult(True, pdf_path, log, None)
    return CompileResult(False, None, log, _first_tex_error(log)
                         or f"tectonic exited with code {code}")


def _first_tex_error(log: str) -> str | None:
    for line in log.splitlines():
        if line.startswith("error:") or line.startswith("!"):
            return line.lstrip("!").strip()
    return None


def pdf_page_heights_mm(pdf_path: Path) -> list[float]:
    import pymupdf
    with pymupdf.open(pdf_path) as doc:
        return [p.rect.height * 25.4 / 72 for p in doc]
