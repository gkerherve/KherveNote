# CLAUDE.md — working conventions for KherveNote

Project: live note-taking for lectures, trainings and talks. Listen,
transcribe offline, mark sections, then let Claude (over MCP) turn the
session into a proper note exported to LaTeX/PDF.
Member of the **KherveTools** family (khervetools.com); conventions follow
KherveTeX (sibling repo `../KherveTeX`).
Stack: Python 3.12+, PySide6, tectonic (LaTeX engine), PyMuPDF.
Remote: https://github.com/gkerherve/KherveNote

## Branching: `dev` is the working branch

All work goes on `dev` in the main checkout
(`~/Documents/PycharmProjects/KherveNote` on the Mac). Never commit to
`main` directly; `main` lags `dev` until the user asks for a merge. Never
work in a git worktree or on a throwaway `claude/<name>` branch — the
user watches commits land on `dev` in PyCharm's Git Log.

Workflow:
1. Confirm the checkout is the main repo and on `dev`.
2. Make the edits.
3. Run `python -m pytest tests/ -q` (`py -m pytest tests/ -q` on Windows)
   and verify all tests pass.
4. `git add` the specific files changed (no bare `git add -A`).
5. Commit with a HEREDOC message explaining the **why**.
6. `git push` — never skip. If it fails, report it; do not retry
   destructively.

## Always commit and push after any change

Every change ends committed and pushed to `origin/dev`, even small ones.

## Bump the version when behaviour changes

`khervenote/__init__.py` defines `__version__` as `"<major>.<minor>"`
only. The window title shows `KherveNote v<major>.<minor>.<commits>+<sha7>`
— the last two parts come from git at start-up. **Never put a third
number in `__version__`.** Bump the minor for any user-visible change
(features, visible bug fixes, serializer output changes) in the same
commit; not for pure refactors, docs or test-only commits. Major only at
the user's request.

## Architectural invariants

- Comments only when the *why* is non-obvious.
- The **document model** (`khervenote/model.py`) is the single source of
  truth. The live page, `.knote` file, serializer and MCP tools all go
  through it. LaTeX strings are produced only in `serializer.py`.
- Tests in `tests/` cover model, file format and serializer (including
  real tectonic compiles when tectonic is installed). Changes to those
  modules come with tests in the same commit.
- Toolbar icons are drawn in `icons.py` with QPainter — no PNG/SVG files.
- The light Fusion palette in `__main__.py` is intentional.

## The continuous PDF

The default export is **one PDF page as tall as the note** (see the
docstring of `serializer.py`). Each section is typeset into a box
(`knotechunk`), boxes are stacked, and the page height is set from the
stack. Consequences that must hold for anything added to the template:

- **No floats and no footnotes** in the body — TeX cannot place them
  inside a box. Figures use `\captionof` in place.
- PDF viewers cap a page near 5.08 m; past `CONTINUOUS_LIMIT_MM` the note
  breaks into several tall pages **between sections only**.
- `paged` (A4) is the print option from the same body.

## Roadmap

| Version | Scope |
|---|---|
| 0.1 | Model, `.knote`, continuous live page, typed notes / key points / questions / images, manual sections, LaTeX + continuous/A4 PDF export |
| 0.2 | Microphone capture + **offline Whisper** (mlx-whisper on Mac, faster-whisper on Windows), pause/stop, audio kept in the `.knote` |
| 0.3 | MCP server/bridge (copied from KherveTeX `mcp_*.py`), Connect to Claude, "Summarise with Claude" via `claude -p` |
| 0.4 | Section suggestions: silence + cue phrases live, semantic via Claude |
| 0.5 | Import Word / PDF / PowerPoint notes → Claude writes the document |
| 0.6 | Open in KherveTeX (`.ktex`), KherveRef citations, slide screenshots |
| 0.7 | Installers with tectonic, warmed package cache and a Whisper model |

Transcription stays **offline** (user decision, 2026-10-05): audio never
leaves the machine.
