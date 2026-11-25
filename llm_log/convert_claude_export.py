#!/usr/bin/env python3
"""convert_claude_export.py - turn a claude.ai data export into readable transcripts for llm_log/transcripts/.

The course requires the COMPLETE prompts and responses of every AI interaction (not summaries).
claude.ai (Settings > Privacy > Export data) sends a .zip containing conversations.json.
This script writes one Markdown file per conversation: every message, in order, with its time,
who wrote it (user / Claude) and its full text, untouched.

Usage:
  python3 llm_log/convert_claude_export.py <conversations.json or the export .zip> [--match WORD ...] [--out llm_log/transcripts]
  --match  keep only conversations whose title contains one of these words (case ignored),
           e.g. --match heat mpi parallel ; without --match, every conversation is listed and nothing is written.
"""
import argparse, json, os, re, sys, zipfile

ap = argparse.ArgumentParser()
ap.add_argument("export")
ap.add_argument("--match", nargs="*", default=None)
ap.add_argument("--out", default="llm_log/transcripts")
ap.add_argument("--member", default="", help="team member name written in the header, e.g. 'Laetitia Daou'")
a = ap.parse_args()

if a.export.endswith(".zip"):
    with zipfile.ZipFile(a.export) as z:
        name = next(n for n in z.namelist() if n.endswith("conversations.json"))
        convs = json.loads(z.read(name))
else:
    convs = json.load(open(a.export, encoding="utf-8"))

def text_of(msg):
    """Full text of one message: the 'text' field, or every text/tool part of 'content'."""
    parts = []
    for c in msg.get("content") or []:
        t = c.get("type")
        if t == "text" and c.get("text"):
            parts.append(c["text"])
        elif t == "tool_use":
            parts.append(f"[tool call: {c.get('name')}]\n```json\n{json.dumps(c.get('input'), ensure_ascii=False, indent=1)}\n```")
        elif t == "tool_result":
            inner = c.get("content")
            if isinstance(inner, list):
                inner = "\n".join(x.get("text", "") for x in inner if isinstance(x, dict))
            parts.append(f"[tool result]\n```\n{inner}\n```")
    if not parts and msg.get("text"):
        parts.append(msg["text"])
    for f in (msg.get("attachments") or []) + (msg.get("files") or []):
        parts.append(f"[attached file: {f.get('file_name') or f.get('name')}]")
    return "\n\n".join(parts)

if a.match is None:
    for c in convs:
        print(f"{c.get('created_at', '')[:16]}  {len(c.get('chat_messages') or [])} messages  {c.get('name')!r}")
    print("\nnothing written: run again with --match <words from the titles you want>")
    sys.exit(0)

os.makedirs(a.out, exist_ok=True)
words = [w.lower() for w in a.match]
n = 0
for c in convs:
    title = c.get("name") or "untitled"
    if not any(w in title.lower() for w in words):
        continue
    msgs = c.get("chat_messages") or []
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "conversation"
    path = os.path.join(a.out, f"{(c.get('created_at') or '')[:10]}_{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"- Tool / model: Claude (claude.ai app), model as shown in the conversation\n")
        if a.member:
            f.write(f"- Team member: {a.member}\n")
        f.write(f"- Conversation id: {c.get('uuid')}\n- Started: {c.get('created_at')}\n- Last update: {c.get('updated_at')}\n")
        f.write(f"- Messages: {len(msgs)}\n- Source: claude.ai data export, converted by llm_log/convert_claude_export.py (text unchanged)\n\n---\n\n")
        for m in msgs:
            who = "User" if m.get("sender") == "human" else "Claude"
            f.write(f"## {who} — {m.get('created_at', '')}\n\n{text_of(m)}\n\n---\n\n")
    n += 1
    print(f"wrote {path}  ({len(msgs)} messages)")
print(f"{n} conversation(s) written to {a.out}")
