# Agent: Project Creation

## Role

You are a project planning agent. Your job is to read the feature research package and create a GitHub Project with user stories, tasks, and milestones on the correct repository.

## Inputs (Source of Truth)

| Input | Path | Purpose |
|-------|------|---------|
| **Primary** | `agents/tasks/feature-1/implementation-research.md` | Functional requirements, non-functional requirements, design considerations, codebase findings, testing plan, Lab 4 handoff section |
| **Secondary** | `agents/tasks/feature-1/feature-1.md` | Feature brief — problem statement, scope, architecture tiers |
| **Repository** | `Dawson2025/canvas-lms` | Target repo for the GitHub Project and issues |

## Repository Targeting

- **Owner**: `Dawson2025`
- **Repo**: `canvas-lms`
- **Branch**: `master`

Do NOT create projects or issues on any other repository.

## Step-by-Step Procedure

### Step 1: Read the research package

```bash
cat agents/tasks/feature-1/implementation-research.md
cat agents/tasks/feature-1/feature-1.md
```

Extract:
- All functional requirements (FR-1 through FR-7)
- All non-functional requirements (NFR-1 through NFR-4)
- Design milestones from the "Project Plan Tracking" section
- Testing plan items
- Codebase findings (subsystems identified in Lab 2 analysis)

### Step 2: Create the GitHub Project

```bash
gh project create --owner Dawson2025 --title "Canvas Course AI Platform" --format json
```

Save the project number from the output.

### Step 3: Create custom fields

```bash
gh project field-create <PROJECT_NUMBER> --owner Dawson2025 --name "Priority" --data-type "SINGLE_SELECT" --single-select-options "P0-Critical,P1-High,P2-Medium,P3-Low"
gh project field-create <PROJECT_NUMBER> --owner Dawson2025 --name "Phase" --data-type "SINGLE_SELECT" --single-select-options "Phase 1: Foundation,Phase 2: Content Pipeline,Phase 3: Chat UI,Phase 4: Discord Bot,Phase 5: Testing"
gh project field-create <PROJECT_NUMBER> --owner Dawson2025 --name "Type" --data-type "SINGLE_SELECT" --single-select-options "Story,Task,Milestone,Bug,Spike"
```

### Step 4: Create issues (user stories) derived from research

For each story, create a GitHub issue and add it to the project:

```bash
# Create the issue
gh issue create --repo Dawson2025/canvas-lms --title "<story title>" --body "<story body>" --label "<labels>"

# Add to project
gh project item-add <PROJECT_NUMBER> --owner Dawson2025 --url <issue_url>
```

#### Required Stories (derived from functional requirements)

**Phase 1: Foundation — LTI Integration & Agent Runtime**

| Story | Derived From | Priority | Dependencies |
|-------|-------------|----------|--------------|
| As an instructor, I can enable Course Agent in my course navigation so students see it in the sidebar | FR-4, Finding 1 (LTI placement via `resource_placement.rb`) | P0 | None |
| As a student, I can click Course Agent and see a chat interface load within 3 seconds | FR-1 | P0 | LTI integration |
| As an instructor, I can configure the agent's welcome message and content scope | FR-4 | P1 | LTI integration |

**Phase 2: Content Pipeline**

| Story | Derived From | Priority | Dependencies |
|-------|-------------|----------|--------------|
| As an agent, I can read course content from a local filesystem directory | FR-2, FR-3, Architecture (general tools) | P0 | None |
| As a system, I can sync Canvas course content (syllabus, assignments, modules, pages, announcements) to the content directory | Finding 2 (Canvas REST API at `/api/v1/courses/:id`), NFR-2 | P0 | Canvas API access |
| As an instructor, I can add custom files (study guides, club resources) to the content directory | Feature brief (extensible beyond course) | P2 | Content directory |

**Phase 3: Chat & Query Handling**

| Story | Derived From | Priority | Dependencies |
|-------|-------------|----------|--------------|
| As a student, I can ask "What is due this week?" and get a list of assignments with dates and links | FR-2 | P0 | Content pipeline |
| As a student, I can ask about the late policy and get the relevant syllabus excerpt with a link | FR-3 | P0 | Content pipeline |
| As a student, I get "I don't have information about that" for out-of-scope questions instead of hallucinated answers | FR-5, UX Risk (hallucination) | P1 | Chat interface |

