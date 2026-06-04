# Canvas AI Content Access — Demo Guide

**Feature (PR #20):** PostgreSQL views that expose Canvas course content to AI
agents as clean, FERPA-safe markdown — no Rails app required.

## Run it

```bash
cd tools/ai-content-access
./demo.sh              # builds a fresh demo DB, then runs the narrated walkthrough
./demo.sh --no-build   # re-run walkthrough against the existing demo DB
DEMO_AUTO=1 ./demo.sh  # no pauses (for a recording / dry run)
```

Requires a local PostgreSQL reachable via `psql -d postgres`. The script creates a
throwaway database `cse290r_ai_demo` (override with `DEMO_DB=...`).

## What it shows (6 beats, ~3 min)

1. **The problem** — Canvas stores content as HTML scattered across many tables
   (`assignments`, `wiki_pages`, `discussion_topics`, `context_modules`, ...).
   An agent that wants to "read the course" has to join tables and parse HTML.
2. **Manifest** — `ai_course_manifest` returns one compact row (counts of modules,
   assignments, pages, announcements, files) an agent drops into its system prompt.
3. **Before / After** — raw `assignments.description` HTML vs.
   `ai_course_assignments.description_clean` markdown produced by `strip_html_tags()`.
4. **FERPA** — an unpublished `SECRET DRAFT EXAM` row exists in the table but is
   **invisible** through the view (views filter to published/active only).
5. **Unified search** — `ai_course_content` UNIONs assignments + pages +
   announcements into one queryable surface.
6. **Tests** — 26 AAA-pattern tests (12 core + 14 edge cases) run live, all green.

## Talking points

- 8 views + 1 SQL function (`strip_html_tags`); ~516 lines of SQL total.
- Deploys on the fork as a **Rails migration** — views are additive, read-only,
  zero risk to existing Canvas behavior (brownfield-safe).
- FERPA safety is enforced **in the database**, not in agent code — the agent
  literally cannot see unpublished/deleted content through these views.
- Edge cases covered: NULL/empty bodies, deleted states, HTML entity decode,
  large HTML (32% of original after cleaning), idempotent re-runs, empty courses.

## Files

| File | Purpose |
|------|---------|
| `setup_test_schema.sql` | Minimal Canvas schema (the tables the views read) |
| `seed_test_data.sql` | Seed data from the real CSE 290R course (407700) |
| `create_ai_views.sql` | `strip_html_tags()` + 8 `ai_course_*` views |
| `test_ai_views.sql` | 12 core AAA tests |
| `test_edge_cases.sql` | 14 edge-case tests |
| `demo.sh` | One-command narrated demo runner |
