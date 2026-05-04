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

1. **Build `canvas` CLI** — thin wrapper around Canvas REST API with subcommands
2. **Implement `canvas sync`** — exports course content to filesystem
3. **The filesystem IS the content directory** — agent reads with general tools
4. **Knowledge graph** — already exists in our system (125 concepts, Apache AGE)

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
