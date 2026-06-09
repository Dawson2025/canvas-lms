#!/usr/bin/env python3
"""Shared building blocks for the Course AI Assistant demos.

Two demos consume this module:

* ``showcase_demo.py``    — a fixed, voice-narrated script (unchanged).
* ``interactive_demo.py`` — a free-form loop where a person *types or speaks* a
  request and an LLM "demo director" turns it into concrete product actions that
  Playwright then performs live, narrated by voice.

Everything here is stdlib + Playwright only (no pip): the same constraint the
agent server (``class_agent_server.py``) holds itself to, so the demo runs
anywhere the agent runs.

Action vocabulary the director emits (and ``run_action`` executes):

    {"type": "goto_course",   "course_id": 2}
    {"type": "open_ai_tab"}                                  # current course
    {"type": "ask_assistant", "question": "What is due this week?"}
    {"type": "show_page",     "page": "assignments"}         # syllabus|modules|
                                                             # announcements|home|
                                                             # ai_assistant|<path>
    {"type": "say",           "text": "..."}                 # narration only

A plan is ``{"narration": "<spoken intro>", "actions": [ ...actions... ]}``.
Each action may also carry its own short ``"narration"``.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request

# --------------------------------------------------------------------------- #
# config (env-overridable, same knobs as config.py where they overlap)
# --------------------------------------------------------------------------- #
BASE = os.environ.get("BASE_URL", "http://canvas.docker").rstrip("/")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@canvas.docker")
PW = os.environ.get("ADMIN_PASSWORD", "canvasdev123")
AGENT_BASE = os.environ.get("AGENT_BASE", "http://127.0.0.1:8742").rstrip("/")
SPEAK = os.environ.get("SPEAK", "1") == "1"
PAUSE = float(os.environ.get("PAUSE", "1.2"))
DIRECTOR_MODEL = os.environ.get("DIRECTOR_MODEL_ID", "meta-llama/llama-3.3-70b-instruct")
DIRECTOR_TIMEOUT = int(os.environ.get("DIRECTOR_TIMEOUT", "45"))

C, Y, G, R, M = "\033[1;36m", "\033[1;33m", "\033[1;32m", "\033[0m", "\033[1;35m"

# Whisper.cpp hallucinates these on near-silence — drop them (see memory:
# feedback_whisper_hallucinations).
_STT_HALLUCINATIONS = {
    "thank you.", "thank you", "thanks for watching!", "you", ".", "okay.",
    "bye.", "...", "thank you for watching.",
}


# --------------------------------------------------------------------------- #
# voice I/O (ai-audio voicemode — local Kokoro TTS + Whisper.cpp STT)
# --------------------------------------------------------------------------- #
def speak(text: str | None) -> None:
    """Narrate via local Kokoro TTS. Prints the line either way."""
    if not text:
        return
    print(f"{C}🔊 {text}{R}", flush=True)
    if not SPEAK:
        return
    try:
        subprocess.run(["ai-audio", "voicemode", "say", text], timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:  # narration is best-effort, never fatal
        print(f"(tts skipped: {exc})", flush=True)


def listen_voice(timeout: int = 30) -> str:
    """Capture one spoken utterance via ``ai-audio voicemode listen``.

    Returns the transcript, or "" on silence / hallucination / error.
    """
    try:
        out = subprocess.run(["ai-audio", "voicemode", "listen"],
                             capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        print(f"(voice input failed: {exc})", flush=True)
        return ""
    # The CLI prints diagnostics on stderr and the transcript on stdout; take the
    # last non-empty stdout line to be safe.
    lines = [ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip()]
    text = lines[-1] if lines else ""
    if text.lower() in _STT_HALLUCINATIONS:
        return ""
    return text


# --------------------------------------------------------------------------- #
# course catalog (asked of the live agent server so the director is accurate)
# --------------------------------------------------------------------------- #
def fetch_courses() -> list[dict]:
    """Return [{course_id, course_code, course_name, ...}] from the agent server.

    Falls back to the two seeded demo courses if the server can't be reached.
    """
    try:
        with urllib.request.urlopen(f"{AGENT_BASE}/courses", timeout=8) as r:
            data = json.load(r)
        if isinstance(data, dict):
            data = data.get("courses", [])
        if data:
            return data
    except Exception:
        pass
    return [
        {"course_id": 1, "course_code": "CSE 290R",
         "course_name": "Special Topics — Applied AI"},
        {"course_id": 2, "course_code": "AI Society", "course_name": "AI Society"},
    ]


def courses_blurb(courses: list[dict]) -> str:
    return "\n".join(
        f"  - course_id {c['course_id']}: {c.get('course_code','')} — "
        f"{c.get('course_name','')}"
        for c in courses
    )


# --------------------------------------------------------------------------- #
# the demo director (OpenRouter — request -> JSON action plan)
# --------------------------------------------------------------------------- #
def _openrouter_key() -> str | None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    env = os.path.expanduser("~/.config/secrets/openrouter.env")
    try:
        with open(env) as fh:
            for line in fh:
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


_DIRECTOR_SYS = """You direct a LIVE product demo of the "Course AI Assistant" — a \
one-button AI assistant that an instructor enables on any Canvas course. Once on, \
students get a course-navigation tab with an AI assistant grounded ONLY in that \
course's published content (syllabus, assignments, modules, announcements). It is \
course-agnostic: the SAME assistant works for ANY class, scoped by course_id.

