# Course AI Platform — CSE 290R Feature-1

A **course-agnostic, one-button "Course AI Assistant"** for Canvas. An instructor
clicks **✨ Enable AI Assistant** on any course; students then get an AI assistant
— as a native Canvas course-navigation tab — that answers their questions
**grounded only in that course's published content** (syllabus, modules, pages,
assignments, announcements). It is FERPA-safe by construction and works for *any*
course in the Canvas database, selected purely by `course_id`.

This is the CSE 290R "Course AI Platform" feature (Feature-1), built on a fork of
Canvas LMS (`feature/course-ai-assistant`, HEAD `6c1764b7`).

---

## 1. What it is + the one-button instructor flow

The platform turns "give my students an AI helper for this class" into a single
click, with no per-course configuration:

1. **Instructor opens their course** in Canvas (instructor view).
2. On the course home, they see an **✨ AI Assistant** card with one button:
   *"Add an AI assistant that answers your students' questions using only this
   course's published content — syllabus, modules, assignments, announcements.
   One click. No setup."*
3. They click **✨ Enable AI Assistant**. A provisioning overlay animates the real
   steps — reading the manifest, ingesting the syllabus + pages, loading
   assignments/modules, grounding the assistant FERPA-safe, and adding the menu
   item — then `POST /enable` flips the course on and warms its grounding context
   (`build_course_context(..., force=True)`).
