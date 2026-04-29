# Implementation Research: Canvas Course Agent

> **Feature brief**: See [`feature-1.md`](./feature-1.md) — an AI-powered course assistant embedded in Canvas courses via LTI, providing read-only Q&A over published course content with QR code mobile access.

---

## 1. Design Considerations

### User Flow

1. **Instructor enables agent**: Course Settings → Navigation → drag "Course Agent" to active items (standard Canvas external tool enable flow via `ContextExternalTool` placements).
2. **Student opens agent**: Clicks "Course Agent" in course sidebar → chat interface loads in the Canvas content area via LTI launch.
3. **Student asks question**: Types natural language query → agent retrieves relevant course content via Canvas API → returns answer with source links.
4. **QR code access**: Instructor generates a QR code from agent settings → students scan on phone → opens mobile-optimized chat (authenticated via Canvas session or LTI deep link).

### Data Boundaries

| Boundary | Data Crossing | Direction |
|----------|--------------|-----------|
| Canvas API → Agent backend | Course content (syllabus, assignments, modules, files, pages, announcements) | Read-only pull |
| Agent backend → LLM provider | Anonymized course content chunks as context | Outbound, no PII |
| LLM provider → Agent backend | Generated response text | Inbound |
| Agent backend → Canvas UI | Chat messages, source links | Rendered in iframe |
| Student browser → Agent | Chat input text | User-initiated |

The agent **never writes back to Canvas** — no grade changes, no submissions, no announcements. Read-only by design.

### UX Risks

- **Hallucination**: Agent could fabricate policies not in the syllabus. Mitigation: RAG-only mode (no generation beyond retrieved content), source citations on every answer, confidence indicator.
- **Stale content**: If instructor updates syllabus mid-semester, agent's indexed content may lag. Mitigation: re-index on each session start or on content change webhook (`content.updated` Canvas event).
- **Over-reliance**: Students may stop reading materials. Mitigation: agent links to source material rather than quoting it fully; instructor can see usage analytics.
- **Privacy expectations**: Students may share personal information in chat. Mitigation: clear disclaimer, no chat history stored beyond session, no PII sent to LLM.

### Canvas Concept Interactions

| Canvas Concept | Interaction |
|---------------|-------------|
| **Courses** | Agent is scoped per course; content index is course-specific |
| **Modules** | Agent reads module structure and item ordering for navigation help |
| **Assignments** | Agent reads descriptions, due dates, rubrics, submission types |
| **Users/Roles** | Agent checks enrollment via LTI launch context; instructor vs student permissions |
| **Files** | Agent can reference published course files (PDFs, docs) by name and link |
| **Pages** | Agent indexes wiki pages for content Q&A |
| **Announcements** | Agent surfaces recent announcements in response to "what's new" queries |

### Project Plan Tracking (for Lab 4 MCP)

The following should be tracked in GitHub Projects for Lab 4 automation:

| Tracking Item | Type |
|--------------|------|
| LTI registration and placement configuration | Milestone |
| Canvas API content ingestion pipeline | Milestone |
| RAG indexing and retrieval system | Milestone |
| Chat UI (React component in iframe) | Milestone |
| QR code generation and mobile view | Task |
| Instructor settings panel | Task |
| Usage analytics dashboard | Task |
| Definition of done: agent answers 5 canonical queries correctly using only course content | Acceptance |

---

## 2. Functional Requirements

### In Scope

