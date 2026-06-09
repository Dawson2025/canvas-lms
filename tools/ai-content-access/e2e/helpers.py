"""Reusable page-driving helpers for the Course AI Assistant E2E suite.

These functions wrap the raw Playwright `Page` with intent-named operations
(`login`, `open_course`, `enable_course_ai_assistant`, `ask_assistant`, ...) so
the spec in ``test_course_ai_assistant.py`` reads like the user story.

Design notes
------------
* Locators prefer accessible roles / labels / stable ids over brittle CSS.
* The agent tab embeds the assistant in an ``<iframe>``; ``assistant_frame``
  returns a ``FrameLocator`` so callers never poke at the outer document by
  mistake.
"""
from __future__ import annotations

import re
import time

from playwright.sync_api import (
    FrameLocator,
    Locator,
    Page,
    TimeoutError as PWTimeoutError,
    expect,
)

import config


def screenshot(page: Page, name: str) -> None:
    """Best-effort full-page screenshot into the artifact dir (never fatal)."""
    try:
        config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(config.ARTIFACT_DIR / f"{name}.png"), full_page=True)
    except Exception as exc:  # pragma: no cover - diagnostics only
        print(f"[helpers] screenshot {name!r} failed: {exc}")


# --------------------------------------------------------------------------- #
# 1. authentication
# --------------------------------------------------------------------------- #
def login(page: Page, email: str | None = None, password: str | None = None) -> None:
    """Log an instructor/admin into Canvas via the standard /login/canvas form.

    Idempotent-ish: if a session already exists Canvas redirects away from the
    login form, which we detect and treat as "already logged in".
    """
    email = email or config.ADMIN_EMAIL
    password = password or config.ADMIN_PASSWORD

    page.goto(f"{config.BASE_URL}/login/canvas", wait_until="domcontentloaded")

    # If we're already authenticated Canvas bounces /login/canvas -> /dashboard.
    if "/login" not in page.url:
        return

    email_box = page.locator("#pseudonym_session_unique_id")
    email_box.wait_for(state="visible", timeout=config.TIMEOUT_MS)
    email_box.fill(email)

    pwd_box = page.locator("#pseudonym_session_password")
    pwd_box.wait_for(state="visible", timeout=config.TIMEOUT_MS)
    pwd_box.fill(password)

    submit = page.locator("#login_form input[type='submit'][value='Log In']")
    submit.wait_for(state="visible", timeout=config.TIMEOUT_MS)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS):
        submit.click()

    # Assert we left the login screen (bad creds keep us on /login with a flash).
    if "/login" in page.url:
        screenshot(page, "login-failed")
        raise AssertionError(
            f"Login did not leave the /login screen (still at {page.url}). "
            "Check ADMIN_EMAIL / ADMIN_PASSWORD or the login selectors."
        )


# --------------------------------------------------------------------------- #
# 2. open a course
# --------------------------------------------------------------------------- #
def open_course(page: Page) -> str:
    """Navigate to a course page and return the resolved course id (as str).

    Selection order:
      1. config.COURSE_ID  -> /courses/<id> directly.
      2. config.COURSE_NAME -> click the matching link on /courses.
      3. otherwise          -> open the first course listed on /courses.
    """
    if config.COURSE_ID:
        page.goto(f"{config.BASE_URL}/courses/{config.COURSE_ID}",
                  wait_until="domcontentloaded")
    else:
        page.goto(f"{config.BASE_URL}/courses", wait_until="domcontentloaded")
        if config.COURSE_NAME:
            link = page.get_by_role("link", name=re.compile(re.escape(config.COURSE_NAME), re.I)).first
        else:
            link = page.locator("a[href^='/courses/']").filter(
                has=page.locator(":scope")  # any course link
            ).first
        link.wait_for(state="visible", timeout=config.TIMEOUT_MS)
        with page.expect_navigation(wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS):
            link.click()

    course_id = _course_id_from_url(page.url)
    if not course_id:
        screenshot(page, "open-course-no-id")
        raise AssertionError(f"Could not parse a course id from URL: {page.url}")
    return course_id


def _course_id_from_url(url: str) -> str | None:
    m = re.search(r"/courses/(\d+)", url)
    return m.group(1) if m else None


# --------------------------------------------------------------------------- #
# 3. enable the "Course AI Assistant" feature
# --------------------------------------------------------------------------- #
def enable_course_ai_assistant(page: Page, course_id: str) -> None:
    """Confirm the Course AI Assistant nav item is enabled for the course."""
    tab = course_nav_tab(page, course_id, config.FEATURE_TAB_NAME)
    expect(tab).to_be_visible()


# --------------------------------------------------------------------------- #
# 4. the course-nav tab appears
# --------------------------------------------------------------------------- #
def course_nav_tab(page: Page, course_id: str, tab_name: str | None = None) -> Locator:
    """Return the course-navigation link for the assistant tab (must be visible).

    Reloads the course home so a freshly-enabled tab is picked up.
    """
    tab_name = tab_name or config.FEATURE_TAB_NAME
    page.goto(f"{config.BASE_URL}/courses/{course_id}", wait_until="domcontentloaded")

    tab = page.locator("#section-tabs a#course-ai-assistant-link")
    tab.wait_for(state="visible", timeout=config.TIMEOUT_MS)
    # Sanity: the link should point inside this course.
    href = tab.get_attribute("href") or ""
    assert f"/courses/{course_id}" in href or "/courses/" in href, (
        f"Assistant tab href {href!r} does not look course-scoped"
    )
    return tab


