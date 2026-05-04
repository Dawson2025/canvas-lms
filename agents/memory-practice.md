# Memory Technique: 4-Tier Persistent Memory with Progressive Disclosure

## Technique Choice

I built and use a **4-tier persistent memory architecture** across all my AI agent sessions — not a library, but a production system I designed based on the Week 3 readings (IBM 5 memory types, ML Mastery vector vs graph RAG, Titans surprise-based retention, claude-mem progressive disclosure). The system spans short-term context, file-based persistent memory, PostgreSQL with pgvector + Apache AGE, and a UUID-based entity graph.

**Why it fits Canvas work:** Canvas LMS is a brownfield codebase (>2M LOC). No agent can hold the full context. My memory system lets agents selectively load what they need (progressive disclosure), remember what they learned across sessions (persistent file + database memory), and discover relationships between concepts (hybrid vector + graph retrieval).

## Connection to Other Agent Artifacts

This memory practice directly supports:
- **`agents/analyze-repo.md`** — The analysis agent outputs feed into Tier 2 (file-based knowledge docs). When the agent discovers Canvas architecture patterns, those get saved as durable extraction files with UUID frontmatter so future sessions don't re-analyze.
- **`agents/project-creation.md`** — The GitHub Project items are tracked as episodic memory (session records of what was planned, what changed, why). Board state transitions are logged.
- **`agents/tasks/feature-1/`** — Feature research and implementation evidence will reference knowledge graph concepts for the Canvas feature.

## Procedure (How It Changes Agent Workflow)

### Before Each Session
1. **Load compaction instructions** — a file that tells the agent what to preserve vs discard from prior sessions (maps to Titans' surprise signal: high-surprise items are "MUST PRESERVE")
2. **Check session registry** — find the most recent session archive for the working entity
3. **Query knowledge graph** — `query_knowledge.py search "canvas feature"` uses pgvector (384-dim embeddings) to find semantically relevant concepts

### During Work
4. **Save extracted knowledge as durable files** — every source URL read gets saved to `.0agnostic/01_knowledge/*/sources/` with UUID frontmatter. Agents read these files instead of re-fetching URLs.
5. **Track decisions in episodic memory** — session handoff docs capture what was decided and why
6. **Update knowledge graph** — new concepts get YAML definitions → `verify_knowledge_graph.py` → `load_knowledge_graph.py` (auto-syncs Apache AGE graph) → `embed_concepts.py`

### After Each Session
7. **Create session archive** — versioned immutable snapshot of peak knowledge state
8. **Update compaction instructions** — mark what the next session should preserve

### Purge / Refresh / Last Verified

| Tier | Purge Strategy | Refresh Trigger | Last Verified |
|------|---------------|-----------------|---------------|
| Tier 1 (context window) | Strategic compaction with priority tiers | Every session start | 2026-05-05 |
| Tier 2 (file-based) | LRU — track which files agents read, decay unused | On content change | 2026-05-05 |
| Tier 3 (PostgreSQL) | Temporal versioning — mark old edges superseded | On knowledge graph load | 2026-05-05 (116 concepts) |
| Tier 4 (entity graph) | Orphan pruning via entity-health.sh | On entity move/rename | 2026-05-05 (443 entities) |

## Failure Modes and Mitigations

| Failure Mode | Impact | Mitigation |
|-------------|--------|------------|
| **Stale context** — compaction instructions reference concepts that no longer exist | Agent loads outdated knowledge, makes wrong decisions | Session archives are versioned; compaction instructions include "last verified" dates; agents check file existence before loading |
| **Over-retention** — keeping too much in context window | Token budget exhausted, agent loses track of current task | Progressive disclosure: load compact indices first (~50 tokens), fetch details only when needed (~500-1000 tokens). Maps to claude-mem's 3-layer pattern. |
| **Wrong trust boundary** — treating derived data as source of truth | Stale CLAUDE.md content overrides fresh 0AGNOSTIC.md | Clear hierarchy: 0AGNOSTIC.md is source of truth → agnostic-sync.sh generates derived files. Never edit derived files directly. |
| **UUID collision** — duplicate UUIDs across knowledge graph | Silent data overwrite (lost 4 concepts in one incident) | Pre-load duplicate detection guard in loader; `create_concept.sh` tool uses `uuidgen`; pre-commit hook blocks duplicate UUIDs |

## Evidence of Use

### Session Excerpt (2026-05-05 — this session)

**Query**: Semantic search for new memory concepts after adding 12 CSE 290R concepts:
```
$ query_knowledge.py search "memory purging surprise retention"

0.635  Surprise-Based Retention Signal
       From Google's Titans/MIRAS research...
0.628  Memory Purging and Controlled Forgetting
       Deleting, summarizing, down-weighting...
0.529  Forgetting Curve
       Ebbinghaus's empirical model...
```

**Result**: pgvector correctly ranked the two new Week 3 concepts as the top results. The hybrid system works — vector similarity finds semantically related concepts across all courses.

### Knowledge Graph Stats (as of 2026-05-05)
- 116 concepts across 9 courses (CSE 381, CSE 450, DS 460, MATH 341, CSE 290R + 4 placeholders)
- 70 course_teaches edges, 30 concept_relates_to edges
- All 116 concepts embedded (384-dim, All-MiniLM-L6-v2)
- Apache AGE graph synced with Cypher traversal
- 8 source extraction files saved as durable markdown with UUID frontmatter

### Multi-Method Extraction (applied to Canvas course materials)
When extracting CSE 290R readings, I used a fallback chain:
1. WebFetch → worked for Microsoft Learn (with redirect follow)
2. Browser (Claude in Chrome) → worked for IBM, Google Research, Wikipedia, ML Mastery (all returned 403 to WebFetch)
3. `gh` CLI → worked for GitHub README (browser blocked by cookies)
4. WebSearch → last resort for Atlassian QA (page removed, 404)

Result: 8 of 9 sources fully extracted as durable files. Agents can now read these directly without re-fetching.
