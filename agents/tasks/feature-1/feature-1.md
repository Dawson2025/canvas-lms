# Feature 1: Canvas Course AI Platform

## Problem Statement

Instructors want to bring AI capabilities into their courses but face high barriers: building custom tools requires engineering skills, hosted AI services cost money, and standalone tools don't integrate with the LMS where students already work. Students, meanwhile, have questions about course logistics that don't warrant emailing the instructor — and could benefit from AI assistance that understands their specific course context.

There's no easy way for a non-technical instructor to say "I want an AI assistant for my course" and have it just work — inside Canvas, on Discord, accessible via QR code at a presentation — without building anything from scratch.

## Proposed Solution

A **Course AI Platform** — a system that lets any instructor easily add AI capabilities to their course. The platform:

1. **Automatically ingests course content** from Canvas (syllabus, assignments, modules, files, announcements, pages) into a local filesystem the agent can read
2. **Provides general-purpose tools** (filesystem, terminal, search) so the agent can find and use course content — no custom tools needed per course
3. **Supports skills** (like Claude Code skills) that teach the agent course-specific patterns — instructors or TAs can write these in plain markdown
4. **Connects to multiple channels** — Canvas (LTI), Discord (bot DM), QR code access — all hitting the same agent backend
5. **Extends beyond the course** — the agent can also access external resources related to the course (club Discords, study groups, supplemental materials, instructor-provided links)

### Key Capabilities

- **Course-aware chat**: Students ask questions; the agent answers using published course content as context
- **Navigation help**: "Where do I find the rubric for Assignment 3?" → direct link
- **Deadline awareness**: "What's due this week?" → filtered, prioritized list from course calendar
- **Policy lookup**: "Can I submit late?" → pulls from syllabus grading policy section
- **Discord bot (DM pattern)**: Students DM the bot directly on Discord — like Slack's "Sandbot" pattern. No new app to install, students already have Discord on their phones
- **QR code access**: Generates a QR code that links to the Discord bot's DM. Scan on phone during lecture → opens Discord → ask the bot about the course
- **Extensible beyond the course**: Instructor can add files, links, or MCP tools for things outside Canvas — club resources, external documentation, study materials, conference links

### Architecture: General Tools + Skills over CLIs

The agent doesn't use custom-built tools for each action. Instead, it has **general-purpose tools** and uses them to interact with existing CLIs and filesystems — the same pattern that makes Claude Code powerful:

| Layer | What It Provides | Examples |
|-------|-----------------|----------|
| **General tools** | Filesystem read/write/search, terminal/bash, MCP servers | Read a syllabus file, grep for "late policy", run a CLI command |
| **Skills** | Markdown instructions that teach the agent course-specific patterns | `/deadline-check`, `/policy-search`, `/find-assignment` |
| **Course content** | A directory of files pulled from Canvas + instructor additions | `/courses/cse290r/syllabus.md`, `/courses/cse290r/assignments/*.md` |
| **MCP tools** (optional) | Custom integrations via SimpleMCP kits or any MCP server | Canvas API access, Discord webhooks, external data sources |

This means **no custom code per course**. An instructor enables the platform, content syncs, and the agent works immediately using general tools to read and search the course files.

### Core Design Principle: Complexity on Demand

The platform starts simple and scales without rewriting. At minimum, you need:
- An LLM (free via OpenRouter/Groq)
- A system prompt
- Dynamic context that loads on demand (skills — markdown files with YAML frontmatter)
- A few general-purpose MCP tools (filesystem, terminal)

Skills teach the agent how to use CLIs and tools — keeping the actual MCP tool count minimal while enabling the agent to do anything those CLIs can do.

#### The Noise Problem and Trigger Hierarchy

As you scale up — more skills, more MCP tools, more context avenues — each one adds to the agent's static context. Every listing competes for attention. With 50 skills loaded at once, the agent doesn't know which to reach for. More MCP servers, more tools, more listings = more noise = worse performance.

**Solution: Hierarchical trigger loading.** The system prompt contains only **minimal top-level triggers** — short pattern-matching rules that recognize categories of queries. When a trigger fires, it loads the specific skill/context for that category, which may contain its own sub-triggers. Context expands on demand, not upfront.

```
STATIC CONTEXT (always loaded — kept minimal):
  System prompt + identity
  Top-level triggers:
    "deadlines/due dates"  → load /deadline-check
    "policies/rules"       → load /policy-search
    "assignments/labs"     → load /assignment-lookup
    "course structure"     → load /module-nav

DYNAMIC CONTEXT (loaded per-trigger, then released):
  /deadline-check skill:
    Reads assignments/*.md, filters by date
    Sub-trigger: "late submission?" → loads grading_policy.md

  /policy-search skill:
    Reads syllabus.md, grading_policy.md
    Sub-trigger: "grade dispute?" → loads appeals_process.md
```

A student asking "What's due this week?" loads only the deadline skill — not the grading policy, not the admin settings, not every other skill. Clean context, focused retrieval, no noise.

This is the same pattern used to scale AI coding agents across hundreds of skills and tools — and it applies directly to course agents.

