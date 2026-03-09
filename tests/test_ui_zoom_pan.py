"""Playwright UI tests for zoom/pan reset behavior and cursor states."""

from _demo import demo
from _helpers import upload_test_image, wait_for_container
from playwright.sync_api import sync_playwright


def test_zoom_out_to_min_resets_pan_wheel():
    """Zooming out to min (zoom=1) with scroll wheel should reset pan to (0,0)."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Upload image
            upload_test_image(page)

            # Move mouse to an off-center position on the canvas to produce non-zero pan
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            off_center_x = box["x"] + box["width"] * 0.25
            off_center_y = box["y"] + box["height"] * 0.25
            page.mouse.move(off_center_x, off_center_y)

            # Zoom in several times (deltaY < 0 = zoom in)
            for _ in range(10):
                page.mouse.wheel(0, -120)
            page.wait_for_timeout(300)

            zoomed_state = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                var s = c.__samPrompterState;
                return { zoom: s.zoom, panX: s.panX, panY: s.panY };
            }""")
            assert zoomed_state["zoom"] > 1, "Zoom should be greater than 1 after scrolling up"

            # Zoom out many times past minimum (deltaY > 0 = zoom out)
            for _ in range(30):
                page.mouse.wheel(0, 120)
            page.wait_for_timeout(300)

            final_state = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                var s = c.__samPrompterState;
                return { zoom: s.zoom, panX: s.panX, panY: s.panY };
            }""")
            assert final_state["zoom"] == 1, f"Zoom should be 1 at minimum, got {final_state['zoom']}"
            assert final_state["panX"] == 0, f"panX should be 0 at min zoom, got {final_state['panX']}"
            assert final_state["panY"] == 0, f"panY should be 0 at min zoom, got {final_state['panY']}"

            browser.close()
    finally:
        demo.close()


def test_zoom_out_to_min_resets_pan_keyboard():
    """Zooming out to min (zoom=1) with '-' key should reset pan to (0,0)."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Upload image
            upload_test_image(page)

            # Zoom in via scroll wheel off-center to create non-zero pan
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.3)
            for _ in range(8):
                page.mouse.wheel(0, -120)
            page.wait_for_timeout(300)

            zoomed_state = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                var s = c.__samPrompterState;
                return { zoom: s.zoom, panX: s.panX, panY: s.panY };
            }""")
            assert zoomed_state["zoom"] > 1, "Should be zoomed in"
            assert zoomed_state["panX"] != 0 or zoomed_state["panY"] != 0, (
                "Pan should be non-zero after off-center zoom"
            )

            # Zoom out with '-' key via dispatched keydown events
            page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                for (var i = 0; i < 20; i++) {
                    c.dispatchEvent(new KeyboardEvent('keydown', {
                        key: '-', code: 'Minus', bubbles: true
                    }));
                }
            }""")
            page.wait_for_timeout(300)

            final_state = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                var s = c.__samPrompterState;
                return { zoom: s.zoom, panX: s.panX, panY: s.panY };
            }""")
            assert final_state["zoom"] == 1, (
                f"Zoom should be 1 after pressing '-' many times, got {final_state['zoom']}"
            )
            assert final_state["panX"] == 0, f"panX should be 0 at min zoom, got {final_state['panX']}"
            assert final_state["panY"] == 0, f"panY should be 0 at min zoom, got {final_state['panY']}"

            browser.close()
    finally:
        demo.close()


def test_cursor_crosshair_by_default():
    """Canvas cursor should be crosshair in default (non-move, non-processing) mode."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            upload_test_image(page)

            cursor = page.evaluate("""() => {
                var canvas = document.querySelector('.sam-prompter-container canvas');
                return window.getComputedStyle(canvas).cursor;
            }""")
            assert cursor == "crosshair", f"Default cursor should be 'crosshair', got '{cursor}'"

            browser.close()
    finally:
        demo.close()


def test_cursor_grab_in_move_mode():
    """Canvas cursor should be grab when move mode is toggled on."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            upload_test_image(page)

            # Toggle move mode on
            page.click(".sam-prompter-container .move-btn")
            page.wait_for_timeout(200)

            # Zoom in so grab cursor appears (at zoom=1, no grab is needed)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            for _ in range(5):
                page.mouse.wheel(0, -120)
            page.wait_for_timeout(200)

            cursor = page.evaluate("""() => {
                var canvas = document.querySelector('.sam-prompter-container canvas');
                return window.getComputedStyle(canvas).cursor;
            }""")
            assert cursor == "grab", f"Move mode cursor should be 'grab', got '{cursor}'"

            # Toggle move mode off — cursor should revert to crosshair
            page.click(".sam-prompter-container .move-btn")
            page.wait_for_timeout(200)

            cursor_after = page.evaluate("""() => {
                var canvas = document.querySelector('.sam-prompter-container canvas');
                return window.getComputedStyle(canvas).cursor;
            }""")
            assert cursor_after == "crosshair", f"Cursor should revert to 'crosshair', got '{cursor_after}'"

            browser.close()
    finally:
        demo.close()
