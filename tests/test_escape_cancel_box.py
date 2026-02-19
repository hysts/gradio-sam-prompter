"""Playwright UI tests for Escape key cancelling box drawing."""

from _demo import demo
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
    """Return relevant box-drawing state from the component."""
    return page.evaluate("""() => {
        var s = document.querySelector('.sam-prompter-container').__samPrompterState;
        var obj = s.objects[s.activeObjectIndex];
        return {
            isDrawingBox: s.isDrawingBox,
            didDrag: s.didDrag,
            mouseDownButton: s.mouseDownButton,
            points: obj.points.length,
            boxes: obj.boxes.length
        };
    }""")


def test_escape_cancels_box_drawing():
    """Pressing Escape mid-drag should cancel box drawing without adding a box."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Upload image
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            start_x = box["x"] + 30
            start_y = box["y"] + 30

            # Start dragging (mousedown + mousemove past threshold)
            page.mouse.move(start_x, start_y)
            page.mouse.down()
            page.mouse.move(start_x + 60, start_y + 40, steps=5)
            page.wait_for_timeout(100)

            # Verify box drawing is in progress
            mid_state = _get_state(page)
            assert mid_state["isDrawingBox"], "Should be drawing a box mid-drag"

            # Press Escape to cancel
            page.keyboard.press("Escape")
            page.wait_for_timeout(100)

            # Verify box drawing was cancelled
            after_esc = _get_state(page)
            assert not after_esc["isDrawingBox"], "isDrawingBox should be false after Escape"

            # Release mouse
            page.mouse.up()
            page.wait_for_timeout(300)

            # No box or point should have been added
            final = _get_state(page)
            assert final["boxes"] == 0, f"No box should be added after cancel, got {final['boxes']}"
            assert final["points"] == 0, f"No point should be added after cancel, got {final['points']}"

            browser.close()
    finally:
        demo.close()


def test_escape_cancel_then_mouseup_no_point():
    """After Escape cancels box drawing, the mouseup must not add a foreground point."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2

            # Start a box drag
            page.mouse.move(cx, cy)
            page.mouse.down()
            page.mouse.move(cx + 50, cy + 30, steps=5)
            page.wait_for_timeout(100)

            # Cancel with Escape
            page.keyboard.press("Escape")
            page.wait_for_timeout(50)

            # Release mouse at the current position
            page.mouse.up()
            page.wait_for_timeout(500)

            state = _get_state(page)
            assert state["points"] == 0, f"Mouseup after Escape should not add a point, got {state['points']} points"
            assert state["boxes"] == 0, f"Mouseup after Escape should not add a box, got {state['boxes']} boxes"

            browser.close()
    finally:
        demo.close()


def test_box_drawing_works_after_escape_cancel():
    """After cancelling with Escape, a new box drawing should work normally."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            x1 = box["x"] + 20
            y1 = box["y"] + 20

            # First attempt: start drag, then cancel
            page.mouse.move(x1, y1)
            page.mouse.down()
            page.mouse.move(x1 + 50, y1 + 30, steps=5)
            page.wait_for_timeout(100)
            page.keyboard.press("Escape")
            page.wait_for_timeout(50)
            page.mouse.up()
            page.wait_for_timeout(300)

            state_after_cancel = _get_state(page)
            assert state_after_cancel["boxes"] == 0, "No box after cancel"

            # Second attempt: draw a box normally
            x2 = box["x"] + 30
            y2 = box["y"] + 30
            page.mouse.move(x2, y2)
            page.mouse.down()
            page.mouse.move(x2 + 80, y2 + 60, steps=5)
            page.wait_for_timeout(100)
            page.mouse.up()
            page.wait_for_timeout(500)

            state_after_box = _get_state(page)
            assert state_after_box["boxes"] == 1, (
                f"Should have 1 box after normal draw, got {state_after_box['boxes']}"
            )
            assert state_after_box["points"] == 0, f"Should have no points, got {state_after_box['points']}"

            browser.close()
    finally:
        demo.close()


def test_click_works_after_escape_cancel():
    """After cancelling with Escape, a normal click should add a point."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            x1 = box["x"] + 30
            y1 = box["y"] + 30

            # Start drag, then cancel
            page.mouse.move(x1, y1)
            page.mouse.down()
            page.mouse.move(x1 + 50, y1 + 30, steps=5)
            page.wait_for_timeout(100)
            page.keyboard.press("Escape")
            page.wait_for_timeout(50)
            page.mouse.up()
            page.wait_for_timeout(300)

            # Now do a normal click (should add a foreground point)
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            page.mouse.click(cx, cy)
            page.wait_for_timeout(500)

            state = _get_state(page)
            assert state["points"] == 1, f"Click after cancel should add 1 point, got {state['points']}"
            assert state["boxes"] == 0, f"Click should not add a box, got {state['boxes']}"

            browser.close()
    finally:
        demo.close()
