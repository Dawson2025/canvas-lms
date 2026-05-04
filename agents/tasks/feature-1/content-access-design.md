# Design Decision: How Should AI Agents Access Canvas Course Content?

## The Question

Canvas stores course content across scattered API endpoints and database tables. What's the best architecture to make this content accessible to an AI agent — and what complexity is actually justified?

---

## Part 1: Options Evaluated

### Content Access Interfaces

| Option | What It Does | Token Cost | Freshness | Extension? | Fork? |
|--------|-------------|-----------|-----------|------------|-------|
| **A. Physical sync** | API → markdown files on disk | Zero (Read/Grep) | Stale between syncs | Yes | Yes |
| **B. Virtual filesystem** | FUSE/VFS translates reads → API calls | Zero (Read) | Always fresh | Partial | Yes |
| **C. MCP tools (40+)** | Per-content-type tools | ~55K tokens static | Fresh | Yes | Yes |
| **D. CLI wrapper** | `canvas-cli` via Bash | ~0 static | Fresh | Yes | Yes |
| **E. Fork API endpoint** | `/courses/:id/ai_export` | ~0 (one call) | Fresh | No | Yes |
| **F. Rake task** | `rake canvas:ai_export` | Zero (writes files) | Fresh at export | No | Yes |

### Content Enrichment

| Option | What It Does | When It Helps | When It's Overkill |
|--------|-------------|--------------|-------------------|
| **G. Vector embeddings** | Embed chunks, semantic search | 500+ items, unstructured prose | Structured course content (<100 items) |
| **H. Knowledge graph** | Nodes + edges for relationships | Deep multi-hop prerequisite chains | Simple courses, cold start problem |
| **I. Filesystem + triggers + pointers** | Markdown with frontmatter, DAG via pointers | **Almost always** — agents know files from pretraining | Never overkill — this is the baseline |
| **J. Agent-proposed relationships** | AI infers concept links, human approves | When you want graph depth without cold start | When instructor doesn't want to review |

### Key Evidence

- **Microsoft Research**: 91-tool MCP server = 55K tokens, 85% performance degradation
- **Anthropic**: Tool accuracy degrades past 30-50 tools
- **MindStudio**: Claude Code, Cursor, Devin use grep — not vector databases
- **Neo4j benchmarks**: GraphRAG 95% on multi-hop vs 79% vector — but 2.4x latency
- **Arize (2026)**: Decouple agent interface (filesystem) from storage backend (API/DB)
- **AgentFS (Turso)**: SQLite-backed FUSE — filesystem beats specialized tools

---

## Part 2: The Filesystem-First Insight

### Most "Knowledge Graph Queries" Are Just File Lookups

| Query | Knowledge Graph Approach | Filesystem + Triggers Approach |
|-------|------------------------|-------------------------------|
| "What's in Module 3?" | `MATCH (m:Module)-[:CONTAINS]->(c)` | `ls modules/03-week-3/` |
| "Prerequisites for Module 7?" | `MATCH (m)-[:PREREQUISITE]->(p)` | Read `modules/07/module.md` → `prerequisites: [...]` |
| "What's due this week?" | `SELECT * FROM assignments WHERE due_at BETWEEN...` | `grep -r "due_at: 2026-05" assignments/` |
| "Find content about recursion" | `SELECT * FROM concepts WHERE embedding <-> query < 0.3` | `grep -r "recursion" modules/` |
| "How does concept A relate to B?" | `MATCH path = (a)-[*]-(b)` | Cross-reference in `REFERENCES.md` or typed links in frontmatter |

For a typical course with <100 content items, **the filesystem with good metadata IS the knowledge graph** — just stored as files instead of database rows.

### What Databases Actually Add (Honestly)

| Capability | Filesystem Can Do It? | When You Need a DB |
|-----------|----------------------|-------------------|
| Hierarchical traversal | Yes (directories) | Never — directories ARE hierarchy |
| Prerequisite chains | Yes (frontmatter pointers) | When chains are 5+ hops deep with cycles |
| Semantic similarity | Partial (grep finds keywords) | 500+ items where keywords fail |
| Multi-tenant access control | No (file permissions are coarse) | Multiple learners with different visibility |
| Quantitative decay/mastery | No | Spaced repetition, mastery tracking |
| Cross-course queries | Awkward (grep across directories) | "What do I know across all classes?" |

### The Trigger + Pointer DAG Pattern

Our own system already implements a DAG in the filesystem using triggers and UUID-based pointers:

