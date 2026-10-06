# KherveNote — user manual

KherveNote is for taking notes while someone speaks: a lecture, a
training, a meeting, a talk. You write on one endless page, the
microphone can write down what is said, a local AI can tidy it up, and
the result exports as a clean LaTeX / PDF note.

On a Mac, **Ctrl** in this manual is the **⌘ Command** key.

---

## 1. The page

The page has no edges: it is one long sheet that grows as you write.
Click anywhere and type, as in a notepad.

- At the top: the **title** of the talk, then **speaker**, **date** and
  **place** — click any of them to change it. The 📅 button next to the
  date opens a calendar.
- To the left of each paragraph, in grey: the **time of day** it was
  written, to the second (e.g. 14:31:04) — taken when you start typing
  the line. *View ▸ Show times as the time of day* switches to the time
  since the note began (31:04) instead.
## 2. Your notes — the Notes panel

The panel on the left holds **every note**, in folders, newest first,
with its date.

- **Click** a note to open it. The open note is in bold, with its
  sections listed under it — click a section to jump there.
- **+ Note** starts a new note in the selected folder; **+ Folder** makes
  a folder inside it. Right-click for *New note here*, *New folder here*,
  *Rename*, *Show in Finder* and *Move to Trash*.
- **Drag** notes and folders to move them into another folder.
- **Search**: type in the box at the top. It finds notes by title, date,
  speaker, place and **anything written in them**, and folders by name.
  Clear the box to see everything again.

**Notes save themselves** a couple of seconds after every change, and
when you open another note or quit — there is no need to press Save.
A new note appears in the list straight away (*New note — start writing
to keep it*) and gets its file as soon as something is written in it,
named after its title. A note without a title is listed by its first
words.

**Your notes are kept safe:**

- **Earlier versions** — before a note is saved over, the version on
  disk is kept (one every few minutes, the last 40). *File ▸ Earlier
  versions of this note…* opens any of them **as a copy**; the note you
  have is never changed by it.
- **One KherveNote at a time** — starting it a second time says so and
  closes: two windows on the same note would save over each other.
- **Changed elsewhere?** If a note's file was changed outside this window
  (by a sync program, say), KherveNote does not save over it: your
  version is saved as a separate copy next to it, and you are told.
- **Leaving a note** (opening another, *+ Note*, quitting) first finishes
  any listening — the last words and the recording stay with that note —
  and stops any AI that was writing into it.

All notes are ordinary `.knote` files in **Documents ▸ KherveNote**, the
folders are ordinary folders: you can back them up or sync them like
any files (earlier versions are in the hidden `.history` folder there).
*File ▸ Notes folder…* chooses another place.

## 3. Sections and styles

Every paragraph has a **style**. The style picker in the toolbar shows
the style of the paragraph the cursor is in, and changes it.

| Style | What it is for | Shortcut |
|---|---|---|
| Text | Ordinary notes | Ctrl+0 |
| **Section** | Starts a new section (a big heading) | Ctrl+1 |
| Subsection | A heading inside a section | Ctrl+2 |
| Sub-subsection | A smaller heading | Ctrl+3 |
| Key point | Something important — shown in an orange box ★ | Ctrl+Shift+K |
| Question | Something to ask or look up — blue italics ? | Ctrl+Shift+Q |
| Transcript | What the microphone wrote — grey | |

**To start a new section** while the speaker moves on, either:

- press the **New section** button in the toolbar (or **Ctrl+Return**),
  then type its title; or
- type the title on a line of its own and press **Ctrl+1**.

Press Return after a heading and you are back to ordinary text.

## 4. Writing

- **Bold / italic / underline**: Ctrl+B / Ctrl+I / Ctrl+U, or the
  **B I U** buttons.
- **Bullet list**: type `- ` (dash, space) at the start of a line, or
  press the bullets button (Ctrl+Shift+8).
- **Numbered list**: type `1. ` at the start of a line, or press the
  numbering button (Ctrl+Shift+7).
- In a list, **Return** starts the next item, **Tab** makes a sub-item,
  **Shift+Tab** moves it back out, and **Return on an empty item** ends
  the list. Numbered sub-items come out as 1.1, 1.2, 1.2.1 in the PDF.
- **Shift+Return** starts a new line inside the same paragraph.

**Equations** are written as in LaTeX and come out as real maths in the
PDF:

- in a sentence: `$E = h\nu - \phi$`, or `\(k_1\)`
- on a line of their own: `$$k = A\exp(-E_a/RT)$$`, or `\[ … \]`
- a `$` followed by a space (“it costs $5”) stays a dollar sign.

