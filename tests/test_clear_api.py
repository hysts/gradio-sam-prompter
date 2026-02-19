"""Playwright UI tests for SamPrompter.clear() Python API.

Tests cover the three variants:
- ``SamPrompter.clear()``             — clears prompts & masks, keeps image
- ``SamPrompter.clear(image)``        — clears prompts & masks, re-sends image
- ``SamPrompter.clear((image, masks))`` — clears prompts, re-sends with masks
"""

from _demo_clear import demo
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
    return page.evaluate("""() => {
        var c = document.querySelector('.sam-prompter-container');
        var s = c.__samPrompterState;
        var obj = s.objects[s.activeObjectIndex];
        return {
            hasImage: !!s.image,
            imageSource: s.imageSource,
            isProcessing: s.isProcessing,
            numObjects: s.objects.length,
            activeIndex: s.activeObjectIndex,
            points: obj.points.length,
            boxes: obj.boxes.length,
            maskCount: s.maskCanvases.filter(function(c) { return c !== null; }).length,
            rawMaskCount: s.rawMasks.filter(function(c) { return c !== null; }).length,
            dropZoneHidden: document.querySelector(
                '.sam-prompter-container .drop-zone'
            ).classList.contains('hidden')
        };
    }""")


def _setup_with_point(page: Page, url: str) -> dict:
    """Navigate, upload image, add a foreground point, wait for masks.

    Returns the canvas bounding box.
    """
    page.set_default_timeout(10000)
    page.goto(url)
    page.wait_for_timeout(1000)

    # Upload image
    page.evaluate(UPLOAD_IMAGE_JS)
    page.wait_for_timeout(1500)

    # Click to add a foreground point
    canvas = page.locator(".sam-prompter-container canvas")
    box = canvas.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    # Wait for mock inference round-trip
    page.wait_for_timeout(3000)
    return box


# =========================================================================
# SamPrompter.clear() — keep image, clear prompts & masks
# =========================================================================


def test_clear_keep_image_clears_prompts():
    """clear() should reset objects to a single empty one."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            pre = _get_state(page)
            assert pre["points"] > 0, "Should have points before clear"
            assert pre["maskCount"] > 0, "Should have masks before clear"

            # Click "Clear (keep image)"
            page.locator("#clear-keep").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["numObjects"] == 1, f"Should have 1 object after clear, got {post['numObjects']}"
            assert post["points"] == 0, f"Should have 0 points after clear, got {post['points']}"
            assert post["boxes"] == 0, f"Should have 0 boxes after clear, got {post['boxes']}"

            browser.close()
    finally:
        demo.close()


def test_clear_keep_image_preserves_image():
    """clear() should keep the image visible on the canvas."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            page.locator("#clear-keep").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["hasImage"], "Image should still be present after clear()"
            assert post["dropZoneHidden"], "Drop zone should remain hidden (image visible)"

            browser.close()
    finally:
        demo.close()


def test_clear_keep_image_clears_masks():
    """clear() should remove all masks."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            pre = _get_state(page)
            assert pre["maskCount"] > 0, "Should have masks before clear"

            page.locator("#clear-keep").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["maskCount"] == 0, f"Masks should be cleared, got {post['maskCount']}"
            assert post["rawMaskCount"] == 0, f"Raw masks should be cleared, got {post['rawMaskCount']}"

            browser.close()
    finally:
        demo.close()


def test_clear_keep_image_resets_processing():
    """clear() should reset isProcessing to false."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            page.locator("#clear-keep").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert not post["isProcessing"], "isProcessing should be false after clear()"

            browser.close()
    finally:
        demo.close()


# =========================================================================
# SamPrompter.clear(image) — re-send image, clear prompts & masks
# =========================================================================


def test_clear_resend_image_clears_prompts():
    """clear(image) should reset objects to a single empty one."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            pre = _get_state(page)
            assert pre["points"] > 0, "Should have points before clear"

            page.locator("#clear-resend").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["numObjects"] == 1, f"Should have 1 object, got {post['numObjects']}"
            assert post["points"] == 0, f"Should have 0 points, got {post['points']}"
            assert post["boxes"] == 0, f"Should have 0 boxes, got {post['boxes']}"

            browser.close()
    finally:
        demo.close()


def test_clear_resend_image_keeps_image():
    """clear(image) should display the re-sent image."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            page.locator("#clear-resend").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["hasImage"], "Image should be present after clear(image)"
            assert post["dropZoneHidden"], "Drop zone should remain hidden"

            browser.close()
    finally:
        demo.close()


def test_clear_resend_image_clears_masks():
    """clear(image) with no masks should clear existing masks."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            pre = _get_state(page)
            assert pre["maskCount"] > 0, "Should have masks before clear"

            page.locator("#clear-resend").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["maskCount"] == 0, f"Masks should be cleared, got {post['maskCount']}"

            browser.close()
    finally:
        demo.close()


# =========================================================================
# SamPrompter.clear((image, masks)) — re-send with masks, clear prompts
# =========================================================================


def test_clear_with_masks_clears_prompts():
    """clear((image, masks)) should reset objects to a single empty one."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            pre = _get_state(page)
            assert pre["points"] > 0, "Should have points before clear"

            page.locator("#clear-masks").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["numObjects"] == 1, f"Should have 1 object, got {post['numObjects']}"
            assert post["points"] == 0, f"Should have 0 points, got {post['points']}"
            assert post["boxes"] == 0, f"Should have 0 boxes, got {post['boxes']}"

            browser.close()
    finally:
        demo.close()


def test_clear_with_masks_shows_new_masks():
    """clear((image, masks)) should display the provided masks."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            page.locator("#clear-masks").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["hasImage"], "Image should be present"
            assert post["maskCount"] > 0, f"Should have masks from clear((image, masks)), got {post['maskCount']}"

            browser.close()
    finally:
        demo.close()


# =========================================================================
# Post-clear interaction
# =========================================================================


def test_can_add_point_after_clear():
    """After clear(), clicking on the canvas should add a new point."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            _setup_with_point(page, url)

            page.locator("#clear-keep").click()
            page.wait_for_timeout(2000)

            mid = _get_state(page)
            assert mid["points"] == 0, "Should have 0 points after clear"
            assert not mid["isProcessing"], "isProcessing should be false before click"

            # Re-query bounding box (layout may shift after clear)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(
                box["x"] + box["width"] / 2,
                box["y"] + box["height"] / 2,
            )
            page.wait_for_timeout(500)

            post = _get_state(page)
            assert post["points"] == 1, f"Should have 1 point after clicking, got {post['points']}"

            browser.close()
    finally:
        demo.close()


def test_clear_with_multiple_objects():
    """clear() should reset all objects, not just the active one."""
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

            # Add point to Object 1
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            page.wait_for_timeout(2500)

            # Add Object 2 with a point
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(300)
            page.mouse.click(box["x"] + 130, box["y"] + 80)
            page.wait_for_timeout(2500)

            pre = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return { numObjects: s.objects.length };
            }""")
            assert pre["numObjects"] == 2, "Should have 2 objects before clear"

            # Click "Clear (keep image)"
            page.locator("#clear-keep").click()
            page.wait_for_timeout(2000)

            post = _get_state(page)
            assert post["numObjects"] == 1, f"Should have 1 object after clear, got {post['numObjects']}"
            assert post["points"] == 0, "Points should be 0"
            assert post["maskCount"] == 0, "Masks should be cleared"

            browser.close()
    finally:
        demo.close()
