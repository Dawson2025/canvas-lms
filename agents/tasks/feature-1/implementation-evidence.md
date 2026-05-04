# Lab 3.2: Implementation Evidence

## Work Items Completed

### Item #5: Sync Canvas course content to local content directory
- **Board status**: Todo → In Progress → Done
- **PR**: [#20](https://github.com/Dawson2025/canvas-lms/pull/20) — merged via squash
- **Merge evidence**: PR merged to master, branch deleted

### Item #4: Agent reads course content from local filesystem directory
- **Board status**: Todo → In Progress → Done
- **Covered by same PR** — the AI views provide the content access layer that agents query

## PR Details

**PR #20**: feat: AI content access views with HTML-to-markdown and FERPA filtering

### What Changed

| File | Purpose |
|------|---------|
| `tools/ai-content-access/create_ai_views.sql` | 8 PostgreSQL views + `strip_html_tags()` function for AI agent access to course content |
| `tools/ai-content-access/setup_test_schema.sql` | Minimal Canvas schema reproduction (8 tables matching Canvas models) |
| `tools/ai-content-access/seed_test_data.sql` | Test data based on real CSE 290R course (407700) including FERPA test case |
| `tools/ai-content-access/test_ai_views.sql` | 12 AAA-pattern tests — all passing |

### Views Created

| View | Purpose | FERPA-Safe |
|------|---------|-----------|
| `ai_course_assignments` | Published assignments with cleaned descriptions | Yes — `workflow_state = 'published'` |
| `ai_course_pages` | Wiki pages with cleaned body text | Yes — `workflow_state = 'active'` |
| `ai_course_modules` | Module structure with content_tag items resolved | Yes — both module and tag filtered |
| `ai_course_announcements` | Announcements with cleaned messages | Yes — `workflow_state = 'active'` |
| `ai_course_syllabus` | Course syllabus cleaned | Yes — `workflow_state = 'available'` |
| `ai_course_files` | Available file attachments | Yes — `file_state = 'available'` |
| `ai_course_content` | Unified search across all content types | Yes — union of filtered views |
| `ai_course_manifest` | Compact course index for agent system prompts | Yes — counts from filtered views |

### Test Results (12/12 PASS)

| # | Test | Result |
|---|------|--------|
| 1 | FERPA — unpublished content hidden | PASS |
| 2 | Published assignments visible | PASS |
| 3 | HTML stripped from assignments | PASS |
| 4 | Syllabus accessible and cleaned | PASS |
| 5 | Module structure preserved | PASS |
| 6 | Module prerequisites preserved | PASS |
| 7 | Announcements visible and cleaned | PASS |
| 8 | Unified content search works | PASS |
| 9 | Course manifest counts correct | PASS |
| 10 | Pages accessible via wiki join | PASS |
| 11 | Due-this-week filter works | PASS |
| 12 | Files view works | PASS |

## Plan Trace

This implementation maps directly to the feature plan:

- **Feature brief** (`feature-1.md`): "Automatically ingests course content from Canvas" — the views provide AI-ready access to all course content
- **Implementation research** (`implementation-research.md`): FR-2 (deadline queries), FR-3 (policy lookup) — both are single-query operations against the views
- **Content access design** (`content-access-design.md`): 14-part design document evaluated 7 approaches. Chose server-side PostgreSQL views based on:
  - Microsoft Research: 91-tool MCP = 55K tokens, 85% degradation
  - Arize: decouple agent interface from storage backend
  - MindStudio: leading AI agents use grep, not vectors
  - Course content is inherently structured — views preserve that structure

The design doc also covers extension model (API-based CLI), progressive disclosure with trigger hierarchies, cross-avenue flow, and a 5-level progressive complexity roadmap — all designed but deferred to future labs.
