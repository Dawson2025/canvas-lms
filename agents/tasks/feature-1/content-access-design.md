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

## Part 8: Schema Context Eliminates Speculation

### The Key Insight: Schema Knowledge = Deterministic Queries

An agent with the Canvas schema in its context doesn't guess — it composes the exact right query on the first try, the same way a developer who's read the schema docs would. The "speculative querying" problem only exists when the agent doesn't know the schema.

```
Without schema context:
  "Where's the late policy?"
  → Try assignments table? → 0 results
  → Try wiki_pages? → 0 results
  → Try syllabus_body? → found it! (3 round-trips, 2 wasted)

With schema context (agent knows the table map):
  "Where's the late policy?"
  → Schema says: policies are in courses.syllabus_body or wiki_pages.body
  → Query: SELECT syllabus_body FROM courses WHERE id = 407700
  → Found it. (1 query, 0 waste)
```

This means the three components of the system are:

1. **Schema context** (~100 lines of markdown) — loaded into agent context, teaches it WHERE content lives. Eliminates speculation entirely. The agent knows `assignments.description` has assignment content, `wiki_pages.body` has page content, `courses.syllabus_body` has the syllabus, and `content_tags` is the polymorphic join for modules.

2. **HTML→markdown converter** — a function or CLI tool that strips Canvas HTML noise (inline styles, nested divs, CSS classes) and returns clean markdown. Can be a Rails helper, a Python script, or `pandoc`. Makes content READABLE for the agent instead of wasting tokens on CSS.

3. **Index/manifest** (optional but valuable) — adds semantic summaries and keywords on TOP of schema knowledge. Schema tells the agent which TABLE to query; the manifest tells it which specific ITEM matches the user's question without fetching content. This is an optimization, not a requirement.

### With vs Without the Manifest

| Scenario | Schema Only | Schema + Manifest |
|----------|------------|-------------------|
| "What's the late policy?" | Knows to check syllabus_body + wiki_pages → 1-2 queries | Manifest says "syllabus.md — contains late work policy" → 1 fetch |
| "What's due this week?" | `SELECT title, due_at FROM assignments WHERE context_id=407700 AND due_at BETWEEN...` → 1 query | Same query — manifest doesn't help here, schema is sufficient |
| "What did we learn about recursion?" | `SELECT body FROM wiki_pages WHERE context_id=407700 AND body ILIKE '%recursion%'` → 1 query, but scans all pages | Manifest says "Module 3 covers recursion" → fetch only Module 3 content |
| "Prerequisites for Module 7?" | `SELECT prerequisites FROM context_modules WHERE context_id=407700 AND name ILIKE '%7%'` → 1 query | Same — schema is sufficient for structural queries |

**Bottom line**: Schema context alone handles 80% of queries deterministically. The manifest adds value for semantic matching ("which content is ABOUT this topic?") where keyword search might miss.

---

## Part 9: Fork Model — PostgreSQL Extensions on the Existing Database

### Canvas Already Runs PostgreSQL

This is the critical architectural advantage. Canvas's database is already PostgreSQL. Adding AI capabilities means enabling extensions on the SAME database — not deploying new infrastructure:

```sql
-- Enable on existing Canvas PostgreSQL instance:
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS age;        -- Apache AGE for knowledge graph

-- Add embedding column to existing content tables:
ALTER TABLE wiki_pages ADD COLUMN IF NOT EXISTS embedding vector(384);
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS embedding vector(384);
ALTER TABLE discussion_topics ADD COLUMN IF NOT EXISTS embedding vector(384);

-- Create knowledge graph on same database:
SELECT create_graph('course_knowledge');
```

### What Each Extension Adds

| Extension | What It Enables | Query Example |
|-----------|----------------|---------------|
| **pgvector** | Semantic search — "find content LIKE this query" | `SELECT title FROM wiki_pages ORDER BY embedding <=> query_vec LIMIT 5` |
| **Apache AGE** | Knowledge graph — prerequisites, concept deps, learning paths | `MATCH (m:Module)-[:PREREQUISITE]->(p) WHERE m.name='Week 7' RETURN p` |

### The Three-Layer Architecture (Fork)

