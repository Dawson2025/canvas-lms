"""End-to-end spec for the Canvas "Course AI Assistant" feature.

User story under test
----------------------
1. An instructor logs into Canvas.
2. Opens one of their courses.
3. Enables the "Course AI Assistant" (course feature flag / nav item).
4. The "Course AI Assistant" tab appears in the course navigation.
5. Opens that tab (the assistant is embedded via an <iframe>).
6. Asks "what is due this week?" and gets a grounded, non-empty, course-specific
   answer (drawn from the course's published content).
7. Asks an out-of-scope question and the assistant declines.

How to run
----------
    # headless CI runner with PASS/FAIL summary
    ./run_e2e.sh

    # headed live demo (DISPLAY=:0, slow motion)
    ./demo_headed.sh

    # or directly with the global pytest/playwright
    BASE_URL=http://canvas.docker python3 -m pytest -v test_course_ai_assistant.py

Canvas must be reachable at BASE_URL. Selectors marked ``# TODO(selector)`` in
helpers.py must be confirmed against the live UI before this is green.

The full journey is also expressed as ONE ordered story test
(``test_full_course_ai_assistant_journey``) so a smoke run is a single command,
while the granular ``test_step_*`` tests localize failures during development.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

import config
import helpers


# --------------------------------------------------------------------------- #
# the questions
# --------------------------------------------------------------------------- #
IN_SCOPE_QUESTION = "what is due this week?"

# Clearly outside any single course's published content -> must be declined.
OUT_OF_SCOPE_QUESTION = "Who won the most recent Super Bowl, and what was the score?"

# Generic chatter that should NOT count as a "grounded, course-specific" answer.
# Used to assert the in-scope answer is more than a greeting/boilerplate.
_GENERIC_NOISE = re.compile(
    r"^(hi|hello|hey|sure|of course|i'?m happy to help|how can i help)\b", re.I
)


# --------------------------------------------------------------------------- #
# helpers local to the spec
# --------------------------------------------------------------------------- #
def _course_specific_tokens(page: Page, course_id: str) -> list[str]:
    """Pull a few stable, course-identifying tokens from the course home.

    A "grounded, course-specific" answer should plausibly contain at least one
    of these (the course code, or a word from its title), OR concrete due-date
    language. We keep the bar low and robust because LLM phrasing varies — the
    point is to reject a generic "I can help!" non-answer, not to pin exact text.
    """
    tokens: list[str] = []
    # TODO(selector): course title is usually an <h1>/<h2> in the course header
    # or the breadcrumb. Grab visible heading text and split into words.
    try:
        heading = page.locator("h1, h2, .course-title, #breadcrumbs .ellipsible").first
        title = (heading.inner_text(timeout=3000) or "").strip()
    except Exception:
        title = ""
    for w in re.split(r"\s+", title):
        w = w.strip(":-—,.").strip()
        if len(w) >= 3:
            tokens.append(w)
    tokens.append(course_id)
    return tokens


def _assert_grounded_answer(answer: str, page: Page, course_id: str) -> None:
    """Assertions for step 6: non-empty, substantive, course-grounded, not a decline."""
    assert answer, "Assistant returned an empty answer for an in-scope question."
    assert len(answer.strip()) >= 15, f"Answer suspiciously short: {answer!r}"
    assert not helpers.looks_like_decline(answer), (
        f"Assistant DECLINED an in-scope question. Answer was: {answer!r}"
    )
    assert not _GENERIC_NOISE.match(answer.strip()), (
        f"Answer looks like generic boilerplate, not a grounded reply: {answer!r}"
    )

    # Grounding signal: either it references something course-specific, or it
    # talks about due dates / deadlines / "this week" in a concrete way, or it
    # plainly states nothing is due (also a valid grounded answer).
    lower = answer.lower()
    due_language = any(
        kw in lower
        for kw in ("due", "deadline", "assignment", "this week", "nothing is due",
                   "no assignments", "submit", "quiz", "exam")
    )
    tokens = _course_specific_tokens(page, course_id)
    course_ref = any(t.lower() in lower for t in tokens if t)
    assert due_language or course_ref, (
        "Answer does not look grounded in the course (no due-date language and "
        f"no course-specific token from {tokens!r}). Answer: {answer!r}"
    )


# --------------------------------------------------------------------------- #
# the ordered story test (the smoke test)
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
def test_full_course_ai_assistant_journey(instructor_page: Page) -> None:
    """All seven steps in sequence against a live Canvas."""
    page = instructor_page  # step 1 (login) already done by the fixture

    # 2. open a course
    course_id = helpers.open_course(page)

    # 3. enable the Course AI Assistant
    helpers.enable_course_ai_assistant(page, course_id)

    # 4. the tab appears in course navigation
    tab = helpers.course_nav_tab(page, course_id, config.FEATURE_TAB_NAME)
    expect(tab).to_be_visible()

    # 5. open the tab (assistant is embedded in an iframe)
    helpers.open_assistant_tab(page, course_id, config.FEATURE_TAB_NAME)
    frame = helpers.assistant_frame(page)
    # the iframe should have a visible body / input
    expect(frame.locator("body")).to_be_visible()

    # 6. ask an in-scope question -> grounded, non-empty, course-specific answer
    in_scope_answer = helpers.ask_assistant(page, IN_SCOPE_QUESTION)
    print(f"\n[in-scope answer]\n{in_scope_answer}\n")
    _assert_grounded_answer(in_scope_answer, page, course_id)

    # 7. ask an out-of-scope question -> the assistant declines
    decline = helpers.ask_assistant(page, OUT_OF_SCOPE_QUESTION)
    print(f"\n[out-of-scope answer]\n{decline}\n")
    assert decline, "Assistant returned nothing for the out-of-scope question."
    assert helpers.looks_like_decline(decline), (
        "Assistant did NOT decline an out-of-scope question. It should redirect "
        f"to the course's published content. Answer was: {decline!r}"
    )
    # It must not actually answer the trivia (no score / team name leakage).
    assert not re.search(r"\b\d+\s*[-–to]+\s*\d+\b", decline), (
        f"Out-of-scope answer appears to contain a sports score: {decline!r}"
    )


# --------------------------------------------------------------------------- #
# granular tests — same flow, isolated so failures point at one step
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
def test_step_1_instructor_can_log_in(page: Page) -> None:
    helpers.login(page)
    assert "/login" not in page.url, f"Still on login page: {page.url}"


@pytest.mark.e2e
def test_step_2_can_open_a_course(instructor_page: Page) -> None:
    course_id = helpers.open_course(instructor_page)
    assert course_id.isdigit(), f"Did not resolve a numeric course id: {course_id!r}"
    assert f"/courses/{course_id}" in instructor_page.url


@pytest.mark.e2e
def test_step_3_4_enable_makes_tab_appear(instructor_page: Page) -> None:
    page = instructor_page
    course_id = helpers.open_course(page)
    helpers.enable_course_ai_assistant(page, course_id)
    tab = helpers.course_nav_tab(page, course_id, config.FEATURE_TAB_NAME)
    expect(tab).to_be_visible()
    expect(tab).to_have_text(re.compile(re.escape(config.FEATURE_TAB_NAME), re.I))


@pytest.mark.e2e
def test_step_5_assistant_tab_embeds_iframe(instructor_page: Page) -> None:
    page = instructor_page
    course_id = helpers.open_course(page)
    helpers.enable_course_ai_assistant(page, course_id)
    helpers.open_assistant_tab(page, course_id, config.FEATURE_TAB_NAME)
    frame = helpers.assistant_frame(page)
    expect(frame.locator("body")).to_be_visible()


@pytest.mark.e2e
def test_step_6_in_scope_answer_is_grounded(instructor_page: Page) -> None:
    page = instructor_page
    course_id = helpers.open_course(page)
    helpers.enable_course_ai_assistant(page, course_id)
    helpers.open_assistant_tab(page, course_id, config.FEATURE_TAB_NAME)
    answer = helpers.ask_assistant(page, IN_SCOPE_QUESTION)
    print(f"\n[in-scope answer]\n{answer}\n")
    _assert_grounded_answer(answer, page, course_id)


@pytest.mark.e2e
def test_step_7_out_of_scope_is_declined(instructor_page: Page) -> None:
    page = instructor_page
    course_id = helpers.open_course(page)
    helpers.enable_course_ai_assistant(page, course_id)
    helpers.open_assistant_tab(page, course_id, config.FEATURE_TAB_NAME)
    decline = helpers.ask_assistant(page, OUT_OF_SCOPE_QUESTION)
    print(f"\n[out-of-scope answer]\n{decline}\n")
    assert helpers.looks_like_decline(decline), (
        f"Out-of-scope question was not declined: {decline!r}"
    )
