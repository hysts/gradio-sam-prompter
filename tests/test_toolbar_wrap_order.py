"""Playwright UI tests for toolbar wrap-reverse layout.

When the viewport is wide, toolbar-left (object list) and toolbar-right
(Undo, Clear, etc.) sit on the same row with toolbar-left on the left.
When the viewport is narrow and the toolbar wraps, toolbar-right should
appear ABOVE toolbar-left (via CSS flex-wrap: wrap-reverse).
"""

from _demo import demo
from playwright.sync_api import sync_playwright


def _get_toolbar_positions(page: object) -> dict | None:
    """Return bounding-rect info for toolbar-left and toolbar-right."""
    return page.evaluate("""() => {
        var left = document.querySelector('.sam-prompter-container .toolbar-left');
        var right = document.querySelector('.sam-prompter-container .toolbar-right');
        if (!left || !right) return null;
        var lr = left.getBoundingClientRect();
        var rr = right.getBoundingClientRect();
        return {
            leftTop: lr.top, leftBottom: lr.bottom, leftLeft: lr.left,
            rightTop: rr.top, rightBottom: rr.bottom, rightLeft: rr.left
        };
    }""")


def test_toolbar_same_row_when_wide():
    """With a wide viewport, toolbar-left and toolbar-right share the same row."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.set_default_timeout(5000)
            page.goto(url)
            page.wait_for_timeout(1000)

            pos = _get_toolbar_positions(page)
            assert pos is not None, "Toolbar elements should exist"

            # Both sections should share the same vertical position (same row)
            assert abs(pos["leftTop"] - pos["rightTop"]) < 5, (
                f"toolbar-left (top={pos['leftTop']}) and toolbar-right "
                f"(top={pos['rightTop']}) should be on the same row when wide"
            )

            # toolbar-left should be to the left of toolbar-right
            assert pos["leftLeft"] < pos["rightLeft"], (
                f"toolbar-left (left={pos['leftLeft']}) should be to the left "
                f"of toolbar-right (left={pos['rightLeft']})"
            )

            browser.close()
    finally:
        demo.close()


def test_toolbar_right_above_left_when_narrow():
    """With a narrow viewport, toolbar-right should wrap above toolbar-left."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            # Use a narrow width to force wrapping
            page.set_viewport_size({"width": 360, "height": 720})
            page.set_default_timeout(5000)
            page.goto(url)
            page.wait_for_timeout(1000)

            pos = _get_toolbar_positions(page)
            assert pos is not None, "Toolbar elements should exist"

            # toolbar-right should be above toolbar-left (lower top value)
            assert pos["rightTop"] < pos["leftTop"], (
                f"toolbar-right (top={pos['rightTop']}) should be above "
                f"toolbar-left (top={pos['leftTop']}) when viewport is narrow"
            )

            browser.close()
    finally:
        demo.close()