```
Canvas PostgreSQL (already running — zero new infrastructure)
│
├── Layer 1: Relational tables (EXISTING)
│   ├── courses, assignments, wiki_pages, content_tags, etc.
│   ├── Agent queries these directly with schema knowledge
│   └── Always fresh, always authoritative
│
├── Layer 2: pgvector embeddings (ADD EXTENSION + COLUMNS)
│   ├── embedding vector(384) on content tables
│   ├── Auto-embed on content save (Rails after_save callback)
│   ├── Semantic search for "find content about X"
│   └── Complements schema-based queries (keyword search) with meaning-based search
│
├── Layer 3: Apache AGE knowledge graph (ADD EXTENSION + GRAPH)
│   ├── Nodes: modules, concepts, assignments, learning objectives
│   ├── Edges: prerequisite, contains, teaches, relates_to
│   ├── Auto-populate from ContextModule.prerequisites (Canvas metadata)
│   ├── Agent-proposed concept relationships (instructor approves)
│   └── Multi-hop traversal: "What do I need to know before Week 7?"
│
└── Utility: html_to_markdown() function (ADD FUNCTION)
    ├── Strips Canvas HTML noise → clean markdown
    ├── Called on read, not on write (content stays as HTML in DB)
    └── Agent receives clean markdown, not HTML blobs
```

### Why This Is Better Than Separate Infrastructure

| Factor | Separate DB (new pgvector + AGE instance) | Same Canvas PostgreSQL |
|--------|-------------------------------------------|----------------------|
| Deployment | New server, new backups, new ops | Already running |
| Data freshness | Must sync from Canvas DB | IS the Canvas DB |
| Schema duplication | Must mirror Canvas schema | Uses the actual tables |
| Auth/access | Separate credentials | Same DB credentials |
| Backup/restore | Separate process | Included in Canvas backups |
| Cost | Additional server | $0 (extensions are free) |

### What the Agent Sees (Fork Model)

The agent gets schema context that includes ALL three layers:

```markdown
## Canvas Course Content — Agent Schema Context

### Layer 1: Direct queries (relational)
- Assignments: SELECT title, description, due_at FROM assignments WHERE context_id = ?
- Pages: SELECT title, body FROM wiki_pages JOIN wikis ON ... WHERE context_id = ?
- Modules: SELECT name, prerequisites FROM context_modules WHERE context_id = ?
- Module items: SELECT content_type, content_id FROM content_tags WHERE context_module_id = ?

### Layer 2: Semantic search (pgvector)
- Similar content: SELECT title FROM wiki_pages ORDER BY embedding <=> ? LIMIT 5
- Cross-content search: UNION across assignments + wiki_pages + discussions

### Layer 3: Knowledge graph (AGE)
- Prerequisites: MATCH (m)-[:PREREQUISITE]->(p) RETURN p.name
- Concept chain: MATCH path = (start)-[:TEACHES|PREREQUISITE*]->(end) RETURN path
- Learning path: MATCH (c:Concept)<-[:TEACHES]-(m:Module) RETURN m ORDER BY m.position

### Utility
- Clean content: SELECT html_to_markdown(description) FROM assignments WHERE id = ?
```

The agent picks the right layer based on the query type:
- Structural query ("what's due?") → Layer 1 (relational)
- Semantic query ("content about memory systems") → Layer 2 (pgvector)
- Traversal query ("prerequisites for Week 7?") → Layer 3 (AGE)

No speculation. The schema context tells it exactly which layer and which query pattern to use.

### Pre-Made Views: Encode Complexity Once, Query Simply Forever

Instead of the agent composing JOINs and filters every time, pre-made PostgreSQL views encode the correct logic once. The agent just reads from them:

