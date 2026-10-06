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


def bundled_cache() -> Path | None:
    """The warmed TeX cache a release build carries (``tectonic_cache``
    beside the package), or None when run from source."""
    if not getattr(sys, "frozen", False):
        return None
    d = Path(sys._MEIPASS) / "khervenote" / "tectonic_cache"
    return d if d.is_dir() else None


def tectonic_cache_dir(tectonic: str) -> Path | None:
    """The root of *tectonic*'s cache (it differs per OS, so the binary
    itself is asked).  ``user-cache-dir`` names ``<root>/bundles``; the
    root also holds ``formats/``, and the bundled cache mirrors the root."""
    kw: dict = dict(stdin=subprocess.DEVNULL, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=15)
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run([tectonic, "-X", "show", "user-cache-dir"], **kw)
    except (OSError, subprocess.SubprocessError):
        return None
    # stdout only: tectonic writes a "note: ..." line to stderr.
    lines = (proc.stdout or "").strip().splitlines()
    path = Path(lines[-1].strip()) if proc.returncode == 0 and lines else None
    if path is None or not path.is_absolute():
        return None
    return path.parent if path.name == "bundles" else path


def seed_tectonic_cache() -> int:
    """Copy the bundled TeX cache into the user's tectonic cache, so the
    first PDF export works offline.  Files already there are kept.
    Returns the number of files copied."""
    src = bundled_cache()
    tectonic = find_tectonic()
    if src is None or tectonic is None:
        return 0
    dest = tectonic_cache_dir(tectonic)
    if dest is None:
        return 0
    copied = 0
    for path in src.rglob("*"):
        target = dest / path.relative_to(src)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
    return copied


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
