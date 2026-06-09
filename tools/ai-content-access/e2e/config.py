"""Centralized configuration for the Course AI Assistant E2E suite.

Everything is parameterized via environment variables with sensible defaults so
the same code runs against a throwaway local Canvas, CI, or a teammate's box.

    BASE_URL        Canvas root URL            (default http://canvas.docker)
    ADMIN_EMAIL     instructor/admin login     (default admin@canvas.docker)
    ADMIN_PASSWORD  instructor/admin password  (default canvasdev123)

Optional knobs (all have safe defaults):

    E2E_COURSE_ID       numeric Canvas course id to open directly. If unset, the
                        suite navigates to /courses and picks the first course.
    E2E_COURSE_NAME     substring to match a course by name on the courses page
                        when E2E_COURSE_ID is not given.
    E2E_HEADLESS        "1"/"true" -> headless (default), "0"/"false" -> headed.
    E2E_SLOW_MO         ms of slow_mo between actions (default 0; demo uses 250).
    E2E_TIMEOUT_MS      per-action timeout in ms (default 30000).
    E2E_NAV_TIMEOUT_MS  per-navigation timeout in ms (default 45000).
    E2E_ANSWER_TIMEOUT_MS  how long to wait for an agent answer (default 60000;
                        LLM round-trips can be slow).
    E2E_FEATURE_TAB_NAME   the exact label of the course-nav tab to look for
                        (default "Course AI Assistant").
    E2E_ARTIFACT_DIR    where screenshots/traces land (default ./artifacts).
    E2E_KEEP_ENABLED    "1" -> do not attempt to disable the feature on teardown.
"""
from __future__ import annotations

import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# --- connection / auth -------------------------------------------------------
BASE_URL: str = os.environ.get("BASE_URL", "http://canvas.docker").rstrip("/")
ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "admin@canvas.docker")
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "canvasdev123")

# --- course selection --------------------------------------------------------
COURSE_ID: str | None = os.environ.get("E2E_COURSE_ID") or None
COURSE_NAME: str | None = os.environ.get("E2E_COURSE_NAME") or None

# --- the feature under test --------------------------------------------------
FEATURE_TAB_NAME: str = os.environ.get("E2E_FEATURE_TAB_NAME", "Course AI Assistant")

# --- browser behavior --------------------------------------------------------
HEADLESS: bool = _env_bool("E2E_HEADLESS", True)
SLOW_MO: int = _env_int("E2E_SLOW_MO", 0)
TIMEOUT_MS: int = _env_int("E2E_TIMEOUT_MS", 30_000)
NAV_TIMEOUT_MS: int = _env_int("E2E_NAV_TIMEOUT_MS", 45_000)
ANSWER_TIMEOUT_MS: int = _env_int("E2E_ANSWER_TIMEOUT_MS", 60_000)

# --- artifacts ---------------------------------------------------------------
ARTIFACT_DIR: Path = Path(
    os.environ.get("E2E_ARTIFACT_DIR", str(Path(__file__).parent / "artifacts"))
)

# --- teardown ----------------------------------------------------------------
KEEP_ENABLED: bool = _env_bool("E2E_KEEP_ENABLED", False)


def summary() -> str:
    """Human-readable, secret-redacted dump of the active config."""
    redacted = "*" * len(ADMIN_PASSWORD) if ADMIN_PASSWORD else "(empty)"
    return (
        "Course AI Assistant E2E config\n"
        f"  BASE_URL          = {BASE_URL}\n"
        f"  ADMIN_EMAIL       = {ADMIN_EMAIL}\n"
        f"  ADMIN_PASSWORD    = {redacted}\n"
        f"  COURSE_ID         = {COURSE_ID or '(auto: first course)'}\n"
        f"  COURSE_NAME       = {COURSE_NAME or '(unset)'}\n"
        f"  FEATURE_TAB_NAME  = {FEATURE_TAB_NAME!r}\n"
        f"  HEADLESS          = {HEADLESS}\n"
        f"  SLOW_MO           = {SLOW_MO} ms\n"
        f"  TIMEOUT_MS        = {TIMEOUT_MS} ms\n"
        f"  ANSWER_TIMEOUT_MS = {ANSWER_TIMEOUT_MS} ms\n"
        f"  ARTIFACT_DIR      = {ARTIFACT_DIR}\n"
    )


if __name__ == "__main__":  # `python3 config.py` prints the resolved config
    print(summary())