```sql
-- ============================================================
-- VIEWS FOR AI AGENT ACCESS (created once on fork deployment)
-- ============================================================

-- All published assignments for a course, FERPA-safe, clean format
CREATE VIEW ai_course_assignments AS
SELECT a.id, a.title,
       html_to_markdown(a.description) AS description_md,
       a.due_at, a.lock_at, a.unlock_at,
       a.points_possible, a.grading_type, a.submission_types,
       a.context_id AS course_id
FROM assignments a
WHERE a.workflow_state = 'published'
  AND a.context_type = 'Course';

-- All published pages
CREATE VIEW ai_course_pages AS
SELECT wp.id, wp.title, wp.url,
       html_to_markdown(wp.body) AS body_md,
       w.context_id AS course_id
FROM wiki_pages wp
JOIN wikis w ON wp.wiki_id = w.id
WHERE wp.workflow_state = 'active'
  AND w.context_type = 'Course';

-- Module structure with items resolved
CREATE VIEW ai_course_modules AS
SELECT cm.id AS module_id, cm.name AS module_name, cm.position,
       cm.prerequisites, cm.completion_requirements,
       ct.position AS item_position, ct.title AS item_title,
       ct.content_type, ct.content_id, ct.url AS external_url,
       cm.context_id AS course_id
FROM context_modules cm
LEFT JOIN content_tags ct ON ct.context_module_id = cm.id
  AND ct.workflow_state = 'active'
WHERE cm.workflow_state = 'active'
  AND cm.context_type = 'Course'
ORDER BY cm.position, ct.position;

-- Announcements (recent first)
CREATE VIEW ai_course_announcements AS
SELECT dt.id, dt.title,
       html_to_markdown(dt.message) AS message_md,
       dt.posted_at, dt.context_id AS course_id
FROM discussion_topics dt
WHERE dt.type = 'Announcement'
  AND dt.workflow_state = 'active'
  AND dt.context_type = 'Course'
ORDER BY dt.posted_at DESC;

-- Course syllabus
CREATE VIEW ai_course_syllabus AS
SELECT c.id AS course_id, c.name,
       html_to_markdown(c.syllabus_body) AS syllabus_md
FROM courses c
WHERE c.workflow_state = 'available';

-- Unified content search (all content types, one view)
CREATE VIEW ai_course_content AS
SELECT course_id, 'assignment' AS content_type, id AS content_id,
       title, description_md AS content_md, due_at
FROM ai_course_assignments
UNION ALL
SELECT course_id, 'page', id, title, body_md, NULL
FROM ai_course_pages
UNION ALL
SELECT course_id, 'announcement', id, title, message_md, posted_at
FROM ai_course_announcements;
```

Now the agent's context document is drastically simpler:

```markdown
## How to query course content

| What you need | Query |
|--------------|-------|
| All assignments with dates | `SELECT title, due_at, points_possible, description_md FROM ai_course_assignments WHERE course_id = ?` |
| Assignments due this week | `SELECT * FROM ai_course_assignments WHERE course_id = ? AND due_at BETWEEN NOW() AND NOW() + interval '7 days'` |
| Module structure | `SELECT module_name, item_title, content_type FROM ai_course_modules WHERE course_id = ? ORDER BY position, item_position` |
| Search all content | `SELECT content_type, title, content_md FROM ai_course_content WHERE course_id = ? AND content_md ILIKE '%search_term%'` |
| Syllabus | `SELECT syllabus_md FROM ai_course_syllabus WHERE course_id = ?` |
| Recent announcements | `SELECT title, message_md, posted_at FROM ai_course_announcements WHERE course_id = ? LIMIT 5` |
| Page by title | `SELECT body_md FROM ai_course_pages WHERE course_id = ? AND title ILIKE '%query%'` |
| Semantic search | `SELECT title, content_md FROM ai_course_content WHERE course_id = ? ORDER BY embedding <=> ? LIMIT 5` |
```

**What the views encode that the agent doesn't have to think about:**
- FERPA filtering (`workflow_state = 'published'` / `'active'`)
- HTML→markdown conversion (`html_to_markdown()` called in the view)
- Table joins (wiki_pages → wikis → courses, content_tags → context_modules)
- Content type discrimination (`type = 'Announcement'` vs regular discussions)
- Sort order (modules by position, announcements by date)
- The unified `ai_course_content` view searches ALL content types in one query

**The agent's schema context shrinks from ~100 lines of table documentation to ~20 lines of view documentation.** The complexity is in the view definitions (created once), not in the agent's context (loaded every session).

---

## Part 10: Extension Model — API-Only Equivalent Architecture

### The Constraint

No database access. Only the Canvas REST API with an API token. Must replicate the fork model's capabilities client-side.

