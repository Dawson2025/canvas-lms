# Feature 1: Canvas Course Agent

## Problem Statement

Students frequently have questions about course logistics — assignment due dates, grading policies, module prerequisites, where to find specific materials — that don't warrant emailing the instructor. Instructors spend significant time answering repetitive questions that are already answered in the syllabus, assignment descriptions, or module content.

## Proposed Solution

A **Course Agent** — an AI-powered course assistant accessible as a navigation item within each Canvas course. The agent has read access to all published course content (syllabus, assignments, modules, files, announcements, pages) and can answer student questions in natural language.

### Key Capabilities

- **Course-aware chat**: Students ask questions; the agent answers using published course content as context
- **Navigation help**: "Where do I find the rubric for Assignment 3?" → direct link
- **Deadline awareness**: "What's due this week?" → filtered, prioritized list from course calendar
- **Policy lookup**: "Can I submit late?" → pulls from syllabus grading policy section
- **Discord bot (DM pattern)**: Students DM the bot directly on Discord — like Slack's "Sandbot" pattern. No new app to install, students already have Discord on their phones
- **QR code access**: Generates a QR code that links to the Discord bot's DM. Scan on phone during lecture → opens Discord → ask the bot about the course. No separate web app needed
- **Dual-channel architecture**: The agent backend is a standalone service — Canvas (LTI) and Discord (bot DM) are both frontends querying the same knowledge base

### Per-Course Isolation

Each course gets its own isolated agent instance. An instructor sets up the agent for their course — it only knows that course's content and only enrolled students can access it. There is no shared agent across courses.

- Instructor for CSE 290R sets up an agent → it indexes only CSE 290R content
- Instructor for MATH 341 sets up a separate agent → it indexes only MATH 341 content
- A student enrolled in both sees two separate agents — never cross-contaminated
- The Discord bot enforces this: each course gets its own Discord server (or channel), and the bot only responds with that course's content in that context

### User Roles

| Role | Capabilities |
|------|-------------|
| Student | Chat with agent for enrolled courses only; access via Canvas LTI or Discord bot DM; no access to other courses' agents |
| Instructor | Set up their own course agent; configure content scope, welcome message, Discord server link; generate QR code; view usage analytics |
| Admin | Set institution-level defaults; manage API keys; control which courses can enable the feature |

### Why Canvas (not a standalone tool)

- Agent needs course content access — Canvas already has it via APIs
- Permissions are already solved — Canvas knows who's enrolled, who's an instructor
- No separate login — students are already in Canvas
- LTI placement means it shows up as a native navigation item, not a third-party link

## Scope

**In scope**: Read-only course content Q&A, deadline queries, material navigation, Discord bot (DM pattern), QR code linking to Discord bot, per-course enable/disable, dual-channel access via standalone backend.

**Out of scope (for now)**: Writing/submitting on behalf of students, grade predictions, cross-course queries, real-time lecture transcription, tutoring for course subject matter beyond what's in the materials.

### Future Direction: Hierarchical Agent System

A natural evolution is a **school-level agent** that sits above course agents:

- Students ask cross-cutting questions: "What's due across all my classes this week?" → school agent fans out to each enrolled course agent, aggregates results
- Instructors or advisors get a department-level view: "Which students are falling behind across my courses?"
- The school agent doesn't duplicate course content — it delegates to course agents and synthesizes
- **Inter-class awareness**: Prerequisite checking ("Am I ready for CSE 450?"), workload balancing across classes ("I have exams in 3 classes next week — help me plan"), identifying overlapping content between classes, coordinating group projects that involve students from multiple sections
- Mirrors the Canvas hierarchy: institution → account → course

This is explicitly **not** part of the current feature scope, but the per-course isolation design is built to support it later — each course agent already has a clean API boundary that a parent agent can orchestrate.