| ID | Requirement | Verification |
|----|------------|--------------|
| FR-1 | **Given** a student enrolled in a course with Course Agent enabled, **when** they click "Course Agent" in the sidebar, **then** a chat interface loads within the Canvas content area within 3 seconds. | Load time measurement; UI renders with input field and welcome message. |
| FR-2 | **Given** a student asks "What is due this week?", **when** the agent processes the query, **then** it returns a list of assignments with due dates from the current week, each linked to the assignment page. | Compare agent output against Canvas calendar API for the same date range. |
| FR-3 | **Given** a student asks about the late submission policy, **when** the agent processes the query, **then** it returns the relevant excerpt from the course syllabus with a link to the full syllabus page. | Verify cited text exists in syllabus; verify link resolves. |
| FR-4 | **Given** an instructor, **when** they access Course Agent settings, **then** they can enable/disable the agent, set a custom welcome message, and choose which content types the agent indexes (syllabus, assignments, modules, files, pages). | Settings save and persist; toggling disable removes the nav item for students. |
| FR-5 | **Given** any user, **when** they ask a question the agent cannot answer from course content, **then** the agent responds with "I don't have information about that in this course's materials" rather than fabricating an answer. | Ask out-of-scope questions; verify no hallucinated content. |
| FR-6 | **Given** an instructor, **when** they click "Generate QR Code", **then** a QR code image is displayed that encodes a URL to the mobile-optimized agent chat for that course, requiring Canvas authentication. | Scan QR code on phone; verify it opens agent chat after Canvas login. |
| FR-7 | **Given** a student not enrolled in the course, **when** they attempt to access the agent via direct URL or QR code, **then** they receive a "Not authorized" message. | Test with unenrolled user; verify 403 response. |

### Out of Scope

- Agent does not submit assignments or modify grades on behalf of students.
- Agent does not provide tutoring or generate new educational content beyond what exists in course materials.
- Agent does not support cross-course queries (each agent instance is isolated to one course).
- Agent does not store conversation history beyond the current browser session.
- Agent does not integrate with third-party LMS platforms (Canvas-only).

---

## 3. Non-Functional Requirements

### NFR-1: Security and Privacy (FERPA)

- All course content accessed via agent must respect Canvas's existing permission model — unpublished content is never surfaced to students.
- Chat input is not stored server-side beyond the current session. No student queries are logged with PII.
- LLM API calls use anonymized content chunks — no student names, IDs, or email addresses are included in prompts.
- Agent backend authenticates via LTI 1.3 JWT tokens; no separate credential store.
- QR code URLs require Canvas session authentication — no anonymous access to course content.

### NFR-2: Performance

- Chat responses return within 5 seconds for typical queries (deadline lookups, policy questions).
- Content indexing for a course with 50 modules and 200 assignments completes within 60 seconds.
- Agent supports 50 concurrent users per course instance without degradation.
- Content re-indexing triggers incrementally (only changed content), not full re-index.

### NFR-3: Accessibility

