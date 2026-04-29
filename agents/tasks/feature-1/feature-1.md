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

### User Roles

| Role | Capabilities |
|------|-------------|
| Student | Chat with agent about enrolled courses; access via web or QR code |
| Instructor | Enable/disable per course; configure agent persona and knowledge scope; view usage analytics |
| Admin | Set institution-level defaults; manage API keys; control which courses can use the feature |

### Why Canvas (not a standalone tool)

- Agent needs course content access — Canvas already has it via APIs
- Permissions are already solved — Canvas knows who's enrolled, who's an instructor
- No separate login — students are already in Canvas
- LTI placement means it shows up as a native navigation item, not a third-party link

## Scope

**In scope**: Read-only course content Q&A, deadline queries, material navigation, Discord bot (DM pattern), QR code linking to Discord bot, per-course enable/disable, dual-channel access via standalone backend.

**Out of scope (for now)**: Writing/submitting on behalf of students, grade predictions, cross-course queries, real-time lecture transcription, tutoring for course subject matter beyond what's in the materials.