```
System prompt (CLAUDE.md)
    ↓ triggers table (top-level routing)
    "deadlines/due dates"  → load deadline skill
    "prerequisites"        → load module manifest, follow prerequisite pointers
    "policy questions"     → load syllabus.md
    ↓
Module manifest (module.md with frontmatter)
    ---
    module: Week 3
    prerequisites: [modules/01-context, modules/02-architecture]
    concepts: [recursion, base-cases, call-stack]
    assignments: [assignments/lab-3.md]
    ---
    ↓ pointers (relative paths or UUIDs)
Full content (individual markdown files)
```

This is structurally equivalent to a knowledge graph — nodes (files) connected by edges (pointers in frontmatter) forming a DAG. But with zero infrastructure: no PostgreSQL, no pgvector, no embedding pipeline. Just files, frontmatter, and a trigger system the agent already knows how to use.

---

## Part 3: The Agent Orchestrator Pattern

### Why Not Just a Rigid Script?

A deterministic sync script (`canvas-sync.sh`) handles the 80% case but breaks on the 20%:
- Some professors use modules heavily, others dump everything as pages
- Some put all content in assignment descriptions, others use wiki pages
- Some have external readings linked from Canvas, others upload everything
- Some courses have clear prerequisite chains, others are flat

### The Hybrid: Agent + Deterministic Scripts

An AI agent orchestrates the process, delegating heavy lifting to deterministic scripts that save tokens:

```
┌─────────────────────────────────────────────────────────────┐
│  Content Orchestrator Agent                                  │
│  (AI — flexible, handles edge cases, makes judgment calls)   │
│                                                             │
│  Calls deterministic scripts (save tokens):                 │
│  ├── canvas-fetch.sh     → API calls, raw JSON             │
│  ├── html-to-md.sh       → HTML conversion (no AI needed)  │
│  ├── build-manifest.sh   → manifest from module structure   │
│  │                                                          │
│  Agent adds judgment (where flexibility matters):           │
│  ├── "This course doesn't use modules — reorganize by      │
│  │    assignment groups instead"                            │
│  ├── "These 3 pages are really one topic split across       │
│  │    pages — add cross-references"                         │
│  ├── "The syllabus mentions prerequisites not in module     │
│  │    metadata — add to manifest frontmatter"               │
│  ├── "This assignment references an external reading —      │
│  │    note as external dependency"                          │
│  ├── "Propose trigger rules based on content analysis"      │
│  └── "Propose concept relationships for instructor review"  │
│                                                             │
│  Outputs:                                                   │
│  ├── Agent-ready course directory (markdown + frontmatter)  │
│  ├── Proposed trigger rules (for agent routing)             │
│  └── Proposed relationship map (for instructor approval)    │
└─────────────────────────────────────────────────────────────┘
```

### What's Deterministic vs What Needs AI

| Task | Deterministic (script) | AI (agent judgment) |
|------|----------------------|-------------------|
| Fetching content from Canvas API | Yes — known endpoints, pagination | No |
| Converting HTML to markdown | Yes — regex/library | No |
| Building directory structure from modules | Yes — modules have positions | No |
| Extracting explicit prerequisites | Yes — `prerequisites` field on ContextModule | No |
| Inferring implicit prerequisites | No | Yes — "Week 3 assumes you know recursion from Week 2" |
| Organizing content without modules | No | Yes — "group by assignment_group or topic" |
| Writing trigger rules | No | Yes — "deadline queries should grep assignments/" |
| Proposing concept relationships | No | Yes — "recursion is prerequisite for tree traversal" |
| Detecting external references | Partial (find URLs) | Yes — "this URL is a required reading vs optional" |

---

## Part 4: Agent-Proposed Knowledge Structure

### The Cold Start Solution

Instead of requiring the instructor to manually build a knowledge graph OR auto-extracting a shallow one from metadata, an agent:

1. **Reads all synced course content** (already in markdown on disk)
2. **Proposes a relationship map** — concepts, prerequisites, topic connections
3. **Presents to instructor** for approve / edit / decline
4. **Stores approved relationships** as frontmatter pointers in the existing files — not in a database

```
Step 1: Agent reads modules/03-week-3/assignments/lab-3.md
        Notices: "Build on the recursion concepts from Week 2"

Step 2: Agent proposes in modules/03-week-3/module.md:
        ---
        prerequisites:
          - path: modules/02-week-2
            relationship: builds_on
            concepts: [recursion, base-cases]
            confidence: high
            evidence: "Lab 3 description references 'recursion from Week 2'"
            status: proposed  ← instructor hasn't approved yet
        ---

Step 3: Instructor reviews proposed relationships:
        ✓ Approve: recursion prerequisite (correct)
        ✗ Decline: base-cases prerequisite (not really needed)
        ✎ Edit: change "builds_on" to "prerequisite"

Step 4: Agent updates frontmatter, status: proposed → approved
```