On the page you see what you typed; the PDF shows the equation. Greek
letters and symbols typed directly (λ, ΔH, ≈, →, °) and sub- and
superscripts (H₂O, Al³⁺, cm⁻¹) also print correctly.

**Example notes** — *Help ▸ Example notes* puts eight worked lecture
notes into an *Examples* folder of the Notes panel: linear algebra,
quantum mechanics, thermodynamics, reaction kinetics, XPS, X-ray
diffraction, solid electrolytes for batteries and mechanical properties
of metals. Each has sections, lists, key points, questions, equations
and the speech that was heard beside it — try *Fill in my section*,
the summaries or *Export PDF* on them. Editing them is safe: they are
never written over.

## 5. Listening — the speech beside your notes

Press **Listen** (in the toolbar, at the top of the **Speech** panel on
the right, or **Ctrl+L**).

- **Your notes** stay on the page: you write, make sections and
  headings as usual.
- **What is said** is written in the **Speech** panel on the right, one
  line per stretch of speech, each with the **time it was said**
  (14:31:04). The words being spoken appear live, in italics, under the
  last line, and settle into a new line a second after the speaker
  pauses.
- Press **Listen** again to stop; you can switch it on and off as often
  as you like — new lines are added below.

**The two are linked by time:**

- Click in a paragraph of your notes: the speech said **before** you wrote
  it is highlighted in the Speech panel — as far back as the lead time
  below (two minutes unless you change it).
- Click a **time** in the Speech panel: the page jumps to what you were
  writing then (it flashes briefly).
- Right-click a line (or a selection) of speech: *Insert into my notes*,
  *Show my notes at this time*, *Make notes from the selection*.

**…and by the AI** (buttons under the Speech panel, or the *AI* menu):

- **Fill in my section** — first a small window asks **which speech goes
  with the section**: *From* and *To* times, already filled in, with the
  matching lines listed and highlighted in the Speech panel as you change
  them. *Use the lines I selected* takes exactly the lines you selected
  in the Speech panel; *All the speech* takes everything. Then the AI
  compares that speech with your notes and adds the points you missed
  under a **From the speech (14:31:04–14:38:12)** heading at the end of
  the section.
- **Fill in every section from the speech** (*AI* menu) — the same for
  each section in turn, with the suggested times.

**The speech comes before the notes.** People usually write a section
heading *after* hearing what it is about — often a minute or two later.
So the speech of a section is taken from a little **before** its heading
was written until the same lead before the next heading (or the end).
*Speech ▸ The speech comes before my notes by…* sets that lead: none,
30 seconds, 1, **2 (the default)** or 5 minutes.
- **Make notes from the speech** — turns what was said (the selected
  lines, or all of it) into structured notes with headings, added at the
  end of the note.

*Speech ▸ Write the speech into the page* puts the speech into the page
itself instead, as in earlier versions, above the line you are typing.
*Speech ▸ Stop listening when I press Space or Return* (off by default)
ends the listening as soon as you type.

Everything happens **on this computer**: the speech recognition
(Whisper) runs locally and the audio never leaves it. The recording is
kept inside the note file.

**The first time** the speech model is downloaded once (the page shows
the progress); after that it works without internet.

*Speech* menu:

- **Model** — Tiny / Base are fastest, Small (default) is a good
  balance, Medium and Large are more accurate but slower.
- **Language** — leave on *Detect automatically*, or choose it to make
  recognition more reliable.
- **Microphone** — which input to use (built-in, headset, USB mic).

**If nothing is written**: macOS may be blocking the microphone.
KherveNote warns you after a few seconds of pure silence. Allow it in
*System Settings ▸ Privacy & Security ▸ Microphone* (when running from
PyCharm or Terminal, allow that app), then restart it.

## 6. The local AI (Ollama)

