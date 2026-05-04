# Design Decision: How Should AI Agents Access Canvas Course Content?

## The Question

Canvas stores course content across scattered API endpoints (pages, assignments, modules, files, syllabus, announcements, discussions). What's the best architecture to make this content accessible to an AI agent?

## Options Evaluated

### Option A: Physical Filesystem Sync

Sync Canvas API → local markdown files on a schedule.

```
canvas-sync.sh --course 407700 → courses/cse290r/syllabus.md, assignments/*.md, etc.
Agent uses: Read, Grep, Bash (general tools)
```

| Pro | Con |
|-----|-----|
| Simple, works with any agent | Stale data between syncs |
| Offline-capable | Storage duplication |
| Zero context cost (no tools needed) | Sync script maintenance |
| Agents already know how to read files | Doesn't scale to many courses |

### Option B: Virtual Filesystem (Runtime Materialization)

Present Canvas API data as files on demand — no persistent copies.

**Industry examples**: AgentFS (Turso/SQLite-backed FUSE), mcp-virtual-fs (PostgreSQL-backed MCP server), AIOS (Rutgers — LLM in OS kernel), Arize Phoenix Insight (runtime materialization of remote data).

```
Agent reads courses/cse290r/assignments/lab-3.md
    → VFS intercepts → GET /api/v1/courses/407700/assignments?search=lab-3
    → Returns formatted markdown on the fly
```

| Pro | Con |
|-----|-----|
| Always fresh, no sync lag | Complex to build (FUSE or MCP VFS layer) |
| Familiar filesystem interface (zero learning cost) | Latency per read (API call behind every file access) |
| No storage duplication | Requires API auth at runtime |
| Runtime materialization is the emerging best practice (Arize) | Offline access requires fallback cache |

**Key insight from research**: Arize's analysis (2026) found the winning pattern is to decouple the agent interface (filesystem) from the storage backend (API/DB). The agent sees files; the system fetches on demand.

### Option C: Custom MCP Tools (What We Already Have)

Purpose-built tools per content type — `canvas_assignment_list`, `canvas_module_get`, etc.

```
Agent calls: mcp__canvas__canvas_assignment_list(course_id=407700)
    → Returns structured JSON
```

| Pro | Con |
|-----|-----|
| Already exists (canvas-mcp) | Tool explosion: our canvas-mcp has 40+ tools |
| Typed, structured responses | Microsoft Research: 91-tool MCP server = 55K tokens before any work |
| Auth handled by MCP server | Performance degrades past 30-50 tools (Anthropic) |
| Real-time data | Agent must know which tool to call |

**Critical evidence**: Microsoft Research found stacking multiple MCP servers reaches 150K+ tokens of tool definitions alone. Multi-step reasoning breaks down after 3-4 tool calls from accumulated context. Models experience up to 85% performance reduction with large tool spaces.

### Option D: CLI Wrapper (Thin CLI over Canvas API)

One `canvas` CLI the agent calls via Bash — single general tool.

```bash
canvas courses list
canvas assignments --course 407700 --due-this-week
canvas pages --course 407700 --search "syllabus"
canvas sync --course 407700 --output ./courses/cse290r/
```

| Pro | Con |
|-----|-----|
| Single tool (Bash) — zero tool context cost | Agent must learn CLI syntax |
| Composable: piping, scripting, chaining | Output parsing overhead |
| CLI knowledge from LLM pretraining | Still requires API auth at runtime |
| Can combine with filesystem sync as a subcommand | Must build the CLI |

**Industry evidence**: Leading AI coding agents (Claude Code, Cursor, Devin) do NOT use vector databases — they use grep, file tree inspection, and selective reading. CLI tools leave 95% of the context window available for reasoning.

### Option E: New API on Canvas Fork

Add AI-optimized endpoints to our Canvas fork.

```
GET /api/v1/courses/407700/ai-context
    → Returns everything in one call: syllabus, assignments, modules, pages
GET /api/v1/courses/407700/ai-context/search?q=late+policy
    → Semantic search across all course content
```