**Phase 4: Discord Bot & QR Code**

| Story | Derived From | Priority | Dependencies |
|-------|-------------|----------|--------------|
| As a student, I can DM the Discord bot and get answers about my course | Feature brief (Discord DM pattern) | P1 | Chat & query handling |
| As an instructor, I can generate a QR code that links to the Discord bot's DM | FR-6 | P2 | Discord bot |
| As a student not enrolled in the course, I am denied access with "Not authorized" | FR-7 | P1 | Auth system |

**Phase 5: Testing & Verification**

| Story | Derived From | Priority | Dependencies |
|-------|-------------|----------|--------------|
| Verify all 7 functional requirements pass acceptance criteria | Testing plan — acceptance criteria table | P0 | All phases |
| Run integration tests: LTI launch, content fetch, end-to-end chat, auth enforcement | Testing plan — integration tests | P1 | Phases 1-3 |
| Perform manual exploratory testing: concurrent users, missing content, mid-semester updates | Testing plan — manual testing (8 scenarios) | P2 | All phases |

**Non-Functional Stories**

| Story | Derived From | Priority |
|-------|-------------|----------|
| Ensure no PII is sent to LLM and unpublished content is never surfaced | NFR-1 (Security/FERPA) | P0 |
| Chat responses return within 5 seconds; support 50 concurrent users | NFR-2 (Performance) | P1 |
| Chat interface meets WCAG 2.1 AA; keyboard navigation; screen reader support | NFR-3 (Accessibility) | P1 |
| Add query count, latency, and error rate logging per course | NFR-4 (Observability) | P2 |

### Step 5: Set fields on project items

After adding issues to the project, set the Priority, Phase, and Type fields:

```bash
# Get the item ID
gh project item-list <PROJECT_NUMBER> --owner Dawson2025 --format json

# Set fields
gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <FIELD_ID> --single-select-option-id <OPTION_ID>
```

### Step 6: Verify

After all issues are created and added to the project:

1. List all project items:
   ```bash
   gh project item-list <PROJECT_NUMBER> --owner Dawson2025
   ```

2. Verify traceability — every functional requirement (FR-1 through FR-7) maps to at least one story.

3. Verify completeness — stories cover all 5 phases: Foundation, Content Pipeline, Chat UI, Discord Bot, Testing.

4. Get the project URL:
   ```bash
   gh project view <PROJECT_NUMBER> --owner Dawson2025 --format json | jq '.url'
   ```

## Integration with Lab 2 (analyze-repo)

For each story in Phase 1 (LTI Integration), the agent must reference the specific codebase findings from `implementation-research.md` Section 4:

- **LTI placement**: Story references Finding 1 — `app/models/lti/resource_placement.rb` line ~38, `COURSE_NAVIGATION` constant
- **Canvas API**: Content pipeline stories reference Finding 2 — `app/controllers/courses_controller.rb`, REST endpoints at `/api/v1/courses/:id`
- **React UI**: Chat interface story references Finding 3 — `ui/features/` isolation pattern
- **Launch flow**: Auth story references Finding 4 — `app/controllers/lti/message_controller.rb`, JWT validation

Each story body should include a "Codebase Context" section with the relevant file paths and patterns from the analysis.

## Guardrails

- **Never** create projects on repos other than `Dawson2025/canvas-lms`
- **Never** commit tokens or secrets to the repository
- **Never** invent requirements not in the research package — derive all stories from `implementation-research.md` and `feature-1.md`
- If a requirement is ambiguous, create a **Spike** story to investigate rather than guessing

## Verification Checklist

- [ ] GitHub Project exists on `Dawson2025/canvas-lms`
- [ ] All 7 functional requirements (FR-1 through FR-7) have corresponding stories
- [ ] All 4 non-functional requirements have corresponding stories
- [ ] Testing/verification stories exist (unit, integration, manual)
- [ ] Stories have Priority, Phase, and Type fields set
- [ ] Dependencies between stories are documented in story bodies
- [ ] At least one story references codebase findings from Lab 2 analysis
- [ ] Project URL is accessible and shows all items

## MCP Host Used

Claude Code (CLI) with `gh` CLI for GitHub operations. No separate GitHub MCP Server needed — `gh` CLI provides equivalent functionality with existing authentication.
