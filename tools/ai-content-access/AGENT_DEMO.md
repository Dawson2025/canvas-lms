# Course AI Platform — Class Agent Demo

A working **class agent**: a student asks a question, the agent answers using
**only** the FERPA-safe `ai_course_*` views (PR #20) as its knowledge source.
This is the "interface layer" from `feature-1.md` made real — the views feed the
agent; the agent answers.

The agent is **conversational and LLM-backed**: it loads the course content from
the views as grounding context and answers via the `claude` CLI in print mode
(`claude -p`, the subprocess pattern from `feature-1.md`). It can summarize the
course, chat generally, and answer specifics — but only from published content,
so it won't invent policies or reveal unpublished material. If the LLM is
unavailable (offline / not authed) it falls back to a deterministic keyword
router over the same views, so the demo never dies.

Tunables: `AGENT_MODEL` (default `haiku`), `AGENT_TIMEOUT` (default `45`s).

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

## Correlating the agent to real Canvas (side-by-side demo)

Open two headed windows: the agent (`localhost:8742`) and the real Canvas
course (`byui.instructure.com/courses/407700`). Ask the agent, then show the
same content live in Canvas — proving the agent reads the real course.

| Ask the agent | Show in Canvas | What it proves |
|---------------|----------------|----------------|
| "What's the late policy?" | Syllabus → *Late Policy* section | Same text, pulled from `ai_course_syllabus` |
| "What's the grading weight?" | Syllabus → *Grading* table | Agent extracts the same weights |
| "Show me the modules" | Modules page (Brownfield Weeks 1-4) | Agent lists the same 4 modules, in order |
| "Any recent announcements?" | Announcements (e.g. *Presentations Today*) | Agent surfaces the same announcements |
| "Is there a secret draft exam?" | (nothing to show — it's unpublished) | FERPA: the agent can't see what Canvas hides from students |

The last row is the key point: the agent only ever sees **published/active**
content, because the views enforce that filter in the database — exactly what a
student-facing assistant must do.