### Mapping Fork Capabilities to Extension Equivalents

| Fork Model | Extension Equivalent | How |
|-----------|---------------------|-----|
| Pre-made PostgreSQL views | Pre-made CLI subcommands | `canvas-ai assignments --course 407700 --due-this-week` |
| Ad-hoc SQL with schema knowledge | Ad-hoc API calls with endpoint knowledge | Agent composes `curl` calls from endpoint map |
| `html_to_markdown()` in views | Client-side converter (`pandoc`, `html2text`, or Python) | Pipe API HTML output through converter |
| pgvector semantic search | Local embeddings (pgvector on local Postgres, or in-memory) | Embed fetched content locally, search locally |
| Apache AGE knowledge graph | Filesystem DAG with frontmatter pointers | `module.md` with `prerequisites: [...]` |
| FERPA filtering in views | API handles this — only returns published content to students | Already solved |
| Background auto-reindex on save | Re-run sync on schedule or on-demand | `canvas-ai sync --course 407700` |

### Pre-Made CLI Subcommands (Equivalent to Views)

```bash
# These are the "pre-made views" of the extension model.
# Each subcommand knows which endpoint to call, how to paginate,
# and converts HTML → markdown automatically.

canvas-ai assignments --course 407700                    # all published assignments
canvas-ai assignments --course 407700 --due-this-week    # filtered by date
canvas-ai modules --course 407700                        # module structure with items
canvas-ai pages --course 407700                          # all published pages
canvas-ai page --course 407700 --title "syllabus"        # specific page content (markdown)
canvas-ai syllabus --course 407700                       # course syllabus (markdown)
canvas-ai announcements --course 407700 --limit 5        # recent announcements
canvas-ai search --course 407700 --query "late policy"   # search across all content types
canvas-ai manifest --course 407700                       # generate index/manifest
canvas-ai sync --course 407700 --output ./my-course/     # full export to filesystem
```

Each subcommand:
1. Calls the right API endpoint(s)
2. Handles pagination automatically
3. Converts HTML → markdown
4. Outputs clean, agent-readable text

The agent calls these via Bash — single tool, zero context cost for tool definitions.

### Ad-Hoc API Queries (Equivalent to Schema Knowledge)

For the 20% of queries no subcommand covers, the agent needs endpoint knowledge:

```markdown
## Canvas API Endpoint Map (loaded via trigger)

| Content | Endpoint | Key Params |
|---------|---------|-----------|
| Course + syllabus | `GET /courses/:id?include[]=syllabus_body` | `include[]=total_students` |
| Assignments | `GET /courses/:id/assignments` | `order_by=due_at`, `bucket=upcoming` |
| Single assignment | `GET /courses/:id/assignments/:aid` | `include[]=rubric` |
| Modules + items | `GET /courses/:id/modules?include[]=items` | `per_page=100` |
| Pages | `GET /courses/:id/pages` | `search_term=query`, `sort=title` |
| Single page | `GET /courses/:id/pages/:url` | returns `body` (HTML) |
| Discussions | `GET /courses/:id/discussion_topics` | `only_announcements=true` |
| Files | `GET /courses/:id/files` | `sort=name`, `content_types[]=...` |
| Submissions | `GET /courses/:id/assignments/:aid/submissions/self` | `include[]=rubric_assessment` |

All endpoints: paginate with `per_page=100`, follow `Link: <url>; rel="next"` header.
Auth: `Authorization: Bearer $CANVAS_TOKEN`
Base: `$CANVAS_URL/api/v1/`
```

~30 lines. Loaded on demand when the agent needs to compose a custom query.

### Extension Model Limitations (Honest)

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| N+1 API calls for module items | Slow for large courses (1 call per item to get content) | `include[]=items` on modules endpoint gets metadata; fetch content only when needed |
| Rate limiting | Canvas rate limits API calls | Batch fetches, cache results locally |
| No server-side joins | Can't cross-reference in one query | Fetch both datasets, join client-side |
| No semantic search | Can't find "content LIKE this" | Local grep, or build local embedding index |
| Pagination overhead | Max 100 items per request | Auto-paginate in CLI subcommands |
| HTML content | All descriptions/bodies returned as HTML | Auto-convert via `html2text` in CLI |

