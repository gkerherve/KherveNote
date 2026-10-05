# KherveNote

Live notes for lectures, trainings and talks — written on one continuous
page while you listen, exported as a clean LaTeX note and a **continuous
PDF** (one page as long as the note, with bookmarks per section) or A4
pages for printing.

Part of the [KherveTools](https://khervetools.com) family, alongside
[KherveTeX](https://github.com/gkerherve/kherveTeX).

## Using it

The full **[user manual](khervenote/manual.md)** is also in the app:
*Help ▸ User manual* (F1).

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
- **Listen** (the microphone, Ctrl+L): the words appear on the page *as
  they are spoken* (grey italic, refreshed about twice a second), then
  settle into the final transcript a second after the speaker pauses.
  A "● listening…" mark sits where the words will appear, and shows the
  download / loading state the first time. Keep typing your own notes
  meanwhile — the speech goes in above the line you are writing. Press
  again to stop — or just press Space or Return in the page (switch that
  off under *Speech*).
- **Undo / Redo** (Ctrl+Z / Ctrl+Shift+Z, or the ↶ ↷ buttons) take back
  anything, including what the AI or the microphone wrote. Speech-to-text is **Whisper running on this computer**
  (faster-whisper): the audio never leaves it. The model downloads once
  (*Speech ▸ Model*: tiny … large; Small by default), then it works
  offline. *Speech ▸ Language* and *Speech ▸ Microphone* choose the rest.
  The recording is kept inside the `.knote`.
- **Local AI** (Ollama, on this computer): right-click on the page, the
  ✦ toolbar button or the *AI* menu —
  - *Rephrase* (Ctrl+Shift+R) rewrites the paragraph or selection as
    clear sentences; a rewritten transcript becomes your own text.
  - *Summarise* (Ctrl+Alt+S) adds the key points of the section (or the
    selection) as a key-point box.
  - *Summarise the whole note* writes the summary at the top.
  Pick the model under *AI ▸ Local AI model*. Ctrl+Z undoes any of them.
  Needs [Ollama](https://ollama.com) running with at least one model
  (e.g. `ollama pull qwen3.5:4b`).
- **Images**: the toolbar button, or paste a screenshot with Ctrl+V.
- **Camera** (Ctrl+Shift+P): take a picture of a whiteboard, a slide or
  a handout with the computer's camera; Space takes it.
- **Theme**: *View ▸ Theme* — System, Light or Dark (a black page).
- **Export PDF** (Ctrl+E) — continuous page by default, A4 under
  *Export ▸ A4 pages*. **Export LaTeX** writes a standalone `.tex` and
  its `assets/` folder.
- Notes are saved as `.knote` files (a zip of the note and its images).

## Coming next

Claude over MCP, automatic section detection, and import of existing Word / PDF /
PowerPoint notes. See `CLAUDE.md` for the roadmap.

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