For most courses, this foundational stack — LLM + system prompt + trigger-loaded skills + general filesystem tools — is **all you need**. RAG, vector databases, knowledge graphs, and learning memory are available when the use case demands it (large content libraries, adaptive learning, research programs), but they're not prerequisites. The foundation handles the 80% case. The advanced infrastructure is there for the 20% that needs it.

### Multi-User Concurrency: Session-Per-User Model

Each user interaction spawns its own independent agent session — the same way a developer can open multiple Claude Code terminals, each with their own conversation but reading the same project files.

```
Student A (Discord DM) ──→ Agent session A ──┐
Student B (Discord DM) ──→ Agent session B ──┤── same course content dir
Student C (Canvas LTI) ──→ Agent session C ──┤   same skills & system prompt
Student D (QR → Discord) → Agent session D ──┘   same model backend
                                                  ↓
                                             OpenRouter / Groq (free)
```

Each session:
- Has its own context window (conversations are isolated per user)
- Points at the same course content directory (read-only, shared)
- Uses the same skills and system prompt (configured by instructor)
- Runs independently and concurrently — no blocking, no queue
- Can be resumed if the student comes back later (session continuity)

The Discord bot or Canvas LTI frontend is just an **interface layer** — it maps incoming messages to agent sessions and pipes responses back. The agent runtime handles the actual conversation, tool use, and content retrieval.

**Implementation options for session management:**

| Approach | How It Works | Concurrency |
|----------|-------------|-------------|
| `claude` CLI in subprocess/pipe mode | Discord bot spawns `claude` process per user, pipes messages in/out | One process per active user |
| Anthropic Agent SDK | Programmatic Python/TypeScript — each message creates an agent call | Async, many concurrent |
| Custom tool-calling loop + Groq API | Lightweight Python — each message is an independent API call with tools | Fully concurrent, minimal overhead |
| SimpleMCP-backed agent | SimpleMCP kits provide tools, any LLM handles the conversation | Depends on LLM backend |

All approaches share the same principle: **the course content and skills are shared, the conversations are isolated.** This is how the bot can be always-on and serve unlimited concurrent users — each user is just another lightweight session reading the same files.

### Architecture Tiers

The platform supports multiple architecture approaches — from zero-cost quick start to fully custom builds. These are not mutually exclusive; an institution can start with Tier 1 and graduate to Tier 3 as needs grow.

#### Tier 1: Pre-built Runtime (fastest, free)

Use **Claude Code + OpenRouter** as the agent runtime. Claude Code already provides filesystem tools, terminal, skills, and MCP server support. OpenRouter routes to free models (Groq, Gemini, Llama). Zero custom code needed.

| Component | Source | Cost |
|-----------|--------|------|
| Agent runtime | Claude Code (existing) | Free (CLI is free) |
| Model inference | OpenRouter → Groq / Gemini / Llama | $0 (free tiers) |
| Filesystem tools | Claude Code built-in (Read, Write, Grep, Bash) | Free |
| Skills | `.claude/skills/*.md` — markdown files | Free |
| MCP tools | SimpleMCP kits or any MCP server | Free |
| Course content | Local directory synced from Canvas API | Free |

**Best for**: Quick start, individual instructors, small deployments, prototyping.

#### Tier 2: Managed Service (scalable, low-cost)

A hosted backend with a proper API. Course content stored in a database (Supabase free tier with pgvector for optional RAG). Discord bot and Canvas LTI as frontends. Can use free or paid models.

| Component | Source | Cost |
|-----------|--------|------|
| Agent backend | Cloudflare Workers or Vercel (hosted) | $0 (free tier) |
| Model inference | Groq / Gemini (free) or Claude (paid) | $0 – $3/MTok |
| Content storage | Supabase pgvector or filesystem | $0 (free tier) |
| RAG (optional) | Vector search over embedded course content | $0 (free embeddings via Cloudflare) |
| Discord bot | discord.js on same host | Free |

**Best for**: Department-wide deployments, multiple courses, usage analytics needed.

#### Tier 3: Custom Build (maximum control)

Build the agent from the ground up. Custom tool-calling loop with any LLM API. Full control over prompt engineering, tool definitions, caching, rate limiting, auth. Can use SimpleMCP kits for modular tool development.

| Component | Source | Cost |
|-----------|--------|------|
| Agent loop | Custom Python (tool-calling loop, ~200 lines) | Free |
| Model inference | Any provider — Groq, Gemini, Claude, Ollama (self-hosted) | $0 – varies |
| Tools | Custom-defined functions or SimpleMCP kits | Free |
| Content | Filesystem, database, or hybrid | Free |
| Frontends | Custom Canvas LTI app + Discord bot | Free |

**Best for**: Institutions with engineering resources, specific compliance requirements, research use cases, maximum customization.

### Model Backend Options (all tiers)