4. From then on, **students see a `✨ Course AI Assistant` item in the course
   navigation** (and a banner on the home page: *"Your instructor added an AI
   Assistant."*). Opening it drops them into a grounded chat for that course.

The same button, the same code, the same backend works on a different course
(e.g. CSE 290R vs. AI Society) and produces a *different* grounded assistant —
that course-agnosticism is the whole point.

There are two embodiments of the assistant in this repo, sharing one backend:

- **Native Canvas tab** (the product): a real Rails course-nav tab,
  feature-flagged, that iframes the agent scoped to the course.
- **Canvas-skinned standalone SPA** (the backend's own page at `/`): a
  self-contained demo UI with a global rail, course nav, instructor/student role
  toggle, and the same enable flow — useful for demos without booting Rails.

---

## 2. Architecture (in prose) + exact file map

The data flows **published Canvas tables → FERPA-filtered SQL views → grounded
agent backend → native Canvas course tab (iframe) → (future) other channels**.

```
   Canvas Postgres (real tables: assignments, wiki_pages, context_modules,
   discussion_topics, courses, attachments, content_tags)
            │
            │   create_ai_views.sql  — 8 views, published/active only,
            │                          HTML→markdown via strip_html_tags()
            ▼
   ai_course_* views  (assignments / pages / modules / announcements /
            │          syllabus / files / content / manifest)
            ▼
   class_agent_server.py  (stdlib HTTP server on :8742)
            │   reads ONLY the ai_course_* views (build_course_context + SYS_PROMPT)
            │   routes: /courses  /state  /enable  /ask
            │   pluggable LLM (_call_llm): OpenRouter → Anthropic → OpenAI-compat → claude CLI
            ▼
   Native Canvas course tab   ── OR ──   standalone Canvas-skinned SPA (the same server's "/")
   (Rails: course.rb tab insert,                ?course_id=<id>&embed=1
    routes.rb, controller, show.html.erb,
    feature flag) iframes the agent at
    localhost:8742/?course_id=<id>&embed=1
            ▼
   (future channels: Discord DM bot, QR-code entry points — spec'd, not built)
```

**File map** (paths under `canvas-lms/`):

| Layer | File | What it does |
|-------|------|--------------|
| SQL views | `tools/ai-content-access/create_ai_views.sql` | 8 FERPA-filtered views over real Canvas tables + `strip_html_tags()` PL/pgSQL function (HTML→markdown-ish). Published/active only. |
| Agent backend | `tools/ai-content-access/class_agent_server.py` | Pure-stdlib `ThreadingHTTPServer` (bind `127.0.0.1`, `PORT` env, default 8742). Routes `/courses`, `/state`, `/enable`, `/ask`. Grounding + scope guard + pluggable LLM. Also serves the standalone Canvas-skinned SPA at `/`. |
| Native tab — model | `app/models/course.rb` (`TAB_AI_ASSISTANT = 26`, ~line 3493; feature-gated tab insert ~line 3734; re-insert before Settings ~line 3814) | Adds the `Course AI Assistant` tab to course nav when the feature flag is on, positioned just before Settings. |
| Native tab — routes | `config/routes.rb` (`get "courses/:course_id/ai_assistant" => "course_ai_assistant#show"`, ~line 1295; nested `get "ai_assistant"` ~line 595) | Maps the course-scoped URL to the controller. |
| Native tab — controller | `app/controllers/course_ai_assistant_controller.rb` | `require_context` + `check_feature_flag` (404 if off) + `authorized_action(:read)`. An `after_action` (`allow_local_agent_frame_src`) relaxes the CSP `frame-src` to allow the `localhost`/`127.0.0.1` agent iframe. Agent base URL is `ENV["COURSE_AI_AGENT_URL"]` or `http://localhost:8742`. |
| Native tab — view | `app/views/course_ai_assistant/show.html.erb` | Iframes the agent at `<agent_base_url>/?course_id=<@context.id>&embed=1` (full-height, `clipboard-write`, `referrerpolicy="no-referrer"`). |
| Feature flag | `config/feature_flags/course_ai_assistant_flags.yml` | `course_ai_assistant`, `applies_to: Course`, default `state: hidden`; `development` and `ci` environments are `allowed_on`. `touch_context: true`. |
| Dev seed | `tools/ai-content-access/seed_dev_course.rb` | Idempotent `rails runner` seed of two real courses (CSE 290R "Special Topics — Applied AI" + AI Society) with syllabus + published assignments + a teacher + a student. |
| E2E suite | `tools/ai-content-access/e2e/` | Playwright/pytest browser tests, runner, headed demo, voice-narrated showcase, systemd timer. |

The agent is **course-agnostic**: every query is keyed by `course_id`, which is
int-coerced (`cid()` → `int(course_id)`) before it ever touches SQL, so the
course selector cannot inject SQL. The SPA reads `?course_id` to auto-scope to one
course and `?embed=1` to hide its own chrome (global rail / course nav / top bar)
so it sits cleanly inside the Canvas iframe.

---

## 3. Run Track A locally (the primary track)

Track A boots the **full Canvas fork** in Docker, runs the agent against the
docker Postgres, and serves the native tab on real courses.

> Note on timing: the canvas-lms docs estimate a 2.5–4 hr first boot; on this
> workstation the stack actually came up in **~9 minutes**.

**a. Boot Canvas in Docker** (from the `canvas-lms/` repo root). The
`docker-compose.hostports.yml` override publishes the web app on
`127.0.0.1:80` and Postgres on `127.0.0.1:5433` (→ container `5432`) so the agent
can reach the DB from the host:

```bash
cd /home/dawson/dawson-workspace/code/canvas-lms
docker compose -f docker-compose.yml -f docker-compose.hostports.yml up -d
```

Canvas comes up at **http://canvas.docker** — log in as
`admin@canvas.docker` / `canvasdev123`.

**b. Create the FERPA-safe views** in the `canvas_development` database (run
inside the Postgres container, or from the host against the exposed `5433`):

```bash
# inside the container:
docker compose exec -T postgres psql -U postgres -d canvas_development \
  < tools/ai-content-access/create_ai_views.sql

# …or from the host via the exposed port:
psql -h 127.0.0.1 -p 5433 -U postgres -d canvas_development \
  -f tools/ai-content-access/create_ai_views.sql
```

**c. Seed two real courses** (idempotent — safe to re-run):

```bash
docker compose exec -T web bundle exec rails runner \
  tools/ai-content-access/seed_dev_course.rb
# prints: SEED_OK teacher=… student=… cse290r=<id> aisociety=<id>
```

**d. Start the agent backend** against `canvas_development` via the exposed
Postgres port. The server defaults to DB `cse290r_ai_demo` and port `8742`, so
point `DEMO_DB` and `PGHOST/PGPORT` at the docker DB:

```bash
DEMO_DB=canvas_development PGHOST=127.0.0.1 PGPORT=5433 PGUSER=postgres \
  python3 tools/ai-content-access/class_agent_server.py
# → Course AI Platform on http://localhost:8742  (DB=canvas_development)
```

The standalone SPA is now at **http://localhost:8742/**. For the native tab,
the Rails controller iframes it (default `http://localhost:8742`; override with
`COURSE_AI_AGENT_URL`).

**e. Enable the feature flag** on the courses. In `development` the flag is
`allowed_on`, so an instructor can turn it on per course from the course's
**Feature Options**, or you can flip it from the console:

```bash
docker compose exec -T web bundle exec rails runner \
  'Course.find(1).enable_feature!(:course_ai_assistant)'
```

Then open `http://canvas.docker/courses/1` → click the **✨ Course AI Assistant**
tab → ask away. The tab is live on both seeded courses.

**LLM backend:** the agent picks its backend from env, in order — set one:
`OPENROUTER_API_KEY` (OpenRouter, default model `meta-llama/llama-3.3-70b-instruct`),
`ANTHROPIC_API_KEY` (Anthropic Messages), `LLM_API_BASE`+`LLM_API_KEY` (any
OpenAI-compatible endpoint), or none → the local `claude` CLI. The deterministic
behaviors (due-this-week, scope guard) work even with no LLM configured.

---

## 4. How Track B (AWS) is deployed

Track B is an **always-on, public deployment of the lightweight agent** (not the
full Canvas stack) so the assistant is reachable without a local boot:

- **Host:** an EC2 `t3.large` (2 vCPU / 7.6 GB) at
  **http://98.86.181.215:8742**.
- **Service:** `class_agent_server.py` runs under a systemd unit
  (`courseai.service`), so it survives reboots and restarts on failure.
- **Data:** real course data **snapshotted from the local `canvas_development`
  database** and loaded into the AWS host's Postgres, so the public agent answers
  from the same FERPA-safe `ai_course_*` views.
- **Caveat:** this is the agent backend only — there is no full Canvas LMS on
  AWS. (The AWS Learner Lab session is ephemeral, which is exactly why Track A on
  the workstation is the primary track.)

---

## 5. The three functional behaviors + course-agnosticism + FERPA grounding

The agent has **three first-class behaviors**, all grounded in the `ai_course_*`
views:

1. **Deterministic "due this week."** Questions like *"what's due this week?"* /
   *"is there anything due?"* route through `_due_window_intent()` → a SQL window
   `due_at BETWEEN now() AND now() + interval '7 days'` (`_due_next_7_days`),
   returning real assignment titles + due dates — computed in SQL, not guessed by
   the LLM. (The keyword fallback `_rule_answer` has the same window.)
2. **Syllabus / grading-policy lookup.** Questions about late policy, grading
   weights, etc. pull the relevant sentence(s) out of `ai_course_syllabus`
   (`_sentence_for`), falling back to `ai_course_pages`.
3. **Hard out-of-scope decline (defense-in-depth, 3 layers).**
   (a) A deterministic guard (`_out_of_scope`) runs **before any LLM call** —
   strong off-course markers (sports scores, weather, "what's my grade", *another*
   course's code, etc.) are declined immediately;
   (b) the same guard also runs inside the keyword fallback;
   (c) the `SYS_PROMPT` instructs the grounded LLM to decline anything outside the
   course's published content. A course's *own* code never counts as out-of-scope.

**Course-agnosticism.** Nothing is hard-coded to a course. `/courses` lists every
course in `ai_course_manifest`; `/state`, `/enable`, and `/ask` all take a
`course_id`; the grounding context is rebuilt per course. The same binary answers
CSE 290R and AI Society differently because it reads each course's own views.

**FERPA grounding.** The eight views in `create_ai_views.sql` only ever expose
**published/active** content (`workflow_state = 'published'/'active'`,
`file_state = 'available'`, `courses.workflow_state = 'available'`). There is no
view over grades, submissions, or roster PII. The assistant therefore *cannot*
surface a student's private record or unpublished/draft material — it literally
has no SQL path to it. HTML is converted to readable markdown by
`strip_html_tags()` before it ever reaches the model.

---

## 6. Testing & demo

- **SQL view tests — 26/26 pass.** `test_ai_views.sql` + `test_edge_cases.sql`
  validate the views and `strip_html_tags()` against seeded data (publication
  filtering, HTML stripping, entity decoding, edge cases).
- **Playwright E2E — 7/7 pass.** Under `tools/ai-content-access/e2e/`:

  ```bash
  cd /home/dawson/dawson-workspace/code/canvas-lms/tools/ai-content-access/e2e
  ./run_e2e.sh                 # headless CI run; prints PASS/FAIL, writes JUnit XML + report log
  ./run_e2e.sh -k step_6       # select one test
  ./demo_headed.sh             # headed, slow-motion live run (DISPLAY=:0)
  ```

  The suite is one ordered story test
  (`test_full_course_ai_assistant_journey`) plus granular `test_step_1..7`
  checks: instructor logs in → opens a course → enabling makes the tab appear →
  the tab embeds the agent iframe → an in-scope question gets a **grounded**
  answer → an out-of-scope question is **declined** (no leaked answer). The
  assertions are robust to LLM phrasing variance (reject non-answers and scope
  violations without pinning exact wording). Confirmed live selectors:
  `#section-tabs a#course-ai-assistant-link`,
  `iframe[title='Course AI Assistant']`, chat input `#cq`, send `#cform button`,
  answer bubble `.msg.bot`.
- **Voice-narrated showcase.** `e2e/showcase_demo.py` logs in, walks **two
  courses** (CSE 290R then AI Society), opens the native tab on each, and asks a
  scripted sequence (about / due-this-week / policy / an out-of-scope Super Bowl
  question), with a presenter voice narrating each step via
  `ai-audio voicemode say`. It leaves the browser **open** for hands-on use:

  ```bash
  DISPLAY=:0 SLOW_MO=600 SPEAK=1 python3 e2e/showcase_demo.py
  ```
- **Scheduled regression.** A systemd **user timer** (`canvas-ai-e2e.timer`,
  hourly at :17, `Persistent=true`) runs `run_e2e.sh` and appends a PASS/FAIL line
  to `reports/e2e_report.log`. Install with `e2e/systemd/install_timer.sh`
  (`--status` / `--remove`); a `crontab.example` is provided as an alternative.

---

## 7. Known gaps

- **The out-of-scope guard is a denylist.** `_out_of_scope` fires on an explicit
  set of off-course patterns plus *other* course codes; it is deliberately
  conservative so it never refuses a legitimate course question. It is a UX/cost
  optimization, **not a safety boundary** — the real safety boundary is the
  grounding (the grounded LLM still declines anything not in the views). An
  unusual off-course phrasing the denylist misses will reach the LLM, which then
  declines it.
- **Track B is the lightweight agent, not full Canvas on AWS.** The public host
  runs only the agent backend against a snapshot of `canvas_development`; there is
  no Canvas LMS on AWS, and the Learner Lab session is ephemeral.
- **Other Feature-1 channels aren't built.** The Feature-1 spec includes a
  **Discord DM bot** and **QR-code** entry points for the same grounded
  assistant; only the native Canvas tab (and standalone SPA) are implemented.
- **Seed content is partial.** The two demo courses have **syllabus + assignments**
  seeded; their **modules, pages, and announcements counts are 0**, so behaviors
  that lean on those (e.g. module outlines) have nothing to return for the seeded
  courses until richer content is added.

---

## Provenance

- **Fork / branch:** `github.com/Dawson2025/canvas-lms`, branch
  `feature/course-ai-assistant`, HEAD `6c1764b7`.
- **Key commits:** `cec44713` (OpenRouter backend + 3 student FRs +
  `ai_course_*` real-schema view fix + dev seed + Playwright E2E) ·
  `10d0ea8c` (native course-nav tab + CSP allow for the agent iframe) ·
  `bfece894` (deterministic due-this-week 7-day window + stronger grounded
  decline + SPA embed auto-scope) · `a295532d` (live E2E selectors 7/7) ·
  `05e1bf48` (clean `embed=1` in native tab + robust E2E journey) ·
  `9bbaa6f6` (voice-narrated showcase demo) · `6c1764b7` (local-dev port
  override: web `127.0.0.1:80`, postgres `127.0.0.1:5433`).
- **Entity:** `short_cse_290r_course_ai_platform`
  (`entity_id 9c34a9a4-2866-4b55-bdc2-ff01b4fc9543`), a Pattern-4 child-by-reference
  of the CSE 290R class entity (`6ab9fed2-1379-46f0-976d-0d09b7466b2b`), at
  `layer_1/layer_1_projects/short_cse_290r_course_ai_platform/` with all 11
  stages. Registered in CSE 290R's `children_registry.json` (school submodule,
  commit `d9b6b82a1`) with a breadcrumb in `launchpad_cse_290r/CHILDREN.md`. Root
  entity commit `1380a8960e` + session handoff `01bbf0b718`.

### How it was built (orchestration notes)

The feature was assembled largely via **8 background Codex agents**
(`codex exec -C <repo> -s workspace-write --add-dir /tmp/agent_handoffs`):
native-tab, backend-QA, aws-provision, aws-deploy, e2e, e2e-robust, and
entity-scaffold — plus an earlier Claude Workflow for backend hardening,
research, Playwright authoring, and entity drafts. Two coordination patterns:
**orchestrator-commits** (the agent writes files + a handoff doc; the orchestrator
does the `git commit`) and **composite PID + handoff completion watchers**
(`kill -0 <pid>` OR a handoff file → fast DONE/FAILED, never a silent timeout).

Lessons that shaped the build:

1. **Codex's `workspace-write` sandbox kills background processes when its session
   exits** — so long-running services (the agent, the headed demo) must be started
   by the orchestrator, not the agent.
2. The **entity-scaffold agent reused the `entity_id` as a registry
   `resource_id`**, which the duplicate-UUID pre-commit hook caught; the fix was to
   *remove* the offending field (not to blind-skip the hook).
3. The **full Canvas boot was ~9 min** on the workstation (not the documented
   2.5–4 hr), and the stack **survived a host suspend/resume cleanly**.
