"""Playwright UI tests for max_objects boundary enforcement.

Uses a demo with ``max_objects=2`` to verify that the N key shortcut,
the + Add button, and rapid presses all respect the upper limit.
"""

from _demo_max2 import demo
from _helpers import wait_for_container
from playwright.sync_api import Page, sync_playwright


def _get_object_count(page: Page) -> int:
    return page.evaluate("""() => {
        var c = document.querySelector('.sam-prompter-container');
        return c.__samPrompterState.objects.length;
    }""")


def _hover_container(page: Page) -> None:
    """Move mouse over the container to activate keyboard shortcuts."""
    container = page.locator(".sam-prompter-container")
    box = container.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def test_n_key_rejected_at_max_objects():
    """Pressing N when already at max_objects should have no effect."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            assert _get_object_count(page) == 1, "Should start with 1 object"

            _hover_container(page)

            # Add one object to reach the limit (max_objects=2)
            page.keyboard.press("n")
            page.wait_for_timeout(200)
            assert _get_object_count(page) == 2, "Should have 2 objects after first N"

            # Try adding beyond the limit
            page.keyboard.press("n")
            page.wait_for_timeout(200)
            assert _get_object_count(page) == 2, "Should still have 2 objects (at max)"

            browser.close()
    finally:
        demo.close()


def test_add_button_disabled_at_max_objects():
    """The + Add button should be disabled when at max_objects."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Add one object to reach the limit (max_objects=2)
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(200)
            assert _get_object_count(page) == 2, "Should have 2 objects"

            # Button should be disabled
            is_disabled = page.evaluate("""() => {
                var btn = document.querySelector('.sam-prompter-container .add-object-btn');
                return btn.disabled || btn.classList.contains('disabled');
            }""")
            assert is_disabled, "Add button should be disabled at max_objects"

            browser.close()
    finally:
        demo.close()


def test_object_count_does_not_exceed_max():
    """Rapid N presses should never create more objects than max_objects."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            _hover_container(page)

            # Rapid-fire N presses well beyond max_objects=2
            for _ in range(10):
                page.keyboard.press("n")
            page.wait_for_timeout(300)

            count = _get_object_count(page)
            assert count <= 2, f"Object count should not exceed max_objects=2, got {count}"

            browser.close()
    finally:
        demo.close()