The result is a **human-validated knowledge structure stored in markdown** — no database needed. The filesystem IS the knowledge graph. Relationships live in frontmatter pointers.

### Comparison: Three Approaches to Knowledge Structure

| Factor | Manual graph (instructor) | Auto-extract (fork metadata) | Agent-proposed, human-approved |
|--------|--------------------------|-----------------------------|---------------------------------|
| Quality | High (human knowledge) | Low (only explicit prereqs) | High (AI breadth + human judgment) |
| Effort | Hours | Zero | Minutes (review, not create) |
| Cold start? | Yes — instructor won't do it | Solved, but shallow | Solved — agent does heavy lifting |
| Infrastructure | Database + UI | Fork modification | Just files + an agent spec |
| Depth | Whatever instructor builds | Only Canvas metadata fields | Infers implicit relationships too |

---

## Part 5: Progressive Complexity Roadmap

### Start Simple, Graduate When Justified

```
Level 0: Just files
├── canvas-ai sync → flat markdown directory
├── Agent uses Read/Grep
├── No metadata, no triggers, no relationships
├── Works today, 10 minutes to set up
│
Level 1: Files + metadata (RECOMMENDED STARTING POINT)
├── Frontmatter on every file (due_at, module, position, type)
├── manifest.json listing all content
├── Module manifests with prerequisites
├── Triggers for common query patterns
│
Level 2: Files + agent-proposed relationships
├── Agent orchestrator infers concept connections
├── Instructor reviews/approves proposals
├── Relationships stored as frontmatter pointers
├── Trigger rules auto-generated from content analysis
│
Level 3: Files + vector search (ONLY IF NEEDED)
├── Embed content into pgvector for semantic search
├── Justified when: 500+ items, lots of unstructured prose
├── Agent uses grep first, falls back to vector search
│
Level 4: Files + knowledge graph database (ONLY IF NEEDED)
├── PostgreSQL + Apache AGE for multi-hop traversal
├── Justified when: multi-tenant, mastery tracking, cross-course queries
├── The filesystem remains the source of truth — DB is derived index
```

Each level includes everything below it. You only move up when the simpler approach demonstrably fails for your use case.

---

## Part 6: Two Product Tiers (Extension vs Fork)

### The Cursor Pattern

Cursor couldn't build its AI features as just a VS Code extension — it needed to fork. Same choice here: some features work as a client-side add-on to vanilla Canvas, others require architectural control.

### Tier 1: Extension Model — Any Canvas Instance

```
Recommended: Level 1 (files + metadata) with agent orchestrator

canvas-ai sync --course 407700 --output ./my-course/

my-course/
├── manifest.json                  ← course structure, module order
├── syllabus.md                    ← cleaned HTML → markdown
├── modules/
│   ├── 01-context-efficiency/
│   │   ├── module.md              ← prerequisites, concepts, completion reqs
│   │   ├── assignments/
│   │   │   └── lab-1-setup.md     ← description + due_at + rubric in frontmatter
│   │   └── pages/
│   │       └── instruction-1-1.md
│   └── 02-architectural-state/
│       ├── module.md              ← prerequisites: [01-context-efficiency]
│       └── ...
├── announcements/
├── files/
└── .triggers/                     ← agent routing rules
    ├── deadline-queries.md
    ├── policy-lookup.md
    └── prerequisite-check.md
```

**What the instructor does**: `pip install canvas-ai-tools && canvas-ai sync --course 407700`
**Agent orchestrator**: Reviews output, proposes trigger rules and relationships, presents for approval.

### Tier 2: Fork Model — Our Canvas Fork

```
Recommended: Level 2 (files + agent-proposed relationships) built server-side

Instructor enables "AI Agent" in course settings → one checkbox
Server-side: Rake task exports content, agent proposes relationships,
instructor approves in Canvas UI.
```

**Additional fork capabilities**:
- Server-side export (no N+1 API calls, direct DB access)
- Auto-reindex on content change (background jobs)
- Instructor approval UI built into Canvas
- FERPA enforcement at query time (server-side scope)
- Virtual filesystem controller (future: runtime materialization)

### When to Graduate from Tier 1 to Tier 2

