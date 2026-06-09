# Course AI Assistant — Playwright E2E suite

End-to-end tests for the Canvas **"Course AI Assistant"** feature: an instructor
opens a per-course AI assistant tab in course navigation, and the assistant
(embedded via an `<iframe>`) answers questions **grounded in that
course's published content** while declining out-of-scope questions.

The agent itself is the grounded, FERPA-safe class-agent in
`../class_agent_server.py` (answers only from the `ai_course_*` views). These
tests drive the **browser UI**, not the SQL views directly.

## The flow under test

1. Instructor logs into Canvas.
2. Opens a course.
3. Confirms the "Course AI Assistant" tab appears in course navigation.
5. Opens the tab (assistant embedded in an iframe → tests use `frame_locator`).
6. Asks **"what is due this week?"** → asserts a grounded, non-empty,
   course-specific answer.
7. Asks an out-of-scope question → asserts a polite decline (and that no real
   answer leaks).

## Files

| File | Purpose |
|------|---------|
| `test_course_ai_assistant.py` | The spec. One ordered story test (`test_full_course_ai_assistant_journey`) + granular `test_step_*` tests. |
| `helpers.py` | Intent-named page-driving helpers: `login`, `open_course`, `enable_course_ai_assistant`, `course_nav_tab`, `assistant_frame`, `ask_assistant`, using confirmed live selectors. |
| `conftest.py` | Pytest fixtures: `browser` (global Chromium), `context` (tracing + video + cert tolerance), `page`, `instructor_page` (pre-logged-in). |
| `config.py` | All env-var parameterization with defaults. Run `python3 config.py` to print the resolved config. |
| `pytest.ini` | Marker registration + defaults; keeps the dir self-contained. |
| `run_e2e.sh` | Headless CI runner. Prints PASS/FAIL, appends a line to the report log, writes JUnit XML. |
| `demo_headed.sh` | HEADED live demo (`DISPLAY=:0`, slow motion). |
| `systemd/` | User timer + service to run `run_e2e.sh` on a schedule; `install_timer.sh` installer; `crontab.example` as a cron alternative. |

## Prerequisites

- A local Canvas reachable at `BASE_URL` (default `http://canvas.docker`).
- The **global Playwright (Python)** at `~/.local/bin` (used as `python3 -m
  pytest` with the `playwright` package). Chromium must be installed:
  ```bash
  ~/.local/bin/playwright install chromium
  ```

## Configuration (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `BASE_URL` | `http://canvas.docker` | Canvas root URL. |
| `ADMIN_EMAIL` | `admin@canvas.docker` | Instructor/admin login. |
| `ADMIN_PASSWORD` | `canvasdev123` | Instructor/admin password. |
| `E2E_COURSE_ID` | *(auto: first course)* | Open this course directly. |
| `E2E_COURSE_NAME` | *(unset)* | Match a course by name on `/courses`. |
| `E2E_FEATURE_TAB_NAME` | `Course AI Assistant` | Exact nav-tab label. |
| `E2E_HEADLESS` | `1` | `0` for a visible browser. |
| `E2E_SLOW_MO` | `0` | ms between actions (demo uses 250). |
| `E2E_ANSWER_TIMEOUT_MS` | `60000` | How long to wait for an LLM answer. |
| `E2E_ARTIFACT_DIR` | `./artifacts` | Screenshots / video / traces. |
| `E2E_REPORT_LOG` | `./reports/e2e_report.log` | PASS/FAIL history (run_e2e.sh). |

Print what would be used:
```bash
python3 config.py
```

## Running

Headless (CI):
```bash
./run_e2e.sh
# or select one test:
./run_e2e.sh -k test_step_6_in_scope_answer_is_grounded
```

Headed live demo:
```bash
./demo_headed.sh                 # ordered story test, slow, visible
DISPLAY=:0 E2E_SLOW_MO=400 ./demo_headed.sh -k journey
```

Directly with pytest:
```bash
BASE_URL=http://canvas.docker python3 -m pytest -v -m e2e
```

## Scheduling (systemd user timer)

```bash
./systemd/install_timer.sh          # install + enable + start (hourly at :17)
./systemd/install_timer.sh --status # next runs + last result
./systemd/install_timer.sh --remove # uninstall
# optional, so it runs while logged out:
loginctl enable-linger "$USER"
```

Each run appends one tab-separated line to `reports/e2e_report.log`:
```
2026-06-09T14:17:03Z   PASS   exit=0   BASE_URL=http://canvas.docker   junit=.../artifacts/junit-...xml
```

Cron alternative: see `systemd/crontab.example`.

## Confirmed selectors

- `helpers.login` — `#pseudonym_session_unique_id`,
  `#pseudonym_session_password`, and
  `#login_form input[type='submit'][value='Log In']`.
- `helpers.course_nav_tab` — `#section-tabs a#course-ai-assistant-link`.
- `helpers.assistant_frame` —
  `iframe[src*='localhost:8742'][title='Course AI Assistant']`.
- `helpers.ask_assistant` — input `#cq`, send `#cform button`, answer
  bubble `.msg.bot`.

## Artifacts & debugging

- Screenshots at key steps and on failure → `artifacts/*.png`.
- Per-test video → `artifacts/video/`.
- On a failing test a Playwright trace is saved → `artifacts/trace-<test>.zip`.
  Open it with:
  ```bash
  ~/.local/bin/playwright show-trace artifacts/trace-<test>.zip
  ```

## What the assertions actually check

- **Step 6 (grounded):** answer is non-empty, ≥15 chars, is **not** a decline,
  is **not** generic greeting boilerplate, and either references a
  course-specific token (course code / title word / id) or uses concrete
  due-date language (`due`, `assignment`, `this week`, `nothing is due`, …).
- **Step 7 (decline):** answer matches the agent's scope-guard phrasing
  (`this course`, `published content`, `can only help`, …) and contains no
  sports-score-like `NN–NN` pattern (no real out-of-scope answer leaked).

These bars are deliberately robust to LLM phrasing variance — they reject
non-answers and scope violations without pinning exact wording.

## Scope / safety

This suite lives entirely under `e2e/` and **does not modify any Canvas Rails
files**. It only drives the browser and reads/writes its own artifacts and
report log.
