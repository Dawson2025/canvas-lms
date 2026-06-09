"""Reusable page-driving helpers for the Course AI Assistant E2E suite.

These functions wrap the raw Playwright `Page` with intent-named operations
(`login`, `open_course`, `enable_course_ai_assistant`, `ask_assistant`, ...) so
the spec in ``test_course_ai_assistant.py`` reads like the user story.

IMPORTANT — SELECTOR CONFIRMATION
---------------------------------
Canvas is not running while this file is being authored, so the exact DOM is not
observable. Every place that depends on the live markup is marked with a
``# TODO(selector):`` comment and, wherever possible, given *several* candidate
locators tried in order. Confirm/trim these against the running UI:

    DISPLAY=:0 E2E_HEADLESS=0 E2E_SLOW_MO=400 \
        ~/.local/bin/playwright codegen http://canvas.docker

Design notes
------------
* Locators prefer accessible roles / labels / stable ids over brittle CSS.
* ``first_visible`` walks a list of candidate locators and returns the first one
  that is actually visible, so confirming a selector is "delete the wrong
  candidates" rather than "rewrite the function".
* The agent tab embeds the assistant in an ``<iframe>``; ``assistant_frame``
  returns a ``FrameLocator`` so callers never poke at the outer document by
  mistake.
"""
from __future__ import annotations

import re
import time
from typing import Iterable

from playwright.sync_api import (
    FrameLocator,
    Locator,
    Page,
    TimeoutError as PWTimeoutError,
    expect,
)

import config


