"""Pytest fixtures for the Course AI Assistant E2E suite.

Provides:
  * ``browser``            session-scoped Chromium launched from the global
                           Playwright at ~/.local/bin (headless unless E2E_HEADLESS=0).
  * ``context``            per-test BrowserContext that ignores the self-signed
                           cert a dev Canvas often serves, records video + a
                           Playwright trace, and saves them as artifacts.
  * ``page``               a fresh Page in that context.
  * ``instructor_page``    a Page already logged in as the admin/instructor.

The suite uses ``sync_playwright`` directly (no pytest-playwright plugin
required) so it runs anywhere the ``playwright`` Python package is importable —
which is the case for the global install at ~/.local/lib.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

import config
import helpers


# --------------------------------------------------------------------------- #
# session: one Playwright + one browser for the whole run
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def _playwright():
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(_playwright) -> Browser:
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    print("\n" + config.summary())
    browser = _playwright.chromium.launch(
        headless=config.HEADLESS,
        slow_mo=config.SLOW_MO,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    yield browser
    browser.close()


# --------------------------------------------------------------------------- #
# per-test: isolated context with tracing + video + cert tolerance
# --------------------------------------------------------------------------- #
@pytest.fixture
def context(browser: Browser, request) -> BrowserContext:
    ctx = browser.new_context(
        ignore_https_errors=True,  # dev Canvas commonly uses a self-signed cert
        viewport={"width": 1366, "height": 900},
        record_video_dir=str(config.ARTIFACT_DIR / "video"),
    )
    ctx.set_default_timeout(config.TIMEOUT_MS)
    ctx.set_default_navigation_timeout(config.NAV_TIMEOUT_MS)
    ctx.tracing.start(screenshots=True, snapshots=True, sources=True)

    yield ctx

    # On failure, persist a trace named after the test; on success, discard it.
    failed = getattr(request.node, "_e2e_failed", False)
    trace_path = config.ARTIFACT_DIR / f"trace-{request.node.name}.zip"
    try:
        ctx.tracing.stop(path=str(trace_path) if failed else None)
    except Exception as exc:  # pragma: no cover - diagnostics only
        print(f"[conftest] tracing.stop failed: {exc}")
    ctx.close()
    if failed:
        print(f"[conftest] trace saved -> {trace_path}")


@pytest.fixture
def page(context: BrowserContext) -> Page:
    return context.new_page()


@pytest.fixture
def instructor_page(page: Page) -> Page:
    """A page already authenticated as the configured admin/instructor."""
    helpers.login(page)
    return page


# --------------------------------------------------------------------------- #
# wire failure state into the context fixture so it can keep the trace
# --------------------------------------------------------------------------- #
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        item._e2e_failed = True


# --------------------------------------------------------------------------- #
# custom CLI flag so a single positive test can be run easily
# --------------------------------------------------------------------------- #
def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Override BASE_URL for this run (else env/default is used).",
    )


@pytest.fixture(autouse=True, scope="session")
def _apply_base_url_override(request):
    override = request.config.getoption("--base-url")
    if override:
        config.BASE_URL = override.rstrip("/")