---

## Part 11: HTML→Markdown Conversion (Both Models)

### Why This Is Essential

Canvas stores ALL content as HTML with inline styles, nested divs, and Canvas-specific CSS. This is what the agent actually receives:

```html
<div style="margin:0;padding:0;font-family:Georgia,'Times New Roman',Times,serif;
font-size:17px;line-height:1.68;color:#0f0e0d;background-color:#ebe6dc;
padding:clamp(12px,3vw,22px);">
<div style="max-width:52rem;margin:0 auto;">
<h2 style="font-family:Georgia;font-size:clamp(1.45rem,2vw+0.9rem,2.1rem);
line-height:1.12;margin:2.25rem 0 0.75rem 0;padding-bottom:0.35rem;
border-bottom:1px solid rgba(15,14,13,0.22);">Instruction 3.1</h2>
<p style="margin:0 0 1.1em 0;">Skim the <span style="font-style:normal;
color:#0f0e0d;">suggested readings</span>...</p>
```

vs what the agent needs:

```markdown
## Instruction 3.1

Skim the **suggested readings**...
```

The HTML version wastes 3-5x more tokens on CSS noise. Multiply across an entire course and you're burning thousands of tokens on inline styles instead of content.

### Implementation

| Model | Where Conversion Happens | Tool |
|-------|------------------------|------|
| **Fork** | Server-side: `html_to_markdown()` PostgreSQL function or Rails helper, called in views | Content arrives pre-converted |
| **Extension** | Client-side: CLI subcommands pipe through converter | `pandoc -f html -t markdown`, `html2text`, or Python `markdownify` |
| **Both** | The conversion strips: inline styles, Canvas CSS classes, `<script>` tags, data attributes, empty divs | Preserves: headings, lists, tables, links, bold/italic, code blocks |

### Conversion Quality Matters

A naive `strip_tags()` loses structure (headings become plain text, tables become run-on text). A good converter preserves semantic structure:

```python
# Bad: strip_tags("&lt;h2>Title&lt;/h2>&lt;ul>&lt;li>Item&lt;/li>&lt;/ul>") → "TitleItem"
# Good: html_to_markdown("&lt;h2>Title&lt;/h2>&lt;ul>&lt;li>Item&lt;/li>&lt;/ul>") → "## Title\n- Item"
```

For the fork, this is a one-time function deployed with the views. For the extension, it's built into the CLI tool.

---

## Part 12: Progressive Disclosure & Trigger Hierarchy (Both Models)

### The Problem Without Progressive Disclosure

Loading ALL course content into context at once wastes the context window:

```
A course with 4 modules × 5 items × ~2000 tokens each = ~40,000 tokens
+ syllabus (~3,000 tokens)
+ announcements (~2,000 tokens)
= ~45,000 tokens BEFORE the agent even starts reasoning
```

At 40% of a 200K window, that's already at budget. And most queries only need 1-2 content items.

### The Solution: Trigger Hierarchy

Same pattern as our entity system — a hierarchy of triggers that routes queries to the right content at the right level of detail, without loading everything.

```
Level 0: Course Manifest (ALWAYS LOADED — ~50 lines)
├── Course name, ID, module count
├── Per-module: name, position, item count, topic keywords
├── "This course has 4 modules covering: context, architecture, memory, QA"
│
├── Trigger: "deadlines/due dates/assignments"
│   └── Load: assignment index (titles + due dates, ~20 lines)
│       └── Trigger: specific assignment asked about
│           └── Fetch: full assignment description (markdown, ~100 lines)
│
├── Trigger: "syllabus/policies/grading/late work"
│   └── Fetch: syllabus (markdown, ~200 lines)
│
├── Trigger: "module structure/prerequisites/what's in week N"
│   └── Load: module index (names + prerequisites + item titles, ~30 lines)
│       └── Trigger: specific module content
│           └── Fetch: individual items in that module
│
├── Trigger: "specific page/reading/instruction"
│   └── Load: page index (titles + URLs, ~15 lines)
│       └── Fetch: specific page content
│
└── Trigger: "announcements/updates"
    └── Fetch: last 5 announcements
```

