# KherveNote

Live notes for lectures, trainings and talks — written on one continuous
page while you listen, exported as a clean LaTeX note and a **continuous
PDF** (one page as long as the note, with bookmarks per section) or A4
pages for printing.

Part of the [KherveTools](https://khervetools.com) family, alongside
[KherveTeX](https://github.com/gkerherve/kherveTeX).

## Using it

- Write straight onto the page — it is one endless sheet, no page edges.
  Each paragraph shows the time in the session it was written.
- **Styles** (the picker in the toolbar, or Ctrl+0 / 1 / 2 / 3): Text,
  Section, Subsection, Sub-subsection, Key point (Ctrl+Shift+K), Question
  (Ctrl+Shift+Q), Transcript. Ctrl+Return starts a new section. The
  *Sections* panel jumps to any heading.
- **Bold / italic / underline**: Ctrl+B / I / U.
- **Lists**: type `- ` for a bullet or `1. ` for a numbered item (or use
  the toolbar buttons). **Tab** makes a sub-item — numbered sub-items
  export as 1.1, 1.2, 1.2.1 — Shift+Tab goes back, Enter on an empty item
  leaves the list.
- **Images**: the toolbar button, or paste a screenshot with Ctrl+V.
- **Theme**: *View ▸ Theme* — System, Light or Dark (a black page).
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
