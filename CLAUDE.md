# CLAUDE.md -- logging rules (required by the course)

This repository is a graded course project. The course requires that EVERY interaction
with an AI assistant or LLM is recorded, complete, in `llm_log/`.

For every interaction in this repository:

1. Append an entry to `llm_log/LOG.md` containing: date and time, team member,
   tool and model, the user's prompt (verbatim), your full response, and every
   file you created or modified (with line ranges).
2. Never edit or delete existing entries in `llm_log/`.
3. Commit the log update together with any code changes.

If you can save or export the full session transcript, also put the raw transcript in
`llm_log/transcripts/` named `YYYY-MM-DD_<member>_<tool>.md`.

Project context: C++17 + MPI solver for the 2D heat equation (serial, strips, blocks).
Every parallel output must be bit-for-bit identical to the serial output. The team must
be able to explain every line, so explain what you write and why.
