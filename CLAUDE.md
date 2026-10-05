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
  truth for everything persisted or exported. The `.knote` file,
  serializer and AI tools read the model; the page (`editor.py`, one
  endless `QTextEdit` the user writes on directly) converts to and from
  it only through `document_to_note` / `load_note`. LaTeX strings are
  produced only in `serializer.py`.
- In the editor a paragraph's kind lives in its block format
  (`KIND`/`LEVEL`), its capture time in block user data (`BlockMeta`) so
  stamping never touches the undo stack. Sections are level-1 headings.
- Tests in `tests/` cover model, file format and serializer (including
  real tectonic compiles when tectonic is installed). Changes to those
  modules come with tests in the same commit.
- Toolbar icons are drawn in `icons.py` with QPainter — no PNG/SVG files.
- Themes (`theme.py`: System / Light / Dark) always set an explicit
  Fusion palette — never leave the platform palette in charge (the
  Windows dark theme made drawn icons invisible). Colours come from
  `theme.color()`, never hard-coded in widgets; icons are redrawn on a
  theme change.
- The page is one seamless surface: no page edges, borders or desk
  colour around the text.

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

| Phase | Scope | State |
|---|---|---|
| Notes | Model, `.knote`, LaTeX + continuous/A4 PDF | done (0.1) |
| Lists | Bullet / numbered / nested lists | done (0.2) |
| Editor | Write directly on one endless page, headings, B/I/U, themes | done (0.3) |
| Camera | Take a picture with the computer's camera | 0.4 |
| Listen | Microphone + **offline Whisper** (faster-whisper) writing into the page | 0.5 |
| Local AI | Right-click Summarise / Rephrase with **Ollama** | 0.6 |
| Claude | MCP server/bridge (from KherveTeX `mcp_*.py`), "Summarise with Claude" | later |
| Sections | Section suggestions: silence + cue phrases, then semantic | later |
| Import | Word / PDF / PowerPoint notes → a proper document | later |
| Links | Open in KherveTeX, KherveRef citations | later |
| Release | Installers with tectonic, warmed cache and a Whisper model | later |

Transcription stays **offline** (user decision, 2026-10-05): audio never
leaves the machine.
