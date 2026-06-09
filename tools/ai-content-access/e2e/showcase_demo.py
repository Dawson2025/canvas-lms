#!/usr/bin/env python3
"""Headed, VOICE-NARRATED showcase of the Course AI Assistant.

Logs into Canvas as the instructor, then walks TWO courses (CSE 290R + AI
Society), opening the native Course AI Assistant tab and asking a sequence of
questions in each. A presenter voice (ai-audio voicemode say / local Kokoro)
narrates each step like a human demo. Leaves the browser OPEN at the end.

Run:  DISPLAY=:0 SLOW_MO=600 SPEAK=1 python3 showcase_demo.py
"""
import os, time, subprocess
from playwright.sync_api import sync_playwright

BASE  = os.environ.get("BASE_URL", "http://canvas.docker")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@canvas.docker")
PW    = os.environ.get("ADMIN_PASSWORD", "canvasdev123")
SLOW  = int(os.environ.get("SLOW_MO", "600"))
PAUSE = float(os.environ.get("PAUSE", "1.4"))
SPEAK = os.environ.get("SPEAK", "1") == "1"

C, Y, G, R = "\033[1;36m", "\033[1;33m", "\033[1;32m", "\033[0m"

def speak(text):
    if not text:
        return
    print(f"{C}🔊 {text}{R}", flush=True)
    if not SPEAK:
        return
    try:
        subprocess.run(["ai-audio", "voicemode", "say", text], timeout=90,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"(tts skipped: {e})", flush=True)

def ms(sec):
    return int(sec * 1000)

def ask(page, frame, q, comment=None):
    print(f"\n  {Y}Student:{R} {q}", flush=True)
    before = frame.locator(".msg.bot").count()
    inp = frame.locator("#cq")
    inp.wait_for(state="visible", timeout=30000)
    inp.fill(q)
    try:
        frame.locator("#cform button").click(timeout=5000)
    except Exception:
        inp.press("Enter")
    # Wait for a NEW bubble, then for its text to become a real answer
    # (not the "reading…" placeholder) and stabilize across two reads.
    deadline = time.time() + 90
    last, stable, ans = "", 0, ""
    while time.time() < deadline:
        if frame.locator(".msg.bot").count() > before:
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
    ans = ans or last or "(no answer captured)"
    print(f"  {G}Assistant:{R} {ans}", flush=True)
    speak(comment)
    page.wait_for_timeout(ms(PAUSE))

COURSES = [
    (1, "the Applied A I course",
        "Let me open the Applied A I course and click the Course A I Assistant tab in the course navigation.",
     [
        ("What is this course about?", "It reads the real published course content to answer."),
        ("What is due this week?", "Those are the actual upcoming assignments, with real due dates."),
        ("What is the late policy, and how is grading weighted?", "That came straight from the syllabus."),
        ("Who won the 2026 Super Bowl?", "And it correctly declines, because that is outside the course."),
     ]),
    (2, "the A I Society course",
        "Now here is the key part. The exact same assistant, on a completely different course, the A I Society. This is what makes it work for any class.",
     [
        ("What is this course about?", "Different course, different grounded answer, same one button."),
        ("What is due this week?", None),
        ("What is the attendance policy?", "Again, grounded only in this course's own content."),
     ]),
]

with sync_playwright() as p:
    speak("Here is the Course A I Assistant we built for C S E 290 R. It is a one button A I assistant for a class, and it works for any course. Let me show you.")
    browser = p.chromium.launch(headless=False, slow_mo=SLOW, args=["--start-maximized"])
    ctx = browser.new_context(no_viewport=True, ignore_https_errors=True)
    page = ctx.new_page()

    speak("First, I will log into Canvas as the instructor.")
    page.goto(f"{BASE}/login/canvas")
    page.fill("#pseudonym_session_unique_id", EMAIL)
    page.fill("#pseudonym_session_password", PW)
    try:
        page.click("#login_form input[type='submit'][value='Log In']", timeout=8000)
    except Exception:
        page.press("#pseudonym_session_password", "Enter")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(ms(1.2))

    for cid, cname, intro, questions in COURSES:
        speak(intro)
        page.goto(f"{BASE}/courses/{cid}")
        page.wait_for_timeout(1500)
        try:
            page.click("#section-tabs a#course-ai-assistant-link", timeout=10000)
        except Exception:
            page.goto(f"{BASE}/courses/{cid}/ai_assistant")
        page.wait_for_timeout(2200)
        frame = page.frame_locator("iframe[title='Course AI Assistant']")
        frame.locator("#cq").wait_for(state="visible", timeout=30000)
        for q, comment in questions:
            speak("Let me ask it: " + q)
            ask(page, frame, q, comment)

    speak("That is the same one button assistant, grounded in two different courses' real data. I will leave it open so you can try it yourself.")
    page.goto(f"{BASE}/courses/1/ai_assistant")
    page.wait_for_timeout(1500)
    print(f"\n{G}### DEMO COMPLETE — browser left OPEN on the CSE 290R Course AI Assistant. Try it yourself!{R}", flush=True)
    try:
        time.sleep(7200)  # keep the browser alive ~2h for hands-on use
    except KeyboardInterrupt:
        pass
    browser.close()