### How It Works In Practice

```
Student: "What's the late policy?"

Agent reads manifest (already in context, ~50 lines):
  → Matches trigger: "policies/grading/late work" → syllabus
  → Fetches: canvas-ai syllabus --course 407700
  → Reads ~200 lines of markdown
  → Answers from the relevant section

Total context used: ~250 lines (manifest + syllabus)
NOT loaded: assignments, pages, modules, announcements (~40,000 tokens saved)
```

```
Student: "What's due this week?"

Agent reads manifest (already in context):
  → Matches trigger: "deadlines/due dates" → assignment index
  → Fetches: canvas-ai assignments --course 407700 --due-this-week
  → Reads ~10 lines of results
  → Answers with date-sorted list

Total context used: ~60 lines
```

```
Student: "What concepts from Module 2 do I need for Module 4?"

Agent reads manifest (already in context):
  → Matches trigger: "prerequisites/module structure" → module index
  → Fetches: canvas-ai modules --course 407700
  → Reads module index, sees Module 4 prerequisites include Module 2
  → Fetches Module 2 and Module 4 content for concept comparison
  → Answers with specific concept connections

Total context used: ~150 lines (manifest + module index + 2 module contents)
```

### The Manifest IS the Top-Level Trigger Document

For the extension model, the manifest is generated by `canvas-ai manifest --course 407700` and cached locally. For the fork model, it's a PostgreSQL view (`ai_course_manifest`). Either way, it's the ~50 lines that stay in the agent's context and route all queries.

```markdown
# Course Manifest: CSE 290R Applied AI (407700)
# Last indexed: 2026-05-04T22:00:00Z

## Modules (4 published)

| # | Module | Topics | Items | Prerequisites |
|---|--------|--------|-------|---------------|
| 1 | Context & Efficiency | brownfield, greenfield, context window, context management | 8 | none |
| 2 | Architectural State | memory, caching, technical debt, AI state management | 8 | Module 1 |
| 3 | Memory & Implementation | STM/LTM, purging, vector vs graph, agent memory, feature implementation | 7 | Module 2 |
| 4 | Quality Assurance | QA, unit testing, TDD, red-green-refactor | 6 | Module 3 |

## Content Summary

| Type | Count | Fetch Command |
|------|-------|--------------|
| Assignments | 19 | `canvas-ai assignments --course 407700` |
| Pages | 4 | `canvas-ai pages --course 407700` |
| Announcements | ~5 | `canvas-ai announcements --course 407700` |
| Files | varies | `canvas-ai files --course 407700` |
| Syllabus | 1 | `canvas-ai syllabus --course 407700` |

## Query Routing

| Student asks about... | Fetch |
|----------------------|-------|
| Due dates, deadlines, assignments | `canvas-ai assignments --course 407700 --due-this-week` |
| Policies, grading, late work | `canvas-ai syllabus --course 407700` |
| Module content, prerequisites | `canvas-ai modules --course 407700` then specific items |
| Specific page or reading | `canvas-ai page --course 407700 --title "QUERY"` |
| Recent announcements | `canvas-ai announcements --course 407700 --limit 5` |
| Search everything | `canvas-ai search --course 407700 --query "QUERY"` |
```

~50 lines. Loaded once. Routes every query to the right fetch command. The agent never loads content it doesn't need.

### Extension vs Fork: Same Pattern, Different Backend

| Component | Extension Model | Fork Model |
|-----------|----------------|-----------|
| Manifest source | `canvas-ai manifest` CLI (cached JSON) | `SELECT * FROM ai_course_manifest WHERE course_id = ?` |
| Trigger routing | Agent reads manifest, picks fetch command | Agent reads manifest view, picks query |
| Content fetch | CLI subcommand → API → html2text → markdown | `SELECT * FROM ai_course_pages WHERE course_id = ?` (already markdown in view) |
| Second-level triggers | Sub-manifests per module (cached) | Module-specific views |
| Freshness | Re-run `canvas-ai manifest` periodically | View always reflects current DB state |

The progressive disclosure pattern is identical. The backend differs.

---

## Part 13: The Universal Requirement — System Prompt + Progressive Disclosure

### This Is the Same Architecture Regardless of Backend