- Chat interface meets WCAG 2.1 AA standards (Canvas's baseline accessibility requirement).
- All agent responses are plain text with semantic HTML links — no images or charts in responses.
- Chat supports keyboard navigation: Tab to input, Enter to send, arrow keys to scroll history.
- Screen reader announces new messages via ARIA live regions.
- Mobile view (QR code path) is responsive and touch-friendly.

### NFR-4: Observability

- Agent logs query count, response latency, and error rate per course (no query content logged).
- Instructor dashboard shows: total queries this week, most-asked topics, unanswered question count.
- Backend emits structured logs for debugging: LTI launch events, API fetch timing, LLM call duration.
- Health check endpoint at `/health` returns agent status and Canvas API connectivity.

---

## 4. Codebase Analysis (Using Lab 2 Agent)

### Agent Workflow

The analysis was performed using the repository analysis agent specified in `agents/analyze-repo.md`. The indexing scripts (`agents/scripts/index-repo.sh`) were run against the Canvas LMS fork to generate `.repo-index/` manifests, followed by targeted exploration of relevant subsystems.

#### Session Notes

```
$ bash agents/scripts/index-repo.sh .
Index complete: ./.repo-index/

Key findings from index:
- file_types.txt: 6,697 .rb files, 3,687 .tsx, 2,558 .js, 2,028 .jsx, 1,758 .ts
- directories.txt: app/controllers/, app/graphql/, app/models/, ui/features/
- Tech stack: Ruby on Rails monolith with React frontend, PostgreSQL
```

### Hypotheses (Pre-Exploration)

| # | Hypothesis | Rationale |
|---|-----------|-----------|
| H1 | LTI external tool placement is the integration path | Canvas already has a `COURSE_NAVIGATION` placement type for adding tools to course sidebar |
| H2 | Course content is accessible via REST API v1 | Canvas has well-documented public APIs at `/api/v1/courses/:id/*` |
| H3 | React feature isolation pattern should be followed | Canvas uses `ui/features/` with per-feature `package.json` and entry points |
| H4 | No existing AI/agent infrastructure exists in Canvas | Canvas is an LMS, not an AI platform — agent backend would be external |

### Concrete Findings

#### Finding 1: LTI Course Navigation Placement

- **File**: `app/models/lti/resource_placement.rb` (line ~38)
- **Pattern**: `COURSE_NAVIGATION` is a defined placement constant. External tools registered with this placement appear as sidebar items in courses.
- **File**: `app/controllers/tabs_controller.rb`
- **Pattern**: The tabs API returns external tools as navigation items with `id: "context_external_tool_<ID>"`. This is the standard mechanism for adding new navigation entries.
- **Implication**: The Course Agent should register as an LTI 1.3 tool with `course_navigation` placement. No core Canvas code changes needed for navigation integration.

#### Finding 2: Course Content API Surface

- **File**: `app/controllers/courses_controller.rb`
- **File**: `lib/api/v1/course.rb`
- **Pattern**: REST endpoints serve course data at `/api/v1/courses/:id` with includes for syllabus, modules, assignments, files, pages, announcements. All endpoints respect enrollment-based authorization.
- **Implication**: Agent backend can fetch all needed content via Canvas API using the LTI service token. No direct database access required.

#### Finding 3: React Frontend Architecture

- **Directory**: `ui/features/` — each feature is an isolated React app with its own `package.json`, `index.tsx`, and build configuration.
- **Example**: `ui/features/course_show_secondary/` — a course-level feature mounted in the content area.
- **Pattern**: Features declare an owner team tag in `package.json` and are built independently.
- **Implication**: If building a native Canvas feature (non-LTI), it would follow this pattern. For LTI approach, the React app lives in the external tool's domain and renders in an iframe.

#### Finding 4: External Tool Launch Flow

- **File**: `app/controllers/lti/message_controller.rb`
- **Route**: `/courses/:course_id/external_tools/:id` triggers LTI launch
- **Pattern**: Canvas sends an LTI 1.3 launch JWT with course context, user info, and role claims. The external tool validates the JWT and renders its UI.
- **Implication**: Agent backend receives course_id, user_id, and roles via LTI launch — sufficient context to fetch course content and enforce permissions.

#### Finding 5: Plugin Architecture (Alternative Path)

- **Directory**: `gems/plugins/` — Canvas supports Rails Engine plugins with `engine.rb`, models, controllers, routes.
- **Example**: `gems/plugins/academic_benchmark/` — plugin that adds functionality via the engine mounting pattern.
- **Implication**: A Canvas plugin could add the agent as a first-party feature rather than an LTI tool. This would give deeper integration (e.g., webhooks for content changes) but requires Canvas deployment access. **LTI is preferred for portability.**

### Open Questions

| # | Question | Why It Matters | Resolution Path |
|---|----------|---------------|-----------------|
| OQ-1 | Does Canvas support LTI 1.3 Advantage Services (Names and Role Provisioning, Assignment and Grade Services) in the fork? | Needed if agent should know user names for personalized responses | Check `app/models/lti/` for service implementations; test with LTI tool registration |
| OQ-2 | What is the Canvas content change notification mechanism? | Needed for incremental re-indexing when instructor updates materials | Investigate Canvas webhooks or live events (`app/models/live_events/`) |
| OQ-3 | How large is typical course content (token count after extraction)? | Determines whether RAG is needed vs. full-context prompting | Spike: export a real course's content via API and measure tokens |
| OQ-4 | Does the Canvas CSP policy allow iframe embedding of external domains? | LTI tools render in iframes — CSP must allow the agent domain | Check `config/initializers/` for CSP configuration |

---

## 5. Testing and Verification Plan

### Unit Tests

| Test Area | What to Test | Framework |
|-----------|-------------|-----------|
| Query classifier | Categorizes "What's due?" as deadline query, "late policy?" as policy query | pytest / Jest |
| Content retriever | Given a course content index, returns relevant chunks for a query | pytest with mock index |
| Response formatter | Formats agent response with source links in markdown | Jest |
| Permission checker | Verifies unpublished content is excluded from retrieval | pytest with mock Canvas API |
| QR code generator | Generates valid QR code encoding the correct course agent URL | pytest with QR decode verification |

### Integration Tests

| Test Area | Components | What to Verify |
|-----------|-----------|---------------|
| LTI launch | Canvas → Agent backend | JWT validation succeeds; course_id and user_role extracted correctly |
| Content fetch | Agent backend → Canvas API | All content types (syllabus, assignments, modules, files, pages) fetched and parsed |
| RAG pipeline | Content indexer → Vector store → Retriever | Query returns relevant chunks; irrelevant content excluded |
| End-to-end chat | UI → Backend → LLM → UI | Student question produces accurate answer with source citation |
| Auth enforcement | Unenrolled user → Agent | Returns 403; no content leaked |

### Manual / Exploratory Testing

| Scenario | What to Check | Roles |
|----------|--------------|-------|
| Enable agent in a course with 100+ items | Performance acceptable; all content indexed | Instructor |
| Ask questions about every content type | Agent handles syllabus, assignment, module, file, page, announcement queries | Student |
| Ask off-topic questions | Agent declines gracefully; no hallucination | Student |
| Disable agent mid-semester | Nav item disappears; existing sessions end cleanly | Instructor |
| Access via QR code on mobile | Chat loads after Canvas auth; responsive layout; usable on small screen | Student |
| Two students chatting simultaneously | No cross-contamination of sessions or responses | Student × 2 |
| Course with no syllabus | Agent handles missing content gracefully | Student |
| Instructor changes assignment after indexing | Agent reflects updated content on next query (or after re-index) | Instructor + Student |

### Acceptance Criteria (Mapped to Functional Requirements)

| FR | Acceptance Test | Pass Criteria |
|----|----------------|--------------|
| FR-1 | Open Course Agent in Chrome and Firefox | Chat UI loads in < 3s; input field focused; welcome message displayed |
| FR-2 | Ask "What is due this week?" in a course with 3 assignments due | All 3 assignments listed with correct dates and links |
| FR-3 | Ask "What is the late policy?" in a course with syllabus containing late policy section | Response quotes syllabus text; link to syllabus resolves |
| FR-4 | Toggle agent off as instructor; verify as student | Nav item gone; direct URL returns "Agent disabled for this course" |
| FR-5 | Ask "What is the meaning of life?" | Response: "I don't have information about that in this course's materials" |
| FR-6 | Generate and scan QR code | QR resolves to agent chat; requires Canvas login; mobile layout renders |
| FR-7 | Access agent URL while logged in as non-enrolled user | 403 "Not authorized" returned |

### Impractical to Automate

| Area | Why | Alternative |
|------|-----|-------------|
| LLM response quality | Non-deterministic; depends on model and prompt | Manual review checklist: accuracy, source citation, no hallucination. Run against 20 canonical queries quarterly. |
| Mobile UX on diverse devices | Too many device/browser combinations | Manual testing on iOS Safari + Android Chrome; responsive design review |
| FERPA compliance | Legal interpretation, not code behavior | Compliance checklist reviewed by instructor/admin before deployment |
