# KherveNote — the MCP tool table
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""What an assistant may call over MCP, and how.  Qt-free.

A tool's ``description`` is prompt text sent to the model verbatim: say
what it does and when to prefer it over its neighbours.  A new tool = a
``TOOLS`` entry + a ``_t_<name>`` method in ``mcp_tools.py`` (+ a line in
``mcp_server._INSTRUCTIONS``); ``tests/test_mcp.py`` enforces the pairing.
"""
from __future__ import annotations

_SECTION = {"type": "integer", "minimum": 0,
            "description": "Section index, as get_note numbers them (0 = first)."}
_BODY = {"type": "string",
         "description": ("Light Markdown: paragraphs between blank lines, '- ' / '1. ' "
                         "items (indent two spaces to nest), '## ' subheadings, **bold**, "
                         "maths as $…$ or $$…$$ in LaTeX.")}
_LAYOUT = {"type": "string", "enum": ["continuous", "paged"],
           "description": "continuous = one page as long as the note (default: the "
                          "note's own choice); paged = A4 pages."}
_KIND = {"type": "string", "enum": ["text", "important", "question", "transcript"],
         "description": "text, important (key-point box), question, or transcript "
                        "(quoted speech)."}


def _tool(name, description, props=None, required=None):
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": props or {},
                             "required": required or []}}


TOOLS = [
    _tool("get_note",
          "The open note: title, speaker, date, place, summary, its file, whether it "
          "has unsaved changes, and every SECTION (index, title, the time it was "
          "started) with its paragraphs (index, kind, list level, the time written, "
          "text), plus how many lines of speech there are. Call this FIRST."),
    _tool("get_transcript",
          "What was said (the offline speech transcript), line by line with the time "
          "of day. With section, only the speech that goes with that section: from "
          "the lead time (2 min by default) before its heading was written up to the "
          "same before the next section.",
          {"section": _SECTION,
           "max_lines": {"type": "integer", "minimum": 1, "default": 2000}}),
    _tool("list_notes",
          "Every note in the user's library (folders of .knote files under "
          "Documents/KherveNote): path, title, speaker, date, folder."),
    _tool("open_note",
          "Open a note from the library in the window (the current one is saved "
          "first, as when the user clicks another note).",
          {"path": {"type": "string",
                    "description": "Path of a .knote file, as list_notes gives it."}},
          ["path"]),
    _tool("new_note",
          "Start a new, empty note in the library (the current one is saved first).",
          {"title": {"type": "string"}}),
    _tool("set_header",
          "Set the top of the note: title, speaker, date, place and the summary box "
          "(plain text). Only the fields given change.",
          {"title": {"type": "string"}, "speaker": {"type": "string"},
           "date": {"type": "string"}, "place": {"type": "string"},
           "summary": {"type": "string"}}),
    _tool("add_section",
          "Append a new section (a heading and its body) at the end of the note — "
          "e.g. 'Notes from the speech' made from the transcript, or a summary. One "
          "undo step.",
          {"title": {"type": "string"}, "body": _BODY}, ["title"]),
    _tool("fill_section",
          "The app's 'Fill in my section': add what the speech covered and the "
          "notes of that section miss, at the end of the section under a "
          "subheading 'From the speech (<from>–<to>)'. Read the section (get_note) "
          "and its speech (get_transcript with section) first; never repeat what "
          "the notes already say. One undo step.",
          {"section": _SECTION, "body": _BODY,
           "title": {"type": "string",
                     "description": "Subheading; default 'From the speech (<times>)'."}},
          ["section", "body"]),
    _tool("append_to_section",
          "Add paragraphs to the end of a section, in the section itself (no "
          "subheading). One undo step.",
          {"section": _SECTION, "body": _BODY, "kind": _KIND}, ["section", "body"]),
    _tool("set_paragraph",
          "Rewrite one paragraph of a section (index from get_note), optionally "
          "changing its kind. The user's own words are theirs: only rewrite when "
          "asked. One undo step.",
          {"section": _SECTION,
           "paragraph": {"type": "integer", "minimum": 0},
           "text": {"type": "string"}, "kind": _KIND},
          ["section", "paragraph", "text"]),
    _tool("save_note",
          "Save the note now (it also saves itself a few seconds after a change). "
          "A new note gets its file in the library, named after its title."),
    _tool("export_latex",
          "Write the note as a standalone .tex file (and its assets/ folder of "
          "pictures beside it).",
          {"path": {"type": "string", "description": "Absolute .tex path."},
           "layout": _LAYOUT,
           "show_times": {"type": "boolean", "default": False,
                          "description": "Each paragraph's time in the margin."},
           "transcript": {"type": "boolean", "default": False,
                          "description": "Add the speech, with its times, as a last "
                                         "section."}},
          ["path"]),
    _tool("export_pdf",
          "Typeset the note to PDF with the built-in LaTeX engine (tectonic): "
          "'continuous' is one page as long as the note with a bookmark per section, "
          "'paged' is A4. Returns the page count and heights, or the LaTeX error.",
          {"path": {"type": "string", "description": "Absolute .pdf path."},
           "layout": _LAYOUT,
           "show_times": {"type": "boolean", "default": False},
           "transcript": {"type": "boolean", "default": False}},
          ["path"]),
]

#: Tools offered only at the Full access level (none run code here).
FULL_ACCESS_TOOLS = frozenset()

TOOL_NAMES = [t["name"] for t in TOOLS]
_BY_NAME = {t["name"]: t for t in TOOLS}

_TYPES = {"string": str, "integer": int, "number": (int, float),
          "boolean": bool, "array": list, "object": dict}


def check_args(name, args):
    """Validate *args* against the tool's schema; returns an error string
    or '' when they are fine."""
    tool = _BY_NAME.get(name)
    if tool is None:
        return f"Unknown tool {name!r}."
    if not isinstance(args, dict):
        return "Arguments must be an object."
    schema = tool["input_schema"]
    for req in schema.get("required", []):
        if req not in args or args[req] in (None, ""):
            return f"{name}: missing required argument {req!r}."
    props = schema.get("properties", {})
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            return f"{name}: unknown argument {key!r}."
        want = _TYPES.get(spec.get("type"))
        if want is not None and value is not None:
            if spec.get("type") in ("integer", "number") and isinstance(value, bool):
                return f"{name}: {key} must be a {spec['type']}."
            if not isinstance(value, want):
                return f"{name}: {key} must be a {spec['type']}."
        if "enum" in spec and value not in spec["enum"]:
            return f"{name}: {key} must be one of {spec['enum']}."
    return ""