No matter the model (extension or fork), the course agent needs the same context architecture:

```
┌─────────────────────────────────────────────────────────────┐
│  System Prompt (STATIC — loaded every request)              │
│  ├── Agent identity + role + guardrails                     │
│  ├── Course manifest (~50 lines)                            │
│  │   ├── Module list with topic keywords                    │
│  │   ├── Content type counts                                │
│  │   └── Query routing table (trigger hierarchy)            │
│  └── Fetch instructions (which tool/command to use)         │
│                                                             │
│  Dynamic Context (LOADED ON DEMAND via triggers)            │
│  ├── Level 1: Content indexes (assignment list, page list)  │
│  ├── Level 2: Specific content (one assignment, one page)   │
│  └── Level 3: Deep detail (rubric, discussion replies)      │
└─────────────────────────────────────────────────────────────┘
```

### This Maps Directly to Our Entity System

| Entity System Component | Course Agent Equivalent |
|-------------------------|------------------------|
| `CLAUDE.md` (system prompt) | Course agent system prompt + manifest |
| Triggers table in CLAUDE.md | Query routing table ("deadlines" → fetch assignments) |
| Rule groups (`.0agnostic/02_rules/groups/`) | Content category sub-indexes (assignment index, page index) |
| Individual rules (loaded on demand) | Individual content items (fetched on demand) |
| `.0agnostic/01_knowledge/` (on-demand Read) | Course content fetched via CLI or SQL views |
| Progressive disclosure spectrum | Manifest (~1 line/item) → index (~5 lines/item) → full content (~100 lines) |

### What Gets Built (Both Models)

1. **Course agent system prompt template** — reusable across any course. Contains:
   - Agent identity (role, guardrails, FERPA rules)
   - Slot for course manifest (generated per-course)
   - Fetch instruction set (CLI subcommands or SQL views)
   - Trigger hierarchy template

2. **Manifest generator** — produces the ~50 line course manifest:
   - Extension: `canvas-ai manifest --course 407700`
   - Fork: `SELECT * FROM ai_course_manifest WHERE course_id = 407700`

3. **Content fetcher with HTML→markdown** — retrieves and converts on demand:
   - Extension: CLI subcommands piping through `html2text`
   - Fork: PostgreSQL views with `html_to_markdown()` built in

4. **Trigger hierarchy rules** — routes queries to the right content:
   - Can be generated by the agent orchestrator based on course content analysis
   - Or hand-written as a template that works for most courses

### The Progressive Disclosure Chain for a Course

```
Most compressed ────────────────────────────────────── Most detailed
System prompt      Manifest         Content index      Full content
(agent identity)   (~1 line/item)   (~5 lines/item)    (~100 lines/item)

"CSE 290R has      "Module 3:       "Lab 3.2:          Full assignment
4 modules about    Memory &         Agent Driven       description with
context, arch,     Implementation,  Implementation,    rubric, all
memory, QA"        7 items, prereq: due 5/9, 30 pts,  sections, template
                   Module 2"        online_text_entry"  code, requirements"
```

Agent stops at whatever depth answers the question. "How many modules?" → manifest. "What's Lab 3.2 about?" → content index. "Show me the full Lab 3.2 requirements" → full content.

---

## Part 14: Context Avenue Granularity — Why Multiple Data Avenues Exist

### The Granularity Problem with File-Only Access

File-based progressive disclosure has a **granularity floor** — the smallest unit is a file. If the answer is one field buried in a 200-line page, the agent loads all 200 lines.

```
File-based:                              Data-based:
  "When is Lab 3 due?"                     "When is Lab 3 due?"
  → Load assignments/lab-3.md (100 lines)  → SELECT due_at → "2026-05-09" (1 line)
  → Agent scans for due date               → Exact answer, zero waste
  → 99 lines wasted
```

### Each Data Avenue Has Unique Granularity and Capability