| Option | Cost | Quality | Speed |
|--------|------|---------|-------|
| **Groq** (Llama 3.3 70B) | $0 | Good | 300+ tok/s |
| **Google Gemini** (Flash) | $0 | Good | Fast |
| **OpenRouter free models** | $0 | Varies | Varies |
| **Cloudflare Workers AI** | $0 | Good (edge) | Low latency |
| **Ollama** (self-hosted) | $0 (needs GPU) | Varies | Depends on hardware |
| **Anthropic Claude** | ~$3/MTok | Best | Fast |
| **OpenAI GPT** | ~$2.50/MTok | Excellent | Fast |

### Per-Course Isolation

Each course gets its own isolated agent instance. An instructor sets up the agent for their course — it only knows that course's content and only enrolled students can access it. There is no shared agent across courses.

- Instructor for CSE 290R sets up an agent → it reads only CSE 290R's content directory
- Instructor for MATH 341 sets up a separate agent → it reads only MATH 341's content directory
- A student enrolled in both sees two separate agents — never cross-contaminated
- The Discord bot enforces this: each course gets its own Discord server (or channel), and the bot only responds with that course's content in that context

### User Roles

| Role | Capabilities |
|------|-------------|
| Student | Chat with agent for enrolled courses only; access via Canvas LTI or Discord bot DM; no access to other courses' agents |
| Instructor | Set up their own course agent; add custom content/skills; configure Discord server; generate QR code; choose model backend; view usage analytics |
| Admin | Set institution-level defaults; manage API keys; control which courses can enable the feature |

### Why Canvas (not a standalone tool)

- Agent needs course content access — Canvas already has it via APIs
- Permissions are already solved — Canvas knows who's enrolled, who's an instructor
- No separate login — students are already in Canvas
- LTI placement means it shows up as a native navigation item, not a third-party link

## Scope

**In scope**: Course content ingestion from Canvas, filesystem-based agent with general tools, skills system, Discord bot (DM pattern), QR code linking to Discord bot, per-course isolation, multiple model backends (including free options), instructor self-service setup, extensibility beyond course content.

**Out of scope (for now)**: Writing/submitting on behalf of students, grade predictions, real-time lecture transcription, tutoring for course subject matter beyond what's in the materials.

### Knowledge Organization: Entity Ecosystem (Opt-In Complexity)

The platform can optionally use an **entity-based knowledge organization system** — the same pattern used to manage large-scale AI coding projects. Each course becomes an entity with structured knowledge, rules, skills, and context. The system is opt-in at every level — a course only takes on complexity when it needs it.

#### Level 1: Just Files
A directory of markdown files. The agent reads and searches them. No structure needed beyond filenames.
```
courses/cse290r/
  syllabus.md
  assignments/lab-1.md
  announcements/welcome.md
```

#### Level 2: Entity Structure
The course becomes a proper entity with organized knowledge, rules, and skills. Instructors or TAs can write skills in markdown. Knowledge is categorized.
```
courses/cse290r/
  0AGNOSTIC.md                        ← source of truth
  .0agnostic/
    01_knowledge/                     ← syllabus, policies, FAQs
    02_rules/                         ← "don't answer about grades directly"
    05_handoff_documents/             ← TA shift notes, section handoffs
    06_context_avenue_web/
      01_file_based/
        05_skills/                    ← /deadline-check, /find-rubric
```

#### Level 3: Full Entity Ecosystem
Layers, stages, propagation chains, trigger pointers, UUID-based referencing, context chaining, memory systems. Supports multi-section courses, TA delegation, semester-over-semester evolution.
```
courses/cse290r/
  0AGNOSTIC.md
  .0agnostic/
    01_knowledge/
    02_rules/
    03_protocols/                     ← grading workflows, office hours protocols
    04_episodic_memory/               ← session history across semesters
    05_handoff_documents/             ← cross-section, cross-semester
  layer_1_group/
    layer_1_modules/                  ← child entities per module/unit
      module_01_intro/
      module_02_features/
```

#### Level 4: Knowledge Infrastructure
RAG with vector databases (pgvector), knowledge graphs with typed relationships, learning memory with mastery tracking, evidence-graded research outputs. For adaptive learning, research courses, or institution-wide deployments.

Each level includes everything below it. Moving up is additive — just add directories and files. The agent's general tools (filesystem, search, terminal) work the same at every level. The entity ecosystem was originally built for coding agents (Claude Code, Codex, Cursor Agent, Gemini CLI), but because it's just files and directories, any agent with filesystem access can use it — including LangChain, custom Python loops, or any system that can read files.

### Future Direction: Hierarchical Agent System

A natural evolution is a **school-level agent** that sits above course agents:

- Students ask cross-cutting questions: "What's due across all my classes this week?" → school agent fans out to each enrolled course agent, aggregates results
- Instructors or advisors get a department-level view: "Which students are falling behind across my courses?"
- The school agent doesn't duplicate course content — it delegates to course agents and synthesizes
- **Inter-class awareness**: Prerequisite checking ("Am I ready for CSE 450?"), workload balancing across classes ("I have exams in 3 classes next week — help me plan"), identifying overlapping content between classes, coordinating group projects that involve students from multiple sections
- Mirrors the Canvas hierarchy: institution → account → course

This is explicitly **not** part of the current feature scope, but the per-course isolation design is built to support it later — each course agent already has a clean API boundary that a parent agent can orchestrate.
