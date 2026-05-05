# Lab 4.1: QA Evidence

## QA Agent Spec

**File**: `agents/quality-assurance.md`
**Relationship to implementation agent**: QA runs AFTER implementation agent opens a PR or completes a work item. QA is the gate between "implemented" and "done."

## Work Item: AI Content Access Views (Items #4 + #5)

### What Was Implemented

PostgreSQL views that make Canvas course content accessible to AI agents with FERPA filtering and HTML→markdown conversion.

### Tests Added

**File**: `tools/ai-content-access/test_ai_views.sql`
**Test command**: `psql -d canvas_ai_test -f tools/ai-content-access/test_ai_views.sql`
**Pattern**: AAA (Arrange-Act-Assert) per course reading on unit testing

| # | Test Name | Type | Outcome |
|---|-----------|------|---------|
| 1 | FERPA — unpublished content hidden | Security/compliance | **PASS** |
| 2 | Published assignments visible | Happy path | **PASS** |
| 3 | HTML stripped from assignments | Data quality | **PASS** |
| 4 | Syllabus accessible and cleaned | Happy path + cleaning | **PASS** |
| 5 | Module structure preserved | Structural integrity | **PASS** |
| 6 | Module prerequisites preserved | Relationship integrity | **PASS** |
| 7 | Announcements visible and cleaned | Happy path + cleaning | **PASS** |
| 8 | Unified content search works | Cross-type search | **PASS** |
| 9 | Course manifest counts correct | Aggregation accuracy | **PASS** |
| 10 | Pages accessible via wiki join | Join correctness | **PASS** |
| 11 | Due-this-week filter works | Date filtering | **PASS** |
| 12 | Files view works | Happy path | **PASS** |

**Result**: 12/12 PASS

### Test Coverage Analysis

| Category | Tests | Coverage |
|----------|-------|---------|
| FERPA/security | 1 (unpublished hidden) | Verified — unpublished assignment with id=99999 correctly invisible |
| Happy path | 5 (assignments, syllabus, modules, announcements, files) | All content types verified visible |
| Data quality | 2 (HTML stripping on assignments + announcements) | Verified no HTML tags in cleaned output |
| Structural | 2 (module structure + prerequisites) | Verified ordering and prerequisite chains |
| Search/aggregation | 2 (unified search + manifest counts) | Verified cross-type search and count accuracy |

### Boundary Cases Tested

- **Unpublished content** (FERPA boundary): assignment with `workflow_state='unpublished'` correctly hidden
- **Date filtering**: `due_at BETWEEN NOW() AND NOW() + interval '7 days'` returns correct assignments
- **Empty results**: unified search with non-matching term returns 0 rows (no error)
- **Multi-table join**: wiki_pages → wikis → courses join resolves correctly

### What Was NOT Tested (With Rationale)

| Item | Why No Automated Test |
|------|----------------------|
| `agents/feature-implementation.md` | Documentation only — agent spec markdown, no runtime behavior |
| `agents/quality-assurance.md` | Documentation only — agent spec markdown |
| `agents/tasks/feature-1/content-access-design.md` | Design document — no runtime behavior |
| `agents/canvas-content-context.md` | Reference documentation — no runtime behavior |

### Links

- **PR**: [#20](https://github.com/Dawson2025/canvas-lms/pull/20) (merged)
- **Board items**: #4 (Agent reads filesystem) → Done, #5 (Sync Canvas content) → Done
- **Test file**: `tools/ai-content-access/test_ai_views.sql`
- **Views file**: `tools/ai-content-access/create_ai_views.sql`