| Pro | Con |
|-----|-----|
| Purpose-built for AI consumption | Fork maintenance burden |
| Single call for all content | Upstream divergence |
| Can include semantic search | Only works on our fork |
| Can enforce FERPA filtering server-side | Engineering effort |

### Option F: Vector Database (RAG)

Embed all course content into pgvector, retrieve via semantic search.

```
query_course_content("What's the late policy?")
    → Returns top-k chunks with similarity scores
```

| Pro | Con |
|-----|-----|
| Semantic search (finds content by meaning) | Chunking destroys document structure |
| Works for large unstructured corpora | Silent failures (misses look like no results) |
| pgvector competitive (471 QPS at 99% recall for 50M vectors) | Course content is inherently structured — chunking loses this |
| Good for discussion posts, long readings | Overkill for structured course objects |

**Key finding**: Course content is inherently structured (courses > modules > items > assignments). This structure maps naturally to filesystems or knowledge graphs. Chunking it into vector embeddings destroys the relationships that make course navigation work. "What's due after Module 3?" is a structural query, not a semantic one.

### Option G: Knowledge Graph

Represent course structure as nodes and edges in Apache AGE or Neo4j.

```cypher
MATCH (m:Module)-[:CONTAINS]->(a:Assignment)
WHERE m.position > 3
RETURN a.title, a.due_date
ORDER BY a.due_date
```

| Pro | Con |
|-----|-----|
| Multi-hop: "prerequisites for Module 7?" | Cold start: must build the graph first |
| Relationship-aware: module order, concept deps | Overkill for simple content retrieval |
| 1.5x better accuracy on complex queries (benchmarks) | Requires entity extraction pipeline |
| Natural fit for educational content | More infrastructure to maintain |

**Benchmark evidence**: Semantic GraphRAG answers ~95% of multi-hop questions (MuSiQue dataset) vs 79% for vector RAG. But GraphRAG has 2.4x higher latency and 13.4% lower accuracy on simple fact retrieval.

---

## Codebase Findings: How Canvas Actually Stores Content

Since we have the Canvas fork, we looked at the source code directly. This changes the design options.

### Storage Pattern

| Content Type | Model | Storage | Content Field |
|-------------|-------|---------|---------------|
| Syllabus | `Course` | DB (TEXT, 16MB max) | `syllabus_body` (HTML) |
| Assignments | `Assignment` | DB | `description` (HTML) + `due_at`, `points_possible` |
| Pages | `WikiPage` | DB | `body` (HTML) + `url` (slug) |
| Discussions | `DiscussionTopic` | DB | `message` (HTML) |
| Announcements | `Announcement` (STI) | DB | Inherits from DiscussionTopic, `type='Announcement'` |
| Files | `Attachment` | DB metadata + S3/disk | `filename`, `content_type`, `instfs_uuid` |
| Module structure | `ContextModule` | DB | `name`, `prerequisites` (serialized), `completion_requirements` |
| Module items | `ContentTag` | DB | **Polymorphic**: `content_id` + `content_type` → any model above |

### The ContentTag Pattern (Critical)

`ContentTag` is the polymorphic join table that makes modules work. A single content_tag can point to Assignment, WikiPage, DiscussionTopic, Attachment, ExternalUrl, Quiz, LTI Tool, or a SubHeader. This is how Canvas achieves "put anything in a module."

### Existing AI Models (Canvas 2026)

Canvas already added AI features we can extend:

| Model | Purpose | Key Design |
|-------|---------|-----------|
| `AiExperience` | AI learning tool in a course | Has `context_files` (attachments), `learning_objective`, `llm_conversation_context_id` |
| `AiConversation` | Student ↔ AI chat | Links `user_id` + `course_id` + `ai_experience_id` |
| `AiExperienceContextFile` | Files for AI context | Join table: `ai_experience_id` → `attachment_id` with `llm_conversation_service_document_id` |

### Fork-Specific Options (Not Available via API Alone)

Because we own the fork, we can:

1. **Add a server-side export endpoint**: `GET /api/v1/courses/:id/ai_export` — Rails resolves all ContentTags, converts HTML→markdown, bundles everything in one response. Zero N+1 queries.
2. **Add a Rake task**: `rake canvas:ai_export[course_id,output_dir]` — dumps course content directly from the database to a filesystem directory.
3. **Extend AiExperience**: Canvas's existing AI model already links courses to AI-ready content files. We could extend this to auto-index all course content.
4. **Add a virtual filesystem controller**: A Rails controller that presents course content as navigable paths (e.g., `GET /courses/:id/fs/modules/week-1/assignments/lab-3.md`).

These options are MORE efficient than the REST API because they bypass the N+1 API call problem — the server resolves everything in one query chain.

---

## Recommended Architecture: Hybrid (D + A + G)

Based on the research, the best approach combines three layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  Agent Interface Layer                                          │
│                                                                 │
│  1. canvas CLI (via Bash tool) — live queries, auth ops         │
│     canvas assignments --course 407700 --due-this-week          │
│     canvas sync --course 407700 --output ./content/             │
│                                                                 │
│  2. Filesystem (Read/Grep) — cached content for deep analysis   │
│     courses/cse290r/syllabus.md, assignments/*.md               │
│     Refreshed by `canvas sync` subcommand                       │
│                                                                 │
│  3. Knowledge graph (optional) — structural queries             │
│     "What concepts from Week 3 do I need for Week 7?"           │
│     Powered by Apache AGE on same PostgreSQL                    │
│                                                                 │
│  NOT USED for primary access:                                   │
│  - 40+ MCP tools (too much noise, 55K+ tokens)                 │
│  - Vector RAG as primary (destroys structure)                   │
│  - Virtual filesystem (too complex for course prototype)        │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Combination

| Layer | What It Handles | Why It's Best For This |
|-------|----------------|----------------------|
| **CLI** | Live queries, auth ops, sync trigger | Single tool (Bash), zero context cost, composable |
| **Filesystem** | Deep content analysis, grep, bulk reads | Agents know files from pretraining, offline-capable |
| **Knowledge graph** | Structural queries (prerequisites, sequences) | Course content is inherently relational |

### What We DON'T Use (And Why)

| Rejected | Reason |
|----------|--------|
| 40+ MCP tools | Tool explosion — our own research shows 30-50 limit |
| Vector RAG as primary | Chunking destroys course structure; silent failures |
| Virtual filesystem | Too complex for prototype; runtime materialization is future work |
| New fork API | Upstream divergence; CLI wrapper achieves same goal |

### Implementation Order for Lab 3.2

Since we own the Canvas fork, we can build server-side rather than client-side:

1. **Add `rake canvas:ai_export` task** — server-side export that resolves ContentTags, converts HTML→markdown, writes to a course directory. One command, zero N+1 API calls.
2. **The exported filesystem IS the content directory** — agent reads with general Read/Grep tools.
3. **Optional: Add `/api/v1/courses/:id/ai_export` endpoint** — same logic as rake task but accessible via HTTP for remote agents.
4. **Knowledge graph** — already exists in our system (125 concepts, Apache AGE). Future: auto-populate from exported content.

### Why Server-Side Export > Client-Side API Sync

| Factor | Client-side (API calls) | Server-side (Rake/endpoint) |
|--------|------------------------|---------------------------|
| API calls | N+1 (one per module item) | 0 (direct DB queries) |
| Auth | Needs API token | Runs on server with DB access |
| HTML→MD conversion | Client must parse HTML | Server can use existing Rails helpers |
| ContentTag resolution | Must follow polymorphic links via API | Can eager-load with `.includes()` |
| Speed | Minutes (dozens of API calls) | Seconds (few DB queries) |
| FERPA filtering | Client must check `published` | Server applies `workflow_state` scope |

---

---

## Two Product Tiers: Extension vs Fork (The Cursor Pattern)

This is the same architectural decision Cursor faced with VS Code. Cursor couldn't build its AI features as just an extension — it needed to fork VS Code and modify the editor itself. We face the same choice:

### Tier 1: Extension Model — Works with ANY Canvas Instance

No fork required. Any instructor at any school can use this today.

| Component | How It Works | Limitation |
|-----------|-------------|-----------|
| CLI wrapper | Calls Canvas REST API externally | N+1 API calls, rate limited |
| Filesystem sync | Client-side: API → local markdown | Stale data between syncs |
| MCP tools (existing) | canvas-mcp talks to any Canvas via API token | 40+ tools = noise problem |
| Knowledge graph | Built from exported content | Must re-export to refresh |

**Who uses this**: Individual instructors, small deployments, schools that won't install custom software. "Just give me a tool I can run against my existing Canvas."

### Tier 2: Fork Model — Requires Our Canvas Fork

Architectural changes to Canvas itself. More powerful, but schools must deploy our fork.

| Component | How It Works | Advantage over Tier 1 |
|-----------|-------------|----------------------|
| Server-side export | Rake task or API endpoint, direct DB queries | No N+1, seconds vs minutes |
| Virtual filesystem controller | Rails serves course content as navigable paths | Always fresh, no sync |
| Extended AI models | Build on existing `AiExperience` / `AiConversation` | Native Canvas integration |
| Content indexing | Server-side embedding pipeline, auto-updates | No client-side infrastructure |
| FERPA enforcement | Server-side scope filtering at query time | Guaranteed, not client-dependent |

**Who uses this**: Schools that deploy our fork (like how schools deploy their own Canvas instances today). "We want AI-native Canvas."

### What Should We Build for Lab 3.2?

**Both.** Start with Tier 1 (CLI + sync) because it's universally usable and demonstrates the concept. Then add the Tier 2 server-side export as a bonus that shows what's possible with the fork. The PR and evidence doc can show both approaches.

This is also good for the course because:
- Tier 1 shows we understand the API and can build client-side tools
- Tier 2 shows we understand the codebase internals and can modify the fork
- The comparison demonstrates architectural thinking about extension vs fork tradeoffs

---

## Sources

- [AgentFS — Turso Database](https://github.com/tursodatabase/agentfs) — SQLite-backed FUSE filesystem for agents
- [AI Agent Interfaces in 2026 — Arize](https://arize.com/blog/agent-interfaces-in-2026-filesystem-vs-api-vs-database-what-actually-works/) — Runtime materialization, interface decoupling
- [Tool-Space Interference — Microsoft Research](https://www.microsoft.com/en-us/research/blog/tool-space-interference-in-the-mcp-era-designing-for-agent-compatibility-at-scale/) — 91-tool MCP = 55K tokens, 85% degradation
- [Why Cursor, Claude Code, Devin Use grep, Not Vectors — MindStudio](https://www.mindstudio.ai/blog/is-rag-dead-what-ai-agents-use-instead) — Filesystem outperforms RAG for structured content
- [Knowledge Graph vs Vector RAG — Neo4j](https://neo4j.com/blog/developer/knowledge-graph-vs-vector-rag/) — 1.5x accuracy, 95% multi-hop
- [GraphRAG Accuracy — FalkorDB](https://www.falkordb.com/blog/graphrag-accuracy-diffbot-falkordb/) — 2x better on complex queries
- [Canvas + OpenAI Partnership — Instructure](https://www.instructure.com/press-release/instructure-and-openai-announce-global-partnership-embed-ai-learning-experiences)
- [CLI vs MCP for AI Agents](https://jannikreinhard.com/2026/02/22/why-cli-tools-are-beating-mcp-for-ai-agents/) — CLI leaves 95% of context window for reasoning
- [ML Mastery Vector vs Graph RAG](https://machinelearningmastery.com/vector-databases-vs-graph-rag-for-agent-memory-when-to-use-which/) — Hybrid consensus, ~35% precision gains
- [Moodle AI Subsystem](https://moodledev.io/docs/4.5/apis/subsystems/ai) — Plugin architecture for LLM providers