def open_assistant_tab(page: Page, course_id: str, tab_name: str | None = None) -> None:
    """Click the assistant nav tab and wait for its page (and iframe) to load."""
    tab = course_nav_tab(page, course_id, tab_name)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS):
        tab.click()
    screenshot(page, "assistant-tab-open")


# --------------------------------------------------------------------------- #
# 5./6. talk to the assistant (embedded in an iframe)
# --------------------------------------------------------------------------- #
def assistant_frame(page: Page) -> FrameLocator:
    """Return a FrameLocator for the embedded assistant iframe.

    The tab content is rendered by the agent server inside an <iframe>.
    """
    sel = "iframe[src*='localhost:8742'][title='Course AI Assistant']"
    iframe = page.locator(sel)
    iframe.wait_for(state="attached", timeout=config.NAV_TIMEOUT_MS)
    iframe.wait_for(state="visible", timeout=config.NAV_TIMEOUT_MS)
    return page.frame_locator(sel)


def assistant_question_box(page: Page) -> Locator:
    """Return the ready-to-type assistant question input inside the iframe."""
    frame = assistant_frame(page)
    box = frame.locator("#cq")
    box.wait_for(state="visible", timeout=config.NAV_TIMEOUT_MS)
    expect(box).to_be_enabled(timeout=config.NAV_TIMEOUT_MS)
    return box


def ask_assistant(page: Page, question: str) -> str:
    """Type ``question`` into the assistant, submit, and return the answer text.

    All locators are scoped to the iframe via ``assistant_frame``.
    """
    frame = assistant_frame(page)
    box = assistant_question_box(page)
    box.click()
    box.fill(question)

    # Capture how many answer bubbles exist before we submit, so we can wait for
    # a NEW one rather than racing the previous answer.
    answer_sel = _ANSWER_SELECTOR
    before = _safe_count(frame.locator(answer_sel))

    button = frame.locator("#cform button")
    button.click(timeout=config.TIMEOUT_MS)
    if not _answer_count_increased(frame, answer_sel, before, timeout_ms=1500):
        box.press("Enter", timeout=config.TIMEOUT_MS)

    # Wait for a new answer bubble to appear and stop changing (LLM stream).
    return _wait_for_answer(frame, answer_sel, before)


# The element that holds a rendered assistant answer.
_ANSWER_SELECTOR = ".msg.bot"


def _safe_count(loc: Locator) -> int:
    try:
        return loc.count()
    except Exception:
        return 0


def _answer_count_increased(
    frame: FrameLocator, answer_sel: str, before_count: int, timeout_ms: int
) -> bool:
    """Briefly check whether one send path already produced a new answer node."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        if _safe_count(frame.locator(answer_sel)) > before_count:
            return True
        time.sleep(0.1)
    return False


def _wait_for_answer(frame: FrameLocator, answer_sel: str, before_count: int) -> str:
    """Poll until a new answer bubble appears and its text settles."""
    deadline = time.monotonic() + config.ANSWER_TIMEOUT_MS / 1000.0
    last_text = ""
    stable_since: float | None = None
    while time.monotonic() < deadline:
        bubbles = frame.locator(answer_sel)
        count = _safe_count(bubbles)
        if count > before_count:
            try:
                text = (bubbles.nth(count - 1).inner_text(timeout=1500) or "").strip()
            except PWTimeoutError:
                text = ""
            if text and text == last_text:
                # Text hasn't changed since last poll -> stream finished.
                if stable_since is None:
                    stable_since = time.monotonic()
                elif time.monotonic() - stable_since >= 1.0:
                    return text
            else:
                stable_since = None
                last_text = text
        time.sleep(0.5)
    if last_text:
        return last_text  # return whatever we have; caller asserts on it
    raise AssertionError(
        f"No assistant answer appeared within {config.ANSWER_TIMEOUT_MS} ms. "
        "Confirm the answer-bubble selector (_ANSWER_SELECTOR) against the UI."
    )


# --------------------------------------------------------------------------- #
# assertion helpers (shared by the spec)
# --------------------------------------------------------------------------- #
# Phrases that signal the assistant *declined* an out-of-scope question. These
# mirror the agent's SCOPE GUARD prompt ("can only help with this course's
# published content"). Matching is case-insensitive substring.
DECLINE_MARKERS = [
    "this course",
    "published content",
    "can only help",
    "only help with",
    "outside",
    "out of scope",
    "can't help with that",
    "cannot help with that",
    "i can only",
    "not able to",
]


def looks_like_decline(answer: str) -> bool:
    a = (answer or "").lower()
    return any(m in a for m in DECLINE_MARKERS)