KherveNote can use an AI model running **on your own computer** through
[Ollama](https://ollama.com) — nothing is sent to the cloud. Right-click
on the page, use the **AI** button in the toolbar, or the *AI* menu:

- **Rephrase** (Ctrl+Shift+R) — rewrites the paragraph (or the selected
  text) as clear, well-written sentences. A messy transcript becomes
  clean prose, and becomes your own text.
- **Summarise** (Ctrl+Alt+S) — adds the key points of the current
  section (or of the selection) as a key-point box after it.
- **Summarise the whole note** — writes the summary at the top of the
  note.
- **Revise with directions…** (Ctrl+Shift+D) — rewrites the selected
  text, or the whole section you are in, the way you tell it: “shorter,
  as bullet points”, “in French”, “a heading per topic”, “explain the
  terms”. A box asks for the directions (your last ones are filled in).
  Headings and lists in the answer become real headings and lists.

Choose the model under *AI ▸ Local AI model*; a general model such as
qwen3.5 is picked by default.

### Setting up the local AI

*AI ▸ Set up the local AI…* shows whether Ollama is running, links to
the download, and installs a model with one click.

1. **Install Ollama** — download it from
   [ollama.com/download](https://ollama.com/download) (Mac, Windows,
   Linux) and open it once; on a Mac it then runs in the menu bar. On a
   Mac you can also type `brew install ollama` in Terminal.
2. **Install a model** — press *Install* next to one in the set-up
   window (or type `ollama pull qwen3.5:4b` in Terminal). It downloads
   once, then works without internet.
3. **Choose it** — *Use this* in the set-up window, or *AI ▸ Local AI
   model*.

**Which model?** Bigger models write better but are slower and need more
memory. The set-up window marks each one *fits this computer* or *needs
more memory*. The model shares the memory with Whisper and the rest of
the computer, so keep it under about 40 % of it (6–7 GB on a 16 GB Mac).
Installing two or three and comparing them on a real note is the best
way to choose.

| Model | Size | Made by | Good for |
|---|---|---|---|
| [qwen3.5:9b](https://ollama.com/library/qwen3.5) | 6.6 GB | Alibaba | **Best for notes on a 16 GB computer**: clearly better summaries and rewriting than the 4b; many languages; long documents. |
| [gemma4:e4b](https://ollama.com/library/gemma4) | 6.6 GB | Google | Google's newest small model: natural writing, many languages, reads images too. |
| [ministral-3:8b](https://ollama.com/library/ministral-3) | 6.0 GB | Mistral AI | From a French company: strong in French and other European languages. |
| [aya-expanse:8b](https://ollama.com/library/aya-expanse) | 5.1 GB | Cohere | Made for 23 languages — when talks are not in English. |
| [gemma4:e2b](https://ollama.com/library/gemma4) | 4.6 GB | Google | The lighter Gemma 4: quicker, still good. |
| [granite4:7b-a1b-h](https://ollama.com/library/granite4) | 4.2 GB | IBM | A bigger Granite that stays very fast; plain, factual style. |
| [qwen3.5:4b](https://ollama.com/library/qwen3.5) | 3.3 GB | Alibaba | The best small all-rounder; fine on 8 GB. |
| [ministral-3:3b](https://ollama.com/library/ministral-3) | 3.0 GB | Mistral AI | Small and quick, good French. |
| [phi4-mini](https://ollama.com/library/phi4-mini) | 2.5 GB | Microsoft | Small and quick; decent summaries. |
| [llama3.2:3b](https://ollama.com/library/llama3.2) | 2.0 GB | Meta | Quick, good English; weaker on long documents and other languages. |
| [granite4:micro-h](https://ollama.com/library/granite4) | 1.9 GB | IBM | The smallest: fast and light on long texts; plain style, mostly English. |

Too big for most laptops (they need 32 GB or more): gpt-oss:20b
(OpenAI, 14 GB), mistral-small3.2 (15 GB), qwen3.6 and qwen3.8 (18 GB
and up).

**Qwen or Granite?** Qwen 3.5 gives the most polished summaries and
rewrites and handles French, German and other languages best. Granite 4
stays quick on long documents thanks to its hybrid design; its writing
is plainer and more literal, and it is strongest in English. Both are
free to use.

Every model Ollama has is listed under *AI ▸ Local AI model* —
including custom ones made for other apps, such as the *xps-expert*
models built for KherveFitting, which are marked as such and are not
meant for notes.

**While the AI works** a bar appears above the page: what it is doing
("Read 2 of 3 parts"), how long it has taken, the words it is writing
as they come, and **Cancel**. A small local model can take a minute or
two over a long document — the bar shows it is working.

**Not happy with what the AI wrote? Press Undo** (Ctrl+Z, or the ↶
button): each AI change is one undo step.

## 7. Documents — PDF, Word, PowerPoint

Put the handouts, slides or papers of a talk into its note:

- **Drag the file onto the page** — from Finder, the desktop or an
  e-mail — and drop it where you want it; or
- press **Insert PDF** in the toolbar (Ctrl+Shift+A), or *Insert ▸ PDF,
  Word or PowerPoint document…*.

PDF, Word (`.docx`), PowerPoint (`.pptx`), text and Markdown files work.
The document appears **as an icon in the note**, where you dropped it,
and is kept inside the note file. While a note has no document, a
dashed "Drag a PDF…" line under the title is a reminder.

**Click a PDF's icon** to open it in **KhervePDF**, the KherveTools PDF
viewer — to read it, highlight, annotate and sign. If KhervePDF is
already open, the PDF arrives as a new tab there. KhervePDF works on the
note's own copy: annotations you **save in KhervePDF are kept in the
note** (save there before you switch to another note). Word, PowerPoint
and text documents open in their usual app the same way.

If KhervePDF is not found, KherveNote asks where it is (*File ▸ Where is
KhervePDF…*) or opens the computer's default viewer instead.

**Right-click the icon** for the **Document panel** (sections, find,
ask), *Summarise the document*, *Summarise every section*, *Find in
it…*, *Ask the AI about it…*, *Open with the computer's default app* and
*Remove from the note*.

In the Document panel:

- **Directions for the AI** — an optional box at the top. Whatever you
  write there is followed by every summary and answer below: “In
  French”, “At most five bullet points”, “Focus on the methods and the
  numbers”, “Explain it for a first-year student”… It is remembered
  until you change it.
- **Summarise the whole document** — the AI writes a summary section.
  Long documents are summarised part by part, so it takes a little time.
- **Summarise every section** — one summary per chapter of the
  document, each under its own heading, in a single new section of your
  note. The status bar shows which section it is on.
- **Sections** — the document's own chapters (a PDF's bookmarks, Word
  headings, one per slide, or one per page). Double-click a section, or
  *Insert into note*, to copy it into the note; *Summarise section* asks
  the AI for its key points instead.
- **Find** — type words or a sentence: every place it appears is listed
  with its page and the sentence around it. Double-click one to quote it
  in the note, with its page.
- **Ask the AI about this document** — type a question and press Enter.
  The AI reads the passages that best match the question and writes the
  answer as a **new section** of your note, with page references such as
  (p. 23). If the document does not say, it says so rather than guess.

Everything the AI writes goes after the section you are in, and one
**Undo** removes it. This uses the local AI (section 6) — nothing leaves
the computer.

## 8. Undo and redo

- **Undo**: Ctrl+Z, the ↶ button, or *Edit ▸ Undo*.
- **Redo**: Ctrl+Shift+Z (Ctrl+Y on Windows), the ↷ button, or
  *Edit ▸ Redo*.

Undo takes back your typing, style changes, what the AI wrote, and
what the microphone wrote — most recent first. The words shown live
while someone is still speaking are not part of the note yet, so they
never need undoing.

## 9. Pictures

- **Image** button: insert a picture file.
- **Paste** (Ctrl+V): paste a screenshot, e.g. of a slide.
- **Camera** button (Ctrl+Shift+P): take a picture of a whiteboard, a
  handout or a slide with the computer's camera; **Space** takes it.
  If the camera stays black, allow it in *System Settings ▸ Privacy &
  Security ▸ Camera*.

Text typed after a picture on the same line becomes its caption.

## 10. Saving and exporting

- Notes save themselves (see section 2); **Save** (Ctrl+S) saves at once.
  A `.knote` file holds the note, its pictures and its recordings.
- **Export PDF** (Ctrl+E) compiles the note with LaTeX:
  - *Export ▸ Continuous page* (default): the whole note on **one long
    page**, just like the screen, with a bookmark per section;
  - *Export ▸ A4 pages*: ordinary pages for printing.
  - *Export ▸ Show times in export* adds the time of each paragraph in
    the margin.
  - *Export ▸ Add what was said (transcript) at the end* adds the speech,
    with its times, as a last section.
- **Export LaTeX** writes the `.tex` file (and its pictures) to edit or
  compile elsewhere, e.g. in KherveTeX.

## 11. Appearance

*View ▸ Theme*: **System** (follows the computer), **Light** or **Dark**
(a black page).

## 12. All shortcuts

| Action | Shortcut |
|---|---|
| New / Open / Save | Ctrl+N / Ctrl+O / Ctrl+S |
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z |
| Listen on / off | Ctrl+L |
| New section | Ctrl+Return |
| Text / Section / Subsection / Sub-subsection | Ctrl+0 / 1 / 2 / 3 |
| Key point / Question | Ctrl+Shift+K / Ctrl+Shift+Q |
| Bold / Italic / Underline | Ctrl+B / I / U |
| Bullets / Numbering | Ctrl+Shift+8 / Ctrl+Shift+7 |
| Sub-item / back out | Tab / Shift+Tab (in a list) |
| Rephrase / Summarise with AI | Ctrl+Shift+R / Ctrl+Alt+S |
| Revise with directions | Ctrl+Shift+D |
| Take a picture | Ctrl+Shift+P |
| Insert a PDF / Word / PowerPoint document | Ctrl+Shift+A |
| Export PDF | Ctrl+E |
| This manual | F1 |
