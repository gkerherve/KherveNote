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
- The notes library (`library.py`, Qt-free; `library_panel.py`) is a
  plain folder tree on disk (`~/Documents/KherveNote` by default):
  folders are folders, notes are `.knote` files. Never keep a separate
  index or database the files could disagree with. Notes autosave
  (2 s after a change, and before switching / quitting); deleting goes
  to the Trash, never a hard delete. Tests must point `library/root`
  at a temporary folder.
- **Notes must never be lost.** Before a note file is overwritten its
  current version goes to `<library>/.history/<meta.id>/` (`history.py`);
  restoring always makes a new file. A file whose mtime changed since
  this window read or wrote it is never overwritten (a copy is saved
  instead). Only one KherveNote runs at a time (`QLockFile` in
  `__main__`). Leaving a note finishes listening and stops the AI first;
  an AI answer for a note that is no longer open is dropped, never
  written into another note. Recordings are written (flushed each
  second) to `recovery.recovery_dir()`, not the note's temporary folder,
  and that copy is deleted only after the note holding it is saved; the
  next start offers any left behind. Tests set `KHERVENOTE_RECOVERY_DIR`.
- The page is one seamless surface: no page edges, borders or desk
  colour around the text.

## The user manual

`khervenote/manual.md` is the manual — shown in the app (Help ▸ User
manual, F1) and linked from the README. **Update it in the same commit
as any user-visible change**: a new button, shortcut, menu or behaviour.

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
| Camera | Take a picture with the computer's camera | done (0.4) |
| Listen | Microphone + **offline Whisper** (faster-whisper) writing into the page | done (0.5) |
| Local AI | Right-click Summarise / Rephrase with **Ollama** | done (0.6) |
| Claude | MCP server/bridge (from KherveTeX `mcp_*.py`), "Summarise with Claude" | later |
| Sections | Section suggestions: silence + cue phrases, then semantic | later |
| Documents | Attach PDF / Word / PowerPoint; sections, find, summarise, ask the AI | done (0.12) |
| Links | Open in KherveTeX, KherveRef citations | later |
| KhervePDF | PDFs in notes open in KhervePDF; its saved annotations stay in the note | done (0.20) |
| Release | CI installers (Windows Inno, macOS DMGs) with tectonic + warmed cache | done (0.26) |
| Release 2 | Ship KhervePDF with KherveNote; optional bundled Whisper model | later |

Attached documents sit **in the page** as an inline icon (an image whose
resource name is `knote-attachment:<path>|<name>`, drawn by
`editor.chip_image`) and are `attachment` blocks in the model; deleting
the icon removes the document (Undo restores it), and `Note.attachments`
is derived from those blocks on save. They are read (`documents.py`,
Qt-free) into sections that
never share text (a PDF's bookmarks are cut where their title is
printed). Questions send only the best-matching passages (BM25, ~9000
characters) and long summaries go part by part, so a small local model
copes with a long manual; `num_ctx` is raised to fit.

PDFs open in **KhervePDF** (sibling repo `../KhervePDF`; `khervepdf_link.py`).
The contract is KhervePDF's single-instance channel — a JSON line
`{"cmd": "open", "paths": [...]}` on the local socket `khervepdf-<user>`
(`KHERVEPDF_IPC_NAME` overrides it in tests) — else KhervePDF is started
(installed app, `pdf/khervepdf` setting, or the sibling checkout with its
`.venv`). Never import KhervePDF. It opens the note's own copy of the
file (new attachments live at `assets/att-<id>/<Name>.pdf`), watched with
`QFileSystemWatcher` so annotations saved there return into the note.
The release installers must ship KhervePDF with KherveNote.

The local AI (`local_ai.py`) talks to Ollama over plain HTTP
(`OLLAMA_HOST`, default `localhost:11434`) and sends `think: false` so
reasoning models answer in seconds; it must never need a cloud key.

The speech transcript is `Note.transcript` (segments with their session
time), shown in the Speech panel (`speech_panel.py`) beside the notes —
not mixed into them. Notes and speech are linked by time: a paragraph is
timed when its first character is typed (`BlockMeta`), times show as the
time of day (`Note.time_label`), and "fill in from the speech" sends the
AI the segments said during a section — shifted earlier by the lead
time (`speech/lead`, 2 min by default: people write after they hear),
and confirmed by the user in `SpeechRangeDialog` (From/To clock times,
live highlight, "use my selection"). Long AI jobs go through
`MainWindow._run_ai` with a `local_ai.Job`, so the AI bar can show
steps, the streamed text and Cancel.

Microphone and camera permission (`permissions.py`): the macOS app
bundle's Info.plist **must** carry `NSMicrophoneUsageDescription` and
`NSCameraUsageDescription`, or Qt refuses both at once. Run from
source, Qt's permission API is skipped — macOS asks on behalf of the
terminal / IDE — and a microphone that only sends zeros (the way macOS
blocks it) is reported after 5 s.

Transcription stays **offline** (user decision, 2026-10-05): audio never
leaves the machine.

## Packaging and releases

Release version = `<__version__>.<commit count>` (e.g. `0.26.27`), the
same number the window title shows without the `+sha`.
`packaging/spec_common.py` computes it and writes the git-ignored
`khervenote/VERSION`, which `mainwindow.version_string()` reads first in a
frozen build (no `.git` there). Builds refuse a shallow clone.

All release artifacts come from GitHub Actions, from **one tagged commit
on `dev`** (workflows only build and upload artifacts — they never create
a release):

- `git tag v<ver> && git push origin v<ver>` → `windows-build.yml`:
  `KherveNote-Setup-<ver>.exe` (per-user Inno, `.knote` associated),
  `KherveNote-<ver>-portable.zip`, stable `KherveNote-Setup.exe`; the
  installer is installed silently, smoke-tested and uninstalled on CI.
- `git tag macos-v<ver> && git push origin macos-v<ver>` →
  `macos-build.yml`: arm64 (macos-14) and x86_64 (macos-15-intel)
  `KherveNote-<ver>-macOS-<arch>.dmg` + stable `KherveNote-macOS-<arch>.dmg`
  + `.sha256`, ad hoc signed. Info.plist carries the microphone and
  camera usage strings; `packaging/macos/entitlements.plist` adds
  audio-input / camera for a future Developer ID (hardened runtime) build.

Each job runs the tests, then `packaging/smoke_test.py`, which starts the
frozen app with `--self-test` (`khervenote/selftest.py`): speech stack
imports + the VAD model, an **offline** PDF from the bundled tectonic and
cache, the main window on a throw-away library. Local Mac dry run:
`python packaging/build_macos.py` (`CI=1` skips create-dmg's Finder
layout, which waits on an Automation permission prompt).

What is bundled vs fetched on first use (decided 2026-10-06):

- **Bundled:** tectonic 0.17.0 (official binary, `fetch_tectonic.py`) and
  a TeX cache warmed by typesetting every example note in both layouts
  (~45 MB, `khervenote/tectonic_cache`, git-ignored). On start-up a frozen
  build copies it into tectonic's own cache (`compiler.seed_tectonic_cache`,
  never overwriting), so the first PDF export works offline. The speech
  engine (faster-whisper, CTranslate2, onnxruntime, PyAV) is code and is
  bundled.
- **First use:** the Whisper model (Small, the default, ~480 MB) downloads
  once on the first Listen — the recording runs meanwhile — then works
  offline. Bundling it would more than double the installer for a model
  some users never need or replace with another size.
- **Not bundled:** Ollama and its models (separate install), KhervePDF
  (found when installed; shipping it inside is "Release 2").
