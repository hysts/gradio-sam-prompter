"""Playwright UI tests for image upload, canvas click, clear, and button layout."""

from _demo import demo
from _helpers import upload_test_image, wait_for_container, wait_for_inference_complete
from playwright.sync_api import sync_playwright


def test_image_upload_persists():
    """After uploading an image the drop zone should stay hidden and canvas should be visible."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Upload image via DataTransfer API
            upload_test_image(page)

            # Check drop zone is hidden immediately after upload
            assert page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be hidden after upload"

            # Wait for Python round-trip (change -> mock_inference -> postprocess)
            wait_for_inference_complete(page)

            # Drop zone should STILL be hidden after Python responds
            still_hidden = page.evaluate("""() => {
                var dz = document.querySelector('.sam-prompter-container .drop-zone');
                return dz.classList.contains('hidden');
            }""")
            assert still_hidden, "Drop zone should still be hidden after Python round-trip"

            browser.close()
    finally:
        demo.close()


def test_click_on_canvas_adds_point_not_upload():
    """Clicking on the canvas after image upload should add a point, not trigger file upload."""
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

            # Verify upload succeeded
            assert page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be hidden"

            # Wait for full round-trip
            wait_for_inference_complete(page)
            assert page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should still be hidden after round-trip"

            # Click on the canvas center to add a foreground point
            canvas = page.locator(".sam-prompter-container canvas")
            canvas_box = canvas.bounding_box()
            page.mouse.click(
                canvas_box["x"] + canvas_box["width"] / 2,
                canvas_box["y"] + canvas_box["height"] / 2,
            )
            page.wait_for_timeout(500)

            # Drop zone should still be hidden (click should NOT trigger upload)
            assert page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be hidden after clicking canvas"

            # Verify a point was added by checking the canvas has drawn content
            has_point = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container canvas');
                var ctx = c.getContext('2d');
                var cx = Math.floor(c.width / 2);
                var cy = Math.floor(c.height / 2);
                var data = ctx.getImageData(cx - 5, cy - 5, 10, 10).data;
                var nonEmpty = false;
                for (var i = 0; i < data.length; i += 4) {
                    if (data[i + 3] > 0) { nonEmpty = true; break; }
                }
                return nonEmpty;
            }""")
            assert has_point, "Canvas should have drawn content at click location"

            browser.close()
    finally:
        demo.close()


def test_clear_image_resets():
    """Clicking the X button should clear the image and show the drop zone again."""
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

            # Verify upload succeeded
            assert page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be hidden after upload"

            # Click the clear image button (x)
            page.click(".sam-prompter-container .clear-image-btn")
            page.wait_for_timeout(500)

            # Drop zone should be visible again
            assert not page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be visible after clearing image"

            browser.close()
    finally:
        demo.close()


def test_image_button_in_toolbar_next_to_masks():
    """Image toggle button should be in the toolbar, right after the Masks button."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Image button should be inside toolbar-right, not in settings-bar
            in_toolbar = page.evaluate("""() => {
                var btn = document.querySelector('.sam-prompter-container .image-toggle-btn');
                if (!btn) return false;
                return btn.closest('.toolbar-right') !== null;
            }""")
            assert in_toolbar, "Image button should be inside .toolbar-right"

            not_in_settings = page.evaluate("""() => {
                var btn = document.querySelector('.sam-prompter-container .image-toggle-btn');
                if (!btn) return true;
                return btn.closest('.settings-bar') === null;
            }""")
            assert not_in_settings, "Image button should NOT be inside .settings-bar"

            # Image button should be the immediate previous sibling of Masks button
            is_adjacent = page.evaluate("""() => {
                var image = document.querySelector('.sam-prompter-container .image-toggle-btn');
                var masks = document.querySelector('.sam-prompter-container .mask-toggle-btn');
                if (!image || !masks) return false;
                return image.nextElementSibling === masks;
            }""")
            assert is_adjacent, "Image button should be immediately before Masks button"

            browser.close()
    finally:
        demo.close()