| Data Avenue | Granularity | Unique Capability | Example |
|------------|-------------|-------------------|---------|
| **Relational (SQL)** | Field-level | Exact values, filters, joins, counts, sorting | `SELECT title, due_at WHERE due_at BETWEEN...` |
| **Vector (pgvector)** | Semantic chunk | Find content by MEANING, not just keywords. Handles paraphrasing. | "I'm struggling with the project" → finds "office hours", "study tips", "project FAQ" even without keyword match |
| **Knowledge Graph (AGE)** | Relationship-level | Multi-hop path traversal. Discover indirect connections. | "Do I need Week 2 for the final?" → traverses prerequisite chain across 5 modules |
| **Full-text search (tsvector)** | Keyword occurrence | Ranked keyword matching across large text fields | `WHERE body @@ to_tsquery('academic & honesty')` — faster than ILIKE, supports relevance ranking |
| **File-based (Read/Grep)** | File-level | Full content for deep reading, contextual understanding | "Explain the Lab 3 requirements in detail" — needs the whole description |

### What Each Avenue Finds That Others Miss

```
"What's due Friday?"
  → Relational: SELECT due_at WHERE due_at = '2026-05-09' ✓
  → Vector: can't filter by date ✗
  → Graph: dates aren't relationships ✗
  → Files: would need to grep all assignment files ✗ (slow)

"I'm overwhelmed, any resources to help?"
  → Vector: embedding similarity finds "office hours", "tutoring", "study group" ✓
  → Relational: no keyword match for "overwhelmed" ✗
  → Graph: not a relationship query ✗
  → Files: grep "overwhelmed" → 0 results ✗

"What concepts from Module 2 feed into Module 6?"
  → Graph: MATCH (m2)-[:PREREQUISITE|TEACHES*]->(m6) RETURN path ✓
  → Relational: can get direct prerequisites but not multi-hop chains ✗
  → Vector: can find similar content but not structural paths ✗
  → Files: would need to manually trace frontmatter pointers ✗ (tedious)

"Where exactly does the syllabus mention 'academic honesty'?"
  → Full-text: to_tsquery with position highlighting ✓
  → Relational: ILIKE works but slower, no ranking ○
  → Vector: too broad — returns semantically similar but not exact ✗
  → Files: grep works but no relevance ranking ○
```

### Trigger Hierarchy Routes to the Right Avenue

The agent doesn't decide which avenue to use — the trigger rules encode that:

```
Trigger Hierarchy for Course Agent
│
├── Metadata queries (dates, counts, titles, points)
│   └── Route to: Relational (SQL views)
│   └── Examples: "what's due", "how many assignments", "how many points"
│
├── Semantic queries (topic understanding, recommendations)
│   └── Route to: Vector search (pgvector)
│   └── Examples: "help with", "resources about", "content related to"
│
├── Structural queries (prerequisites, paths, dependencies)
│   └── Route to: Knowledge graph (AGE)
│   └── Examples: "what do I need before", "how does X connect to Y"
│
├── Keyword search (find specific text in content)
│   └── Route to: Full-text search (tsvector) or grep
│   └── Examples: "where does it say", "find the part about"
│
├── Content understanding (explain, summarize, detail)
│   └── Route to: File-based (Read full markdown)
│   └── Examples: "explain the requirements", "summarize module 3"
│
└── Compound queries (metadata + content)
    └── Route to: Relational first (get list), then file-based (get details)
    └── Examples: "what's due this week and what do I need to know about each"
```

### Progressive Complexity for Data Avenues

Not every deployment needs all avenues. The progressive complexity roadmap for data avenues:

```
Level 0: File-only (grep + read)
  → Works immediately, no infrastructure
  → Granularity floor: file-level

Level 1: + Relational queries (SQL/API)
  → Field-level granularity for metadata
  → Extension: API calls. Fork: SQL views.

Level 2: + Full-text search
  → Keyword matching with ranking
  → Extension: API search_term param. Fork: tsvector columns.

Level 3: + Vector search (pgvector)
  → Semantic similarity, handles paraphrasing
  → Extension: local embedding. Fork: pgvector on Canvas DB.

Level 4: + Knowledge graph (AGE)
  → Multi-hop traversal, structural reasoning
  → Extension: filesystem DAG. Fork: AGE on Canvas DB.
```

Each level adds a new granularity capability. Start at Level 0, graduate when the simpler levels demonstrably fail for your queries.

---

## Part 15: Implementation Plan for Lab 3.2

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
