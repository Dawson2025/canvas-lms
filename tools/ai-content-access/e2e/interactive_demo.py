#!/usr/bin/env python3
"""Headed, voice-narrated demo of the Course AI Assistant in TWO phases.

Phase 1 — SCRIPTED showcase (an "AI-driven demo like before"): logs in and walks
a fixed sequence across two courses, narrating each step.

Phase 2 — INTERACTIVE: hands the wheel to a person. They TYPE or SPEAK a free-form
request ("what's due this week in the AI Society course", "show me the syllabus",
"ask it who won the super bowl") and an LLM "demo director" (OpenRouter) turns it
into concrete product actions that Playwright performs LIVE in the same browser,
narrated by voice. Grounded answers come from the real product; navigation shows
real Canvas pages. The browser is left OPEN at the end for hands-on use.

Run (headed, voice on, typed input):
    DISPLAY=:0 SPEAK=1 python3 interactive_demo.py

Voice input too (mic via ai-audio voicemode listen):
    DISPLAY=:0 SPEAK=1 VOICE_IN=1 python3 interactive_demo.py

Skip the scripted intro and go straight to interactive:
    DISPLAY=:0 SCRIPTED=0 python3 interactive_demo.py

Env knobs: BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, AGENT_BASE, SPEAK, VOICE_IN,
SCRIPTED, SLOW_MO, PAUSE, DIRECTOR_MODEL_ID, CLOSE_ON_EXIT, KEEP_OPEN_SECONDS.
"""
from __future__ import annotations

import os
import time

from playwright.sync_api import sync_playwright

import demo_lib as D

SLOW = int(os.environ.get("SLOW_MO", "500"))
SCRIPTED = os.environ.get("SCRIPTED", "1") == "1"
VOICE_IN = os.environ.get("VOICE_IN", "0") == "1"
CLOSE_ON_EXIT = os.environ.get("CLOSE_ON_EXIT", "0") == "1"
KEEP_OPEN = int(os.environ.get("KEEP_OPEN_SECONDS", "7200"))

QUIT_WORDS = {"quit", "exit", "q", "stop", "done", "that's all", "thats all",
              "no thanks", "nothing", "goodbye", "bye"}
HELP_WORDS = {"help", "?", "examples", "what can i ask"}

EXAMPLES = [
    "What is this course about?",
    "What's due this week in the AI Society course?",
    "Show me the assignments",
    "Show me the syllabus",
    "What's the late policy and how is grading weighted?",
    "Ask it who won the 2026 Super Bowl   (watch it decline — out of scope)",
    "Switch to the Applied AI course and ask what's due this week",
]

# Phase-1 scripted sequence: (course_id, spoken intro, [(question, comment), ...])
SCRIPT = [
    (1, "Here is the Course A I Assistant we built for C S E 290 R. It is a one "
        "button A I assistant for a class, and it works for any course. Let me "
        "open the Applied A I course and click its Course A I Assistant tab.",
     [
        ("What is this course about?",
         "It reads the real published course content to answer."),
        ("What is due this week?",
         "Those are the actual upcoming assignments, with real due dates."),
        ("Who won the 2026 Super Bowl?",
         "And it correctly declines, because that is outside the course."),
     ]),
    (2, "Now the key part: the exact same assistant on a completely different "
        "course, the A I Society. This is what makes it work for any class.",
     [
        ("What is this course about?",
         "Different course, different grounded answer, same one button."),
        ("What is the attendance policy?",
         "Grounded only in this course's own content."),
     ]),
]


def banner(text: str) -> None:
    print(f"\n{D.M}{'='*70}\n{text}\n{'='*70}{D.R}", flush=True)


def run_scripted(page) -> int:
    current = 1
    for cid, intro, questions in SCRIPT:
        D.speak(intro)
        current = cid
        D.goto_course(page, cid)
        D.open_ai_tab(page, cid)
        for q, comment in questions:
            D.speak("Let me ask it: " + q)
            print(f"\n  {D.Y}Asked:{D.R} {q}", flush=True)
            ans = D.ask_assistant(page, cid, q)
            print(f"  {D.G}Assistant:{D.R} {ans}", flush=True)
            D.speak(comment)
            page.wait_for_timeout(int(D.PAUSE * 1000))
    return current


def read_request() -> str:
    """Get the next request — spoken (VOICE_IN) or typed. '' means skip/retry."""
    if VOICE_IN:
        print(f"\n{D.M}🎤 Speak your request (say 'quit' to finish)…{D.R}", flush=True)
        D.speak("What would you like me to show you?")
        return D.listen_voice(timeout=40)
    try:
        return input(f"\n{D.M}You ▸ {D.R}").strip()
    except (EOFError, KeyboardInterrupt):
        return "quit"


def interactive_loop(page, courses, current_course_id: int) -> None:
    banner("INTERACTIVE DEMO — ask the assistant anything, or ask me to SHOW you "
           "things in the product. Type 'help' for examples, 'quit' to finish.")
    D.speak("Now it is your turn. You can ask the assistant a question, or ask me "
            "to show you something in the product, and I will do it live.")
    print(f"{D.Y}Try:{D.R}")
    for ex in EXAMPLES:
        print(f"  • {ex}")

    current = current_course_id
    while True:
        req = read_request()
        if not req:
            continue
        low = req.lower().strip(" .!?")
        if low in QUIT_WORDS:
            break
        if low in HELP_WORDS:
            print(f"{D.Y}Examples:{D.R}")
            for ex in EXAMPLES:
                print(f"  • {ex}")
            continue
        print(f"{D.C}↳ directing: {req}{D.R}", flush=True)
        plan = D.director_plan(req, courses, current)
        if plan.get("narration"):
            D.speak(plan["narration"])
        for action in plan.get("actions", []):
            current = D.run_action(page, action, current)


def main() -> None:
    courses = D.fetch_courses()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=SLOW,
                                    args=["--start-maximized"])
        ctx = browser.new_context(no_viewport=True, ignore_https_errors=True)
        page = ctx.new_page()

        D.speak("First, I will log into Canvas as the instructor.")
        D.login(page)

        current = 1
        if SCRIPTED:
            current = run_scripted(page)
        else:
            D.goto_course(page, current)
            D.open_ai_tab(page, current)

        interactive_loop(page, courses, current)

        D.speak("That is the Course A I Assistant. I will leave it open so you "
                "can keep trying it yourself.")
        D.goto_course(page, current)
        try:
            D.open_ai_tab(page, current)
        except Exception:
            pass
        banner("DEMO COMPLETE — browser left OPEN. Try it yourself! "
               "(Ctrl-C here to close.)")
        if CLOSE_ON_EXIT:
            browser.close()
            return
        try:
            time.sleep(KEEP_OPEN)
        except KeyboardInterrupt:
            pass
        browser.close()


if __name__ == "__main__":
    main()