| Signal | What It Means |
|--------|-------------|
| Instructor wants zero setup | Need fork with integrated UI |
| Need always-fresh content | Need server-side VFS or auto-reindex |
| FERPA audit required | Need server-side enforcement |
| Multiple courses, shared infrastructure | Need centralized deployment |
| Cross-course agent queries | Need fork-level data access |

---

## Part 7: Codebase Findings (Canvas Internals)

### How Canvas Actually Stores Content

| Content Type | Model | Storage | Content Field |
|-------------|-------|---------|---------------|
| Syllabus | `Course` | DB TEXT (16MB max) | `syllabus_body` (HTML) |
| Assignments | `Assignment` | DB | `description` (HTML) + `due_at`, `points_possible` |
| Pages | `WikiPage` | DB | `body` (HTML) + `url` (slug) |
| Discussions | `DiscussionTopic` | DB | `message` (HTML) |
| Announcements | `Announcement` (STI) | DB | Inherits from DiscussionTopic |
| Files | `Attachment` | DB metadata + S3/disk | `filename`, `instfs_uuid` |
| Module structure | `ContextModule` | DB | `prerequisites` (serialized), `completion_requirements` |
| Module items | `ContentTag` | DB | **Polymorphic**: `content_id` + `content_type` |

### The ContentTag Pattern

`ContentTag` is the polymorphic join that makes modules work — can point to Assignment, WikiPage, DiscussionTopic, Attachment, ExternalUrl, Quiz, LTI Tool, or SubHeader. This is what the sync script must resolve.

### Existing AI Models (Canvas 2026)

Canvas already has `AiExperience`, `AiConversation`, `AiExperienceContextFile` — the fork can extend these rather than building from scratch.

---

## Part 8: Implementation Plan for Lab 3.2

### What We'll Build

1. **`canvas-ai sync` CLI tool** (Python) — fetches course content via API, converts HTML→markdown, writes agent-ready directory with frontmatter metadata and module manifests
2. **`agents/feature-implementation.md`** — already created, describes the implementation workflow
3. **Execute one work item** — pick item #5 (sync Canvas content), implement as PR, move through board cycle

### What We Won't Build Yet (But Design For)

- Agent orchestrator (Level 2 — future lab)
- Agent-proposed relationships (Level 2 — future lab)
- Server-side Rake task (Tier 2 fork — future)
- Virtual filesystem controller (Tier 2 fork — future)
- Vector/graph enrichment (Level 3-4 — only when justified)

---

## Sources

- [AgentFS — Turso Database](https://github.com/tursodatabase/agentfs) — SQLite-backed FUSE filesystem for agents
- [AI Agent Interfaces in 2026 — Arize](https://arize.com/blog/agent-interfaces-in-2026-filesystem-vs-api-vs-database-what-actually-works/) — Runtime materialization, interface decoupling
- [Tool-Space Interference — Microsoft Research](https://www.microsoft.com/en-us/research/blog/tool-space-interference-in-the-mcp-era-designing-for-agent-compatibility-at-scale/) — 91-tool MCP = 55K tokens, 85% degradation
- [Why Cursor, Claude Code, Devin Use grep, Not Vectors — MindStudio](https://www.mindstudio.ai/blog/is-rag-dead-what-ai-agents-use-instead) — Filesystem outperforms RAG for structured content
- [Knowledge Graph vs Vector RAG — Neo4j](https://neo4j.com/blog/developer/knowledge-graph-vs-vector-rag/) — 1.5x accuracy on complex queries
- [GraphRAG Accuracy — FalkorDB](https://www.falkordb.com/blog/graphrag-accuracy-diffbot-falkordb/) — 2x better on complex queries
- [Canvas + OpenAI Partnership — Instructure](https://www.instructure.com/press-release/instructure-and-openai-announce-global-partnership-embed-ai-learning-experiences)
- [CLI vs MCP for AI Agents](https://jannikreinhard.com/2026/02/22/why-cli-tools-are-beating-mcp-for-ai-agents/) — CLI leaves 95% of context window for reasoning
- [ML Mastery Vector vs Graph RAG](https://machinelearningmastery.com/vector-databases-vs-graph-rag-for-agent-memory-when-to-use-which/) — Hybrid consensus
- [Moodle AI Subsystem](https://moodledev.io/docs/4.5/apis/subsystems/ai) — Plugin architecture for LLM providers
- [IgniteAI Agent — Instructure](https://www.prnewswire.com/news-releases/instructure-delivers-on-safe-simple-ai-promise-with-igniteai-and-major-ecosystem-updates-302638807.html) — Canvas native AI agent
- [AIOS — Rutgers University](https://github.com/agiresearch/AIOS) — LLM-based semantic filesystem
