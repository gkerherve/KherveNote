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

- **Notes panel** (left): every note, in folders you arrange by dragging,
  with a search box that looks inside the notes. Notes save themselves
  into *Documents ▸ KherveNote*; the open note lists its sections.
- Write straight onto the page — it is one endless sheet, no page edges.
  Each paragraph shows the time in the session it was written.
- **Styles** (the picker in the toolbar, or Ctrl+0 / 1 / 2 / 3): Text,
  Section, Subsection, Sub-subsection, Key point (Ctrl+Shift+K), Question
  (Ctrl+Shift+Q), Transcript. Ctrl+Return starts a new section. Title,
  speaker, date (with a calendar) and place sit at the top.
- **Bold / italic / underline**: Ctrl+B / I / U. **Equations** as in
  LaTeX — `$…$` in a sentence, `$$…$$` on their own line — become real
  maths in the PDF; Greek letters, symbols and H₂O-style sub/superscripts
  print correctly too.
- **Example notes** (*Help ▸ Example notes*): eight worked lectures for
  scientists — maths, physics, chemistry and four in materials science —
  with equations and the speech beside them.
- **Lists**: type `- ` for a bullet or `1. ` for a numbered item (or use
  the toolbar buttons). **Tab** makes a sub-item — numbered sub-items
  export as 1.1, 1.2, 1.2.1 — Shift+Tab goes back, Enter on an empty item
  leaves the list.
- **Listen** (Ctrl+L): what is said is written in the **Speech panel**
  beside your notes, line by line, each with the time of day it was said
  — the words appear live as they are spoken. Your own lines carry the
  time they were written, so the two are linked: click a paragraph to
  highlight what was said just before, click a time to jump to what you
  were writing. The AI can **fill in a section** from what was said, or
  **make notes from the speech**. Speech-to-text is **Whisper running on
  this computer** (faster-whisper): the audio never leaves it. The model
  downloads once (*Speech ▸ Model*), then works offline.
- **Undo / Redo** (Ctrl+Z / Ctrl+Shift+Z, or the ↶ ↷ buttons) take back
  anything, including what the AI or the microphone wrote.
- **Local AI** (Ollama, on this computer): right-click on the page, the
  ✦ toolbar button or the *AI* menu —
  - *Rephrase* (Ctrl+Shift+R) rewrites the paragraph or selection as
    clear sentences; a rewritten transcript becomes your own text.
  - *Summarise* (Ctrl+Alt+S) adds the key points of the section (or the
    selection) as a key-point box.
  - *Summarise the whole note* writes the summary at the top.
  A bar above the page shows the AI at work (step, time, the text as it
  is written, Cancel). Ctrl+Z undoes any of it.
  Needs [Ollama](https://ollama.com): *AI ▸ Set up the local AI…* links
  to it, installs a model in one click and compares them (Qwen, Granite,
  Gemma, Llama).
- **Documents**: drag a PDF, Word, PowerPoint or text file onto the page
  (or **Insert PDF**). It sits in the note as an icon; click a PDF to open
  it in [KhervePDF](https://github.com/gkerherve/KhervePDF) (annotations
  saved there stay in the note); right-click for its sections, a search
  through it, a summary of the whole or of every section, or a question
  to the local AI — answers are written into the note as sections.
- **Images**: the toolbar button, or paste a screenshot with Ctrl+V.
- **Camera** (Ctrl+Shift+P): take a picture of a whiteboard, a slide or
  a handout with the computer's camera; Space takes it.
- **Theme**: *View ▸ Theme* — System, Light or Dark (a black page).
- **Export PDF** (Ctrl+E) — continuous page by default, A4 under
  *Export ▸ A4 pages*. **Export LaTeX** writes a standalone `.tex` and
  its `assets/` folder.
- Notes are `.knote` files (a zip of the note, its images and recordings).

## Coming next

Claude over MCP and automatic section detection. See `CLAUDE.md` for
the roadmap.

## Running from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python KherveNote.py
```

Installers for Windows and macOS (Apple Silicon and Intel) bundle
tectonic and the TeX files the template needs, so PDF export works out of
the box; the speech model downloads once on first use. From source,
PDF export needs [tectonic](https://tectonic-typesetting.github.io/)
(`brew install tectonic` on a Mac).

## Licence

GPL v3 — © 2026 Gwilherm Kerherve
