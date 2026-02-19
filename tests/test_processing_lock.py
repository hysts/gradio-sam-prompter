"""Playwright UI tests for click blocking during mask computation.

These tests use a slow mock inference (1 s delay) to verify that the
isProcessing flag properly blocks canvas interactions while a Python
round-trip is in flight and results are being rendered.
"""

from _demo_slow import demo
from playwright.sync_api import Page, sync_playwright

UPLOAD_IMAGE_JS = """() => {
    return new Promise(function(resolve) {
        var fi = document.querySelector('.sam-prompter-container .file-input');
        var canvas = document.createElement('canvas');
        canvas.width = 200; canvas.height = 150;
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = 'rgb(100,150,200)';
        ctx.fillRect(0, 0, 200, 150);
        canvas.toBlob(function(blob) {
            var file = new File([blob], 'test.png', {type: 'image/png'});
            var dt = new DataTransfer();
            dt.items.add(file);
            fi.files = dt.files;
            fi.dispatchEvent(new Event('change', {bubbles: true}));
            resolve(true);
        }, 'image/png');
    });
}"""


def _get_state(page: Page) -> dict:
    """Return processing-related state from the component."""
    return page.evaluate("""() => {
        var c = document.querySelector('.sam-prompter-container');
        var s = c.__samPrompterState;
        var obj = s.objects[s.activeObjectIndex];
        return {
            isProcessing: s.isProcessing,
            isProcessingClass: c.classList.contains('is-processing'),
            points: obj.points.length,
            labels: obj.labels.slice(),
            boxes: obj.boxes.length,
            cursor: window.getComputedStyle(c.querySelector('.canvas-wrapper')).cursor,
            hasImage: !!s.image,
            imageSource: s.imageSource
        };
    }""")


def _setup(page: Page, url: str) -> dict:
    """Navigate, upload image, wait for initial round-trip.

    Returns the canvas bounding box.
    """
    page.set_default_timeout(10000)
    page.goto(url)
    page.wait_for_timeout(1000)

    page.evaluate(UPLOAD_IMAGE_JS)
    page.wait_for_timeout(1500)

    # Wait for initial round-trip (image upload → mock_inference → postprocess)
    page.wait_for_timeout(3000)

    canvas = page.locator(".sam-prompter-container canvas")
    return canvas.bounding_box()


def test_is_processing_set_during_inference():
    """IsProcessing should be true while Python is computing masks."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            box = _setup(page, url)

            cx = box["x"] + box["width"] * 0.5
            cy = box["y"] + box["height"] * 0.5

            # Click → triggers slow inference
            page.mouse.click(cx, cy)
            page.wait_for_timeout(200)

            state = _get_state(page)
            assert state["isProcessing"], "isProcessing should be true during inference"
            assert state["points"] == 1, "First point should have been added"

            # Wait for inference to finish
            page.wait_for_timeout(2000)

            state_after = _get_state(page)
            assert not state_after["isProcessing"], "isProcessing should be false after inference completes"

            browser.close()
    finally:
        demo.close()


def test_click_blocked_during_processing():
    """A second click during mask computation should be ignored."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            box = _setup(page, url)

            x1 = box["x"] + box["width"] * 0.3
            y1 = box["y"] + box["height"] * 0.3
            x2 = box["x"] + box["width"] * 0.7
            y2 = box["y"] + box["height"] * 0.7

            # Click point 1 → triggers slow inference
            page.mouse.click(x1, y1)
            page.wait_for_timeout(200)

            # Try clicking point 2 → should be blocked
            page.mouse.click(x2, y2)
            page.wait_for_timeout(100)

            state = _get_state(page)
            assert state["points"] == 1, (
                f"Second click during processing should be blocked, got {state['points']} points"
            )

            # Wait for inference to complete
            page.wait_for_timeout(2000)

            # Should still have exactly 1 point
            state_after = _get_state(page)
            assert state_after["points"] == 1, (
                f"Should have exactly 1 point after inference, got {state_after['points']}"
            )

            browser.close()
    finally:
        demo.close()