# --------------------------------------------------------------------------- #
# low-level utilities
# --------------------------------------------------------------------------- #
def first_visible(page: Page, selectors: Iterable[str], timeout_ms: int | None = None) -> Locator:
    """Return the first locator (from ``selectors``) that becomes visible.

    Tries each candidate for a short slice of the overall budget. Raises
    AssertionError listing everything tried if none appear — which makes a
    selector that drifted out of date obvious in the failure output.
    """
    selectors = list(selectors)
    budget = timeout_ms if timeout_ms is not None else config.TIMEOUT_MS
    per = max(750, budget // max(1, len(selectors)))
    tried: list[str] = []
    deadline = time.monotonic() + budget / 1000.0
    while time.monotonic() < deadline:
        for sel in selectors:
            tried.append(sel)
            loc = page.locator(sel).first
            try:
                loc.wait_for(state="visible", timeout=per)
                return loc
            except PWTimeoutError:
                continue
    raise AssertionError(
        "None of the candidate selectors became visible within "
        f"{budget} ms. Tried (confirm against live UI):\n  - "
        + "\n  - ".join(dict.fromkeys(tried))
    )


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

    # TODO(selector): Canvas' default login form uses #pseudonym_session_unique_id
    # and #pseudonym_session_password. Some installs (LDAP/SAML/dev) differ.
    email_box = first_visible(
        page,
        [
            "#pseudonym_session_unique_id",
            "input[name='pseudonym_session[unique_id]']",
            "input[type='email']",
            "input[name='email']",
        ],
    )
    email_box.fill(email)

    pwd_box = first_visible(
        page,
        [
            "#pseudonym_session_password",
            "input[name='pseudonym_session[password]']",
            "input[type='password']",
        ],
    )
    pwd_box.fill(password)

    # TODO(selector): default submit button text is "Log In".
    submit = first_visible(
        page,
        [
            "button:has-text('Log In')",
            "input[type='submit'][value='Log In']",
            "#login_form button[type='submit']",
            "button[type='submit']",
        ],
    )
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
        # TODO(selector): /courses renders a table of enrolled/all courses with
        # links of the form <a href="/courses/123">Name</a>.
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
    """Turn on the Course AI Assistant for the given course.

    Two common shapes are handled:
      A) a Course **Feature Flag** toggled on /courses/<id>/settings under the
         "Feature Options" / "Feature Previews" tab; and
      B) a course-navigation item that is *hidden by default* and dragged/enabled
         on the Navigation tab of course settings.

    Confirm which mechanism the fork actually uses and keep that branch.
    """
    page.goto(f"{config.BASE_URL}/courses/{course_id}/settings",
              wait_until="domcontentloaded")

    # --- (A) Feature Option toggle ------------------------------------------
    # TODO(selector): open the Feature Options tab. Canvas uses an anchor
    # "#tab-features" / a tab labelled "Feature Options" (or "Feature Previews").
    feature_tab = page.get_by_role(
        "tab", name=re.compile(r"Feature (Options|Previews)", re.I)
    ).first
    try:
        feature_tab.wait_for(state="visible", timeout=4000)
        feature_tab.click()
    except PWTimeoutError:
        # Some themes render plain anchors instead of ARIA tabs.
        try:
            page.locator("a[href='#tab-features'], #course_features_tab").first.click(timeout=2000)
        except PWTimeoutError:
            pass

    # TODO(selector): each feature row has a heading with the feature name and a
    # state toggle (a <button> with aria-label like "<Feature> is Off"). The
    # default display name registered by the fork is assumed to be
    # "Course AI Assistant". Adjust if the migration registered a different
    # display_name / feature key.
    enabled_via_flag = _try_enable_feature_flag(page, config.FEATURE_TAB_NAME)

    if not enabled_via_flag:
        # --- (B) Navigation tab fallback ------------------------------------
        _try_enable_navigation_item(page, course_id, config.FEATURE_TAB_NAME)

    screenshot(page, "after-enable")


def _try_enable_feature_flag(page: Page, feature_name: str) -> bool:
    """Attempt the Feature-Option path. Returns True if it looks enabled."""
    # Find the row/card whose accessible name mentions the feature.
    # TODO(selector): confirm the toggle control. Canvas modern UI uses a button
    # whose aria-label flips between "Enabled"/"Disabled"/"Off"/"On".
    name_re = re.compile(re.escape(feature_name), re.I)
    candidates = [
        page.get_by_role("button", name=name_re),
        page.locator("[role='listitem']").filter(has_text=name_re).get_by_role("button"),
        page.locator("div").filter(has_text=name_re).get_by_role("button"),
    ]
    for ctrl in candidates:
        ctrl = ctrl.first
        try:
            ctrl.wait_for(state="visible", timeout=3000)
        except PWTimeoutError:
            continue
        label = (ctrl.get_attribute("aria-label") or ctrl.inner_text() or "").lower()
        if any(w in label for w in ("on", "enabled")):
            return True  # already on
        # Toggle it on.
        ctrl.click()
        # A confirmation menu may appear ("Enabled" option in a popover).
        try:
            page.get_by_role("menuitemradio", name=re.compile(r"Enabled|On", re.I)).first.click(
                timeout=2000
            )
        except PWTimeoutError:
            pass
        page.wait_for_timeout(500)
        return True
    return False


def _try_enable_navigation_item(page: Page, course_id: str, item_name: str) -> None:
    """Attempt the course-navigation path (drag a hidden item into the menu)."""
    # TODO(selector): the Navigation tab lives at #tab-navigation. Hidden items
    # sit in a "disabled" list; enable via the kebab menu -> "Enable", or drag
    # from the lower list to the upper list. Drag-and-drop is fragile; prefer the
    # menu action if the fork exposes one.
    try:
        page.get_by_role("tab", name=re.compile(r"Navigation", re.I)).first.click(timeout=3000)
    except PWTimeoutError:
        try:
            page.locator("a[href='#tab-navigation']").first.click(timeout=2000)
        except PWTimeoutError:
            pass

    name_re = re.compile(re.escape(item_name), re.I)
    row = page.locator("li, tr").filter(has_text=name_re).first
    try:
        row.wait_for(state="visible", timeout=4000)
    except PWTimeoutError:
        # Nothing to do; either it's already in the nav or the fork auto-shows it
        # once the feature flag is on. Save the page state so this is debuggable.
        screenshot(page, "navigation-item-not-found")
        return

    # Try a kebab/gear menu -> Enable.
    try:
        row.get_by_role("button").first.click(timeout=2000)
        page.get_by_role("menuitem", name=re.compile(r"Enable", re.I)).first.click(timeout=2000)
    except PWTimeoutError:
        screenshot(page, "navigation-enable-no-menu")

    # Save the Navigation form.
    # TODO(selector): the Navigation tab has its own "Save" submit button.
    try:
        page.get_by_role("button", name=re.compile(r"^Save$", re.I)).first.click(timeout=3000)
        page.wait_for_load_state("domcontentloaded")
    except PWTimeoutError:
        screenshot(page, "navigation-save-not-found")


# --------------------------------------------------------------------------- #
# 4. the course-nav tab appears
# --------------------------------------------------------------------------- #
def course_nav_tab(page: Page, course_id: str, tab_name: str | None = None) -> Locator:
    """Return the course-navigation link for the assistant tab (must be visible).

    Reloads the course home so a freshly-enabled tab is picked up.
    """
    tab_name = tab_name or config.FEATURE_TAB_NAME
    page.goto(f"{config.BASE_URL}/courses/{course_id}", wait_until="domcontentloaded")

    # TODO(selector): course nav is a <nav id="section-tabs"> with <a> children.
    name_re = re.compile(re.escape(tab_name), re.I)
    tab = first_visible(
        page,
        [
            f"#section-tabs a:has-text('{tab_name}')",
            f"nav a:has-text('{tab_name}')",
            f"a[role='link']:has-text('{tab_name}')",
        ],
    )
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

    The tab content is rendered by the agent server inside an <iframe>. We don't
    know its name/id ahead of time, so match generously, then let the caller's
    interactions confirm we picked the right frame.
    """
    # TODO(selector): confirm the iframe attributes. Likely an LTI/tool iframe
    # (id like "tool_content" / class "tool_launch") or a same-origin app frame
    # pointing at the agent server (e.g. src*="ai-assistant" or the agent port).
    candidates = [
        "iframe#tool_content",
        "iframe.tool_launch",
        "iframe[title*='AI' i]",
        "iframe[src*='ai-assistant' i]",
        "iframe[src*='assistant' i]",
        "iframe[name*='assistant' i]",
        "iframe[data-testid*='assistant' i]",
        "iframe",  # last resort: the only iframe on the tab page
    ]
    last_err: Exception | None = None
    deadline = time.monotonic() + config.NAV_TIMEOUT_MS / 1000.0
    while time.monotonic() < deadline:
        for sel in candidates:
            try:
                loc = page.locator(sel).first
                loc.wait_for(state="attached", timeout=1500)
                return page.frame_locator(sel)
            except PWTimeoutError as exc:
                last_err = exc
                continue
    raise AssertionError(
        "Could not locate the assistant iframe. Confirm the iframe selector "
        f"against the live tab. Last error: {last_err}"
    )


def ask_assistant(page: Page, question: str) -> str:
    """Type ``question`` into the assistant, submit, and return the answer text.

    All locators are scoped to the iframe via ``assistant_frame``.
    """
    frame = assistant_frame(page)

    # TODO(selector): the chat input. The agent demo UI uses a free-text box and
    # an "Ask" button; adjust placeholder/role to match.
    box = _frame_first_visible(
        page,
        frame,
        [
            "textarea",
            "input[type='text']",
            "[contenteditable='true']",
            "[placeholder*='Ask' i]",
            "[data-testid='chat-input']",
        ],
    )
    box.click()
    box.fill(question)

    # Capture how many answer bubbles exist before we submit, so we can wait for
    # a NEW one rather than racing the previous answer.
    answer_sel = _ANSWER_SELECTOR
    before = _safe_count(frame.locator(answer_sel))

    # Submit: prefer an explicit button, fall back to Enter.
    submitted = False
    for btn_sel in (
        "button:has-text('Ask')",
        "button:has-text('Send')",
        "button[type='submit']",
        "[data-testid='chat-send']",
    ):
        try:
            frame.locator(btn_sel).first.click(timeout=1500)
            submitted = True
            break
        except PWTimeoutError:
            continue
    if not submitted:
        box.press("Enter")

    # Wait for a new answer bubble to appear and stop changing (LLM stream).
    return _wait_for_answer(frame, answer_sel, before)


# The element that holds a rendered assistant answer.
# TODO(selector): confirm. The demo renders answers as .msg.bot / .answer; an LTI
# tool may use its own markup. Keep this generous list aligned with the real UI.
_ANSWER_SELECTOR = ", ".join(
    [
        ".msg.bot",
        ".message.assistant",
        ".answer",
        "[data-role='assistant']",
        "[data-testid='assistant-message']",
    ]
)


def _frame_first_visible(page: Page, frame: FrameLocator, selectors: Iterable[str]) -> Locator:
    selectors = list(selectors)
    per = max(750, config.TIMEOUT_MS // max(1, len(selectors)))
    tried: list[str] = []
    deadline = time.monotonic() + config.TIMEOUT_MS / 1000.0
    while time.monotonic() < deadline:
        for sel in selectors:
            tried.append(sel)
            loc = frame.locator(sel).first
            try:
                loc.wait_for(state="visible", timeout=per)
                return loc
            except PWTimeoutError:
                continue
    raise AssertionError(
        "No assistant input became visible inside the iframe. Tried:\n  - "
        + "\n  - ".join(dict.fromkeys(tried))
    )


def _safe_count(loc: Locator) -> int:
    try:
        return loc.count()
    except Exception:
        return 0


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
