#!/usr/bin/env bash
#
# Canvas AI Content Access — Live Demo Runner
# ============================================
# Brownfield feature: PostgreSQL views that expose Canvas course content to AI
# agents as clean, FERPA-safe markdown (no Rails app required).
#
# Usage:
#   ./demo.sh            # build demo DB from scratch + run narrated walkthrough
#   ./demo.sh --no-build # just run the walkthrough against an existing demo DB
#
# Requires: a local PostgreSQL reachable via `psql -d postgres` (peer/socket auth).
#
set -euo pipefail

DB="${DEMO_DB:-cse290r_ai_demo}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PSQL=(psql -d "$DB" -v ON_ERROR_STOP=1)

c_title() { printf '\n\033[1;36m%s\033[0m\n' "$1"; }
c_step()  { printf '\n\033[1;33m▶ %s\033[0m\n' "$1"; }
c_note()  { printf '\033[0;90m  %s\033[0m\n' "$1"; }
pause()   { [ -n "${DEMO_AUTO:-}" ] || { printf '\033[0;90m  (enter to continue)\033[0m'; read -r _; }; }

if [ "${1:-}" != "--no-build" ]; then
  c_title "BUILD — standing up the demo database ($DB)"
  c_note "Schema mirrors the real Canvas tables (courses, assignments, wiki_pages, modules, ...)."
  psql -d postgres -q -c "DROP DATABASE IF EXISTS $DB;"
  psql -d postgres -q -c "CREATE DATABASE $DB;"
  "${PSQL[@]}" -q -f "$DIR/setup_test_schema.sql"
  "${PSQL[@]}" -q -f "$DIR/seed_test_data.sql"
  [ -f "$DIR/seed_ai_society.sql" ] && "${PSQL[@]}" -q -f "$DIR/seed_ai_society.sql"
  "${PSQL[@]}" -q -f "$DIR/create_ai_views.sql"
  c_note "Loaded: Canvas schema + seed data (CSE 290R 407700 + AI Society 415990) + 8 AI views + strip_html_tags()."
fi

c_title "=================================================================="
c_title " Canvas AI Content Access — what an AI agent sees through the views"
c_title "=================================================================="
c_note "Problem: Canvas stores course content as messy HTML across many tables."
c_note "An AI agent that wants to read the course has to join tables and parse HTML."
c_note "These views do that once, in the database, FERPA-safely."
pause

c_step "1. The course manifest — one compact row an agent loads into its system prompt"
"${PSQL[@]}" -x -c "SELECT * FROM ai_course_manifest;"
pause

c_step "2. Before / After — raw Canvas HTML vs. agent-ready markdown (Lab 3.2)"
c_note "RAW (what's stored in assignments.description):"
"${PSQL[@]}" -t -A -c "SELECT left(description, 320) || '...' FROM assignments WHERE id = 16835669;"
c_note ""
c_note "CLEANED (what ai_course_assignments.description_clean returns):"
"${PSQL[@]}" -t -c "SELECT description_clean FROM ai_course_assignments WHERE id = 16835669;"
pause

c_step "3. FERPA safety — an UNPUBLISHED 'SECRET DRAFT EXAM' exists in the table"
c_note "Raw table row (should exist):"
"${PSQL[@]}" -c "SELECT id, title, workflow_state FROM assignments WHERE id = 99999;"
c_note "Through the AI view (should be EMPTY — unpublished content is filtered out):"
"${PSQL[@]}" -c "SELECT id, title FROM ai_course_assignments WHERE id = 99999;"
pause

c_step "4. Unified search — every content type in one view"
"${PSQL[@]}" -c "SELECT content_type, left(title, 42) AS title, left(coalesce(content_clean,''), 38) AS preview FROM ai_course_content ORDER BY content_type, content_id;"
pause

c_step "5. Module structure with items resolved (no agent-side joins needed)"
"${PSQL[@]}" -c "SELECT module_name, item_position AS pos, content_type, left(coalesce(item_title,''),40) AS item FROM ai_course_modules WHERE module_name LIKE 'Brownfield - Week 3' ORDER BY item_position;"
pause

c_step "6. Tests — proving it works (AAA pattern)"
c_note "Core view tests:"
"${PSQL[@]}" -t -f "$DIR/test_ai_views.sql" 2>&1 | grep -E "(PASS|FAIL):" | sed 's/^ */  /'
c_note "Edge-case tests (NULLs, empty data, deleted states, entity decode, large HTML):"
"${PSQL[@]}" -t -f "$DIR/test_edge_cases.sql" 2>&1 | grep -E "(PASS|FAIL):" | sed 's/^ */  /'

ALL_OUT=$( { "${PSQL[@]}" -t -f "$DIR/test_ai_views.sql"; "${PSQL[@]}" -t -f "$DIR/test_edge_cases.sql"; } 2>&1 )
PASS_CT=$(printf '%s\n' "$ALL_OUT" | grep -c "PASS:" || true)
FAIL_CT=$(printf '%s\n' "$ALL_OUT" | grep -c "FAIL:" || true)
c_title "RESULT: $PASS_CT passed, $FAIL_CT failed"

c_note ""
c_note "Takeaway: 8 views + 1 SQL function turn Canvas's HTML-in-many-tables into"
c_note "clean, FERPA-safe, agent-ready content — deployable as a Rails migration on the fork."
