# KherveNote

Live notes for lectures, trainings and talks — written on one continuous
page while you listen, exported as a clean LaTeX note and a **continuous
PDF** (one page as long as the note, with bookmarks per section) or A4
pages for printing.

Part of the [KherveTools](https://khervetools.com) family, alongside
[KherveTeX](https://github.com/gkerherve/kherveTeX).

## Using it

- Type in the box at the bottom and press **Enter** — the note lands on
  the page with its time in the session. Shift+Enter for a new line;
  lines starting with `-` become bullets.
- Lists: `- ` (or `*`, `•`) starts a bullet, `1. ` a numbered item. Shift+Enter
  continues the list, **Tab** makes a sub-item (numbered sub-items read
  1.1, 1.2, 1.2.1), Shift+Tab goes back, an empty item ends the list. The
  **Bullets** / **Numbering** buttons turn the current line into an item.
- **New section** (Ctrl+Return) starts a section now; right-click any
  note → *Start a section here* to start one after the fact.
- **Key point** (Ctrl+Shift+K) and **Question** (Ctrl+Shift+Q) flag what
  you type next; **Insert image** or Ctrl+Shift+V adds a picture or a
  slide screenshot.
- **Export PDF** (Ctrl+E) — continuous page by default, A4 under
  *Export ▸ A4 pages*. **Export LaTeX** writes a standalone `.tex` and
  its `assets/` folder.
- Notes are saved as `.knote` files (a zip of the note and its images).

## Coming next

Offline speech-to-text with Whisper (v0.2), summaries and note writing
by Claude over MCP (v0.3), automatic section detection (v0.4), import of
existing Word/PDF/PowerPoint notes (v0.5). See `CLAUDE.md` for the
roadmap.

## Running from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python KherveNote.py
```

PDF export needs [tectonic](https://tectonic-typesetting.github.io/)
(`brew install tectonic` on a Mac).

## Licence

GPL v3 — © 2026 Gwilherm Kerherve
