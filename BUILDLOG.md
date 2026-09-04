# Build log

Where AI helped on this capstone, where it was wrong, and what I changed. Kept honest and appended
as the stages land, not written at the end.

## Stage 0 — repo skeleton and submission pack

**What AI did.** Drafted the submission pack: `.gitignore`, `.env.example`, `capstone.yaml`, the
`EVIDENCE.md` checklist skeleton (transcribed from Section 6 of the brief), and this file.

**What I decided, not the AI.**

- Python + FastAPI + Postgres, matching the stack from the rest of the track, so the layering
  conventions carry over instead of being invented again.
- The repo is separate and public from the first commit, per Section 11 — not a folder inside the
  internship monorepo.
- `.env` went into `.gitignore` *before* the first commit, so no secret has ever been in the history.

**What I want to watch.** AI is good at generating plausible CORS middleware; it is also good at
generating CORS middleware that quietly allows everything. When Stage 5 lands I intend to read that
code line by line rather than trust it, because "it works in the browser" and "it is correct" are
not the same sentence here.