You translate a person's free-form request into a short JSON plan of concrete \
demo actions that Playwright will perform in a real browser, narrated aloud.

Seeded demo courses:
%(courses)s

Current course_id: %(current)s

Allowed actions (emit only these "type" values):
  {"type":"goto_course","course_id":<int>}      navigate to that course
  {"type":"open_ai_tab"}                          click the Course AI Assistant nav tab
  {"type":"ask_assistant","question":"<text>"}    type a question INTO the product's
                                                  assistant and show its grounded answer
  {"type":"show_page","page":"<p>"}               open a Canvas page so the viewer SEES it.
                                                  p in: home|assignments|syllabus|modules|
                                                  announcements|ai_assistant  (or a raw
                                                  /courses/<id>/... path)
  {"type":"say","text":"<text>"}                  narration only, no browser action

Rules:
- If the person asks the assistant a QUESTION (what's due, the late policy, what is
  this course about, an out-of-scope question), use ask_assistant — that is the product.
- If they want to SEE/SHOW/OPEN course content itself, use show_page (open_ai_tab first
  is unnecessary for show_page).
- To demonstrate on a different course, emit goto_course first.
- Keep plans tight: 1-4 actions. Add a brief per-action "narration" when it helps.
- Respond with ONE JSON object only: {"narration":"<spoken intro>","actions":[...]}.
  No markdown, no prose outside the JSON."""


def director_plan(request: str, courses: list[dict], current_course_id: int) -> dict:
    """Turn a free-form request into an action plan.

    Tries OpenRouter first; falls back to a deterministic keyword router so the
    demo still works offline.
    """
    key = _openrouter_key()
    if key:
        sys = _DIRECTOR_SYS % {
            "courses": courses_blurb(courses), "current": current_course_id}
        body = json.dumps({
            "model": DIRECTOR_MODEL, "max_tokens": 500, "temperature": 0.2,
            "messages": [{"role": "system", "content": sys},
                         {"role": "user", "content": request}],
        }).encode()
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions", data=body,
                headers={"Authorization": f"Bearer {key}",
                         "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=DIRECTOR_TIMEOUT) as r:
                d = json.load(r)
            raw = d["choices"][0]["message"]["content"].strip()
            plan = _extract_json(raw)
            if plan and isinstance(plan.get("actions"), list):
                return plan
        except Exception as exc:
            print(f"{Y}(director LLM unavailable, using keyword router: {exc}){R}",
                  flush=True)
    return _keyword_plan(request, courses, current_course_id)


def _extract_json(raw: str) -> dict | None:
    """Pull the first {...} object out of an LLM reply (handles ```json fences)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def _keyword_plan(request: str, courses: list[dict], current: int) -> dict:
    """Deterministic fallback router (no network)."""
    q = request.lower()
    # course detection by name/code substring
    target = current
    for c in courses:
        name = f"{c.get('course_code','')} {c.get('course_name','')}".lower()
        toks = [t for t in re.split(r"[^a-z0-9]+", name) if len(t) > 2]
        if any(t in q for t in toks) or re.search(rf"\b{c['course_id']}\b", q):
            target = int(c["course_id"])
            break
    if "society" in q:
        target = 2
    actions: list[dict] = []
    if target != current:
        actions.append({"type": "goto_course", "course_id": target})
    show = any(w in q for w in ("show", "open", "see", "go to", "take me", "display"))
    if show and any(w in q for w in ("assignment", "due", "homework")):
        actions.append({"type": "show_page", "page": "assignments",
                        "narration": "Here are the real assignments in this course."})
    elif show and any(w in q for w in ("syllabus", "policy", "late", "grading", "weight")):
        actions.append({"type": "show_page", "page": "syllabus",
                        "narration": "This is the course syllabus the assistant is grounded in."})
    elif show and "module" in q:
        actions.append({"type": "show_page", "page": "modules"})
    elif show and "announce" in q:
        actions.append({"type": "show_page", "page": "announcements"})
    elif show and any(w in q for w in ("assistant", "tab", "ai page", "the ai", "the bot")):
        actions.append({"type": "open_ai_tab",
                        "narration": "And here is the one-button Course AI Assistant tab."})
    else:
        # default: route the request to the product's own assistant
        actions.append({"type": "ask_assistant", "question": request})
    return {"narration": "", "actions": actions}


# --------------------------------------------------------------------------- #
# Playwright driving (login, navigate, ask the embedded assistant)
# --------------------------------------------------------------------------- #
def _ms(sec: float) -> int:
    return int(sec * 1000)


def login(page) -> None:
    page.goto(f"{BASE}/login/canvas")
    if "/login" not in page.url:
        return
    page.fill("#pseudonym_session_unique_id", EMAIL)
    page.fill("#pseudonym_session_password", PW)
    try:
        page.click("#login_form input[type='submit'][value='Log In']", timeout=8000)
    except Exception:
        page.press("#pseudonym_session_password", "Enter")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(_ms(1.0))


def goto_course(page, course_id: int) -> None:
    page.goto(f"{BASE}/courses/{course_id}")
    page.wait_for_timeout(1200)


_PAGE_PATHS = {
    "home": "", "assignments": "/assignments", "syllabus": "/assignments/syllabus",
    "modules": "/modules", "announcements": "/announcements",
    "ai_assistant": "/ai_assistant", "ai": "/ai_assistant",
}


def show_page(page, course_id: int, which: str) -> None:
    which = (which or "home").strip()
    if which.startswith("/"):
        page.goto(f"{BASE}{which}")
    else:
        suffix = _PAGE_PATHS.get(which.lower(), f"/{which.lstrip('/')}")
        page.goto(f"{BASE}/courses/{course_id}{suffix}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)


def open_ai_tab(page, course_id: int):
    """Click the native Course AI Assistant nav tab (fallback to direct URL)."""
    try:
        page.click("#section-tabs a#course-ai-assistant-link", timeout=8000)
    except Exception:
        page.goto(f"{BASE}/courses/{course_id}/ai_assistant")
    page.wait_for_timeout(2000)
    frame = page.frame_locator("iframe[title='Course AI Assistant']")
    frame.locator("#cq").wait_for(state="visible", timeout=30000)
    return frame


def assistant_frame(page):
    return page.frame_locator("iframe[title='Course AI Assistant']")


def ask_assistant(page, course_id: int, question: str) -> str:
    """Ensure the assistant tab is open, ask, and return the grounded answer.

    Waits past the "reading the course…" placeholder for the real answer.
    """
    # Make sure the assistant iframe is present; open the tab if not.
    frame = assistant_frame(page)
    try:
        frame.locator("#cq").wait_for(state="visible", timeout=2500)
    except Exception:
        frame = open_ai_tab(page, course_id)

    before = _safe_count(frame.locator(".msg.bot"))
    inp = frame.locator("#cq")
    inp.wait_for(state="visible", timeout=30000)
    inp.fill(question)
    try:
        frame.locator("#cform button").click(timeout=5000)
    except Exception:
        inp.press("Enter")

    deadline = time.time() + 90
    last, stable, ans = "", 0, ""
    while time.time() < deadline:
        if _safe_count(frame.locator(".msg.bot")) > before:
            try:
                cur = frame.locator(".msg.bot").last.inner_text().strip()
            except Exception:
                cur = ""
            placeholder = (not cur) or ("reading" in cur.lower()) or cur.endswith("…")
            if not placeholder and cur == last:
                stable += 1
                if stable >= 2:
                    ans = cur
                    break
            else:
                stable = 0
            last = cur
        page.wait_for_timeout(700)
    return ans or last or "(no answer captured)"


def _safe_count(loc) -> int:
    try:
        return loc.count()
    except Exception:
        return 0


# --------------------------------------------------------------------------- #
# execute one action; return the (possibly updated) current course id
# --------------------------------------------------------------------------- #
def run_action(page, action: dict, current_course_id: int) -> int:
    t = action.get("type")
    note = action.get("narration")
    if t == "goto_course":
        cid = int(action.get("course_id", current_course_id))
        if note:
            speak(note)
        goto_course(page, cid)
        page.wait_for_timeout(_ms(PAUSE))
        return cid
    if t == "open_ai_tab":
        if note:
            speak(note)
        open_ai_tab(page, current_course_id)
        page.wait_for_timeout(_ms(PAUSE))
        return current_course_id
    if t == "show_page":
        if note:
            speak(note)
        show_page(page, current_course_id, action.get("page", "home"))
        page.wait_for_timeout(_ms(PAUSE))
        return current_course_id
    if t == "ask_assistant":
        q = action.get("question", "")
        print(f"\n  {Y}Asked:{R} {q}", flush=True)
        ans = ask_assistant(page, current_course_id, q)
        print(f"  {G}Assistant:{R} {ans}", flush=True)
        speak(note or _spoken_summary(ans))
        page.wait_for_timeout(_ms(PAUSE))
        return current_course_id
    if t == "say":
        speak(action.get("text") or note)
        return current_course_id
    print(f"{Y}(unknown action skipped: {action}){R}", flush=True)
    return current_course_id


def _spoken_summary(answer: str, limit: int = 320) -> str:
    """Trim a long assistant answer to a sentence or two for narration."""
    a = " ".join((answer or "").split())
    if len(a) <= limit:
        return a
    cut = a[:limit]
    dot = cut.rfind(". ")
    return (cut[: dot + 1] if dot > 60 else cut) + " …"
