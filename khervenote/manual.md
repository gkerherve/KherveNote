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
- To the left of each paragraph, in grey: the **time** in the session
  when it was written (or said). The clock starts when the note is
  created; *Note ▸ Restart session clock* starts it again when the talk
  really begins.
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
A new note gets its file as soon as something is written in it, named
after its title (or "Note <date>" until it has one).

All notes are ordinary `.knote` files in **Documents ▸ KherveNote**, the
folders are ordinary folders: you can back them up or sync them like
any files. *File ▸ Notes folder…* chooses another place.

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

## 5. Listening — the microphone

Press **Listen** in the toolbar (or **Ctrl+L**).

- A grey **● listening…** mark appears where the words will be written.
- While the person speaks, their words appear **live**, in grey
  italics. When they pause, the words settle into the final transcript
  (grey, upright) — a second or so later.
- **To stop**, press **Listen** again — or simply **press Space or
  Return** in the page: as on a phone, starting to type yourself ends
  the dictation. If you would rather keep listening while you type your
  own notes, untick *Speech ▸ Stop listening when I press Space or
  Return*; the speech then goes in just above the line you are typing.
- You can switch it on and off as often as you like.

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

Choose the model under *AI ▸ Local AI model*; a general model such as
qwen3.5 is picked by default. Ollama must be running with at least one
model installed, e.g. `ollama pull qwen3.5:4b`. Every model Ollama has is
listed — including custom ones made for other apps, such as the
*xps-expert* models built for KherveFitting, which are marked as such
and are not meant for notes.

**Not happy with what the AI wrote? Press Undo** (Ctrl+Z, or the ↶
button): each AI change is one undo step.

## 7. Undo and redo

- **Undo**: Ctrl+Z, the ↶ button, or *Edit ▸ Undo*.
- **Redo**: Ctrl+Shift+Z (Ctrl+Y on Windows), the ↷ button, or
  *Edit ▸ Redo*.

Undo takes back your typing, style changes, what the AI wrote, and
what the microphone wrote — most recent first. The words shown live
while someone is still speaking are not part of the note yet, so they
never need undoing.

## 8. Pictures

- **Image** button: insert a picture file.
- **Paste** (Ctrl+V): paste a screenshot, e.g. of a slide.
- **Camera** button (Ctrl+Shift+P): take a picture of a whiteboard, a
  handout or a slide with the computer's camera; **Space** takes it.
  If the camera stays black, allow it in *System Settings ▸ Privacy &
  Security ▸ Camera*.

Text typed after a picture on the same line becomes its caption.

## 9. Saving and exporting

- Notes save themselves (see section 2); **Save** (Ctrl+S) saves at once.
  A `.knote` file holds the note, its pictures and its recordings.
- **Export PDF** (Ctrl+E) compiles the note with LaTeX:
  - *Export ▸ Continuous page* (default): the whole note on **one long
    page**, just like the screen, with a bookmark per section;
  - *Export ▸ A4 pages*: ordinary pages for printing.
  - *Export ▸ Show times in export* adds the time of each paragraph in
    the margin.
- **Export LaTeX** writes the `.tex` file (and its pictures) to edit or
  compile elsewhere, e.g. in KherveTeX.

## 10. Appearance

*View ▸ Theme*: **System** (follows the computer), **Light** or **Dark**
(a black page).

## 11. All shortcuts

| Action | Shortcut |
|---|---|
| New / Open / Save | Ctrl+N / Ctrl+O / Ctrl+S |
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z |
| Listen on / off | Ctrl+L (Space or Return also stop it) |
| New section | Ctrl+Return |
| Text / Section / Subsection / Sub-subsection | Ctrl+0 / 1 / 2 / 3 |
| Key point / Question | Ctrl+Shift+K / Ctrl+Shift+Q |
| Bold / Italic / Underline | Ctrl+B / I / U |
| Bullets / Numbering | Ctrl+Shift+8 / Ctrl+Shift+7 |
| Sub-item / back out | Tab / Shift+Tab (in a list) |
| Rephrase / Summarise with AI | Ctrl+Shift+R / Ctrl+Alt+S |
| Take a picture | Ctrl+Shift+P |
| Export PDF | Ctrl+E |
| This manual | F1 |
