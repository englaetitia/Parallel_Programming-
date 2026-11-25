# llm_log/transcripts — complete AI conversations

The course (project sheet, Section 12) requires the **complete prompts and responses** of every interaction
with an AI tool, not summaries. `llm_log/LOG.md` is the running index (date, team member, tool/model,
verbatim prompt, summary of the response, files changed); **this folder holds the full text**.

| File | Team member | Tool / model | Period | Content |
| --- | --- | --- | --- | --- |
| *(one line per exported conversation, filled when the exports are added)* | | | | |

## How the files were made

1. claude.ai → **Settings → Privacy → Export data** (web app or Claude Desktop; not available on the phone apps).
   The download link arrives by email; the .zip contains `conversations.json`.
2. From the repository root:
   ```bash
   python3 llm_log/convert_claude_export.py ~/Downloads/<export>.zip            # lists every conversation
   python3 llm_log/convert_claude_export.py ~/Downloads/<export>.zip --match heat parallel mpi --member "Laetitia Daou"
   ```
   One Markdown file per conversation: every message in order, with its time, who wrote it and its full text,
   unchanged (tool calls and their results included).
3. Each team member does this for their own account (Georges-Anthony too, for any AI use, e.g. while
   writing the Tasks).
4. Commit the files; never edit them afterwards (`AGENTS.md` / `CLAUDE.md`: existing log entries are never changed).

The raw export .zip itself is **not** committed: it contains the whole account history, including
conversations unrelated to the course.