def test_right_click_blocked_during_processing():
    """Right-click (background point) during processing should be ignored."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            box = _setup(page, url)

            x1 = box["x"] + box["width"] * 0.3
            y1 = box["y"] + box["height"] * 0.3
            x2 = box["x"] + box["width"] * 0.7
            y2 = box["y"] + box["height"] * 0.7

            # Click point 1 (foreground) → triggers slow inference
            page.mouse.click(x1, y1)
            page.wait_for_timeout(200)

            # Right-click during processing → should be blocked
            page.mouse.click(x2, y2, button="right")
            page.wait_for_timeout(100)

            state = _get_state(page)
            assert state["points"] == 1, (
                f"Right-click during processing should be blocked, got {state['points']} points"
            )

            # Wait for inference to complete
            page.wait_for_timeout(2000)

            state_after = _get_state(page)
            assert state_after["points"] == 1, f"Should have exactly 1 point, got {state_after['points']}"

            browser.close()
    finally:
        demo.close()


def test_click_works_after_processing():
    """After processing completes, clicks should be accepted again."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            # Use a tall viewport so the canvas (which expands to fill
            # the wrapper) doesn't push click targets off-screen.
            page.set_viewport_size({"width": 1280, "height": 2000})
            box = _setup(page, url)

            x1 = box["x"] + box["width"] * 0.3
            y1 = box["y"] + box["height"] * 0.3

            # Click point 1 → triggers slow inference
            page.mouse.click(x1, y1)

            # Wait for inference to fully complete
            page.wait_for_timeout(2500)

            state_mid = _get_state(page)
            assert not state_mid["isProcessing"], "isProcessing should be false after inference"
            assert state_mid["hasImage"], f"Image should exist, state: {state_mid}"
            assert state_mid["points"] == 1, "Should have 1 point"

            # Re-query bounding box (layout may shift after inference)
            canvas = page.locator(".sam-prompter-container canvas")
            box2 = canvas.bounding_box()
            x2 = box2["x"] + box2["width"] * 0.5
            y2 = box2["y"] + box2["height"] * 0.5

            # Click point 2 → should work now
            page.mouse.click(x2, y2)
            page.wait_for_timeout(200)

            state_after = _get_state(page)
            assert state_after["points"] == 2, (
                f"Click after processing should add a point, got {state_after['points']}, state: {state_after}"
            )

            browser.close()
    finally:
        demo.close()


def test_cursor_wait_during_processing():
    """is-processing CSS class should be present during processing, absent after."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            box = _setup(page, url)

            cx = box["x"] + box["width"] * 0.5
            cy = box["y"] + box["height"] * 0.5

            # No is-processing class before any click
            state_before = _get_state(page)
            assert not state_before["isProcessingClass"], "is-processing class should not be present before click"

            # Click → triggers slow inference
            page.mouse.click(cx, cy)
            page.wait_for_timeout(200)

            state_during = _get_state(page)
            assert state_during["isProcessingClass"], (
                f"is-processing class should be present during processing, state: {state_during}"
            )
            assert state_during["cursor"] == "wait", (
                f"Cursor should be 'wait' during processing, got '{state_during['cursor']}'"
            )

            # Wait for inference to complete
            page.wait_for_timeout(2000)

            state_after = _get_state(page)
            assert not state_after["isProcessingClass"], "is-processing class should be removed after processing"

            browser.close()
    finally:
        demo.close()


def test_undo_blocked_during_processing():
    """Undo (Z key) during processing should be blocked."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            box = _setup(page, url)

            cx = box["x"] + box["width"] * 0.5
            cy = box["y"] + box["height"] * 0.5

            # Click a point → triggers slow inference
            page.mouse.click(cx, cy)
            page.wait_for_timeout(200)

            assert _get_state(page)["points"] == 1, "Should have 1 point"

            # Press Z (undo) during processing → should be blocked
            # Move mouse over the container so keyboard shortcut is active
            page.mouse.move(cx, cy)
            page.keyboard.press("z")
            page.wait_for_timeout(100)

            state = _get_state(page)
            assert state["points"] == 1, f"Undo during processing should be blocked, got {state['points']} points"

            # Wait for inference to complete
            page.wait_for_timeout(2000)

            # Point should still be there
            state_after = _get_state(page)
            assert state_after["points"] == 1, f"Point should survive blocked undo, got {state_after['points']}"

            browser.close()
    finally:
        demo.close()


def test_box_draw_blocked_during_processing():
    """Box drawing during processing should be blocked."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            box = _setup(page, url)

            cx = box["x"] + box["width"] * 0.5
            cy = box["y"] + box["height"] * 0.5

            # Click a point → triggers slow inference
            page.mouse.click(cx, cy)
            page.wait_for_timeout(200)

            # Attempt box drawing during processing
            drag_x = box["x"] + 20
            drag_y = box["y"] + 20
            page.mouse.move(drag_x, drag_y)
            page.mouse.down()
            page.mouse.move(drag_x + 80, drag_y + 60, steps=5)
            page.mouse.up()
            page.wait_for_timeout(100)

            state = _get_state(page)
            assert state["boxes"] == 0, f"Box draw during processing should be blocked, got {state['boxes']} boxes"
            assert state["points"] == 1, "Original point should remain"

            # Wait for inference to complete
            page.wait_for_timeout(2000)

            state_after = _get_state(page)
            assert state_after["boxes"] == 0, "No box should exist after processing"
            assert state_after["points"] == 1, "Point should still exist"

            browser.close()
    finally:
        demo.close()
