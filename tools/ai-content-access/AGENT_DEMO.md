# Course AI Platform — Class Agent Demo

A working **class agent**: a student asks a question, the agent answers using
**only** the FERPA-safe `ai_course_*` views (PR #20) as its knowledge source.
This is the "interface layer" from `feature-1.md` made real — the views feed the
agent; the agent answers.

## Prerequisites

```bash
# 1. Build the demo database (once)
./demo.sh            # creates cse290r_ai_demo with schema + seed + views
```

## Run the agent (web chat)

```bash
python3 class_agent_server.py            # http://localhost:8742
# or: DEMO_DB=cse290r_ai_demo PORT=8742 python3 class_agent_server.py
```

Open `http://localhost:8742` in a browser. Pure Python stdlib + `psql` — no pip
installs.

## What to ask in the demo

| Question | Shows |
|----------|-------|
| *What's due?* | Deadline awareness — queries `ai_course_assignments` by date |
| *What's the late policy?* | Policy lookup — extracts the sentence from `ai_course_syllabus` |
| *Show me the modules* | Course structure from `ai_course_modules` |
| *Where's the Quality Assurance lab?* | Content search across `ai_course_content` |
| *Is there a secret draft exam?* | **FERPA punchline** — the agent literally can't see unpublished content |

Every answer cites its **source view**, so you can show the grounding live.

## Backup: static report (no server)

`demo_report.html` is a self-contained snapshot (manifest, raw→clean, FERPA,
unified search, 26 live tests) — open it directly if you can't run the server.
Regenerate with `python3 generate_report.py`.

## How it works

```
student question
   │
   ▼  trigger hierarchy (feature-1.md)
   ├─ "due / deadline"      → ai_course_assignments
   ├─ "late / policy / grade"→ ai_course_syllabus
   ├─ "module / structure"  → ai_course_modules
   ├─ "announcement"        → ai_course_announcements
   └─ "where / find <x>"    → ai_course_content  (FERPA: published only)
   │
   ▼
grounded answer + source view
```

The agent never reads raw Canvas tables — only the views, which enforce the
FERPA boundary in the database. Swap the templated answer step for an LLM call
and the same retrieval layer powers a fully conversational agent.
