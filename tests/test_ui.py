"""Playwright UI tests for SamPrompter component."""

from _demo import demo
from playwright.sync_api import sync_playwright

# Helper: inject a synthetic image via DataTransfer API.
# Playwright's set_input_files does not work with hidden file inputs inside gr.HTML.
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


def test_image_upload_persists():
    """After uploading an image the drop zone should stay hidden and canvas should be visible."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Upload image via DataTransfer API
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

            # Check drop zone is hidden immediately after upload
            assert page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be hidden after upload"

            # Wait for Python round-trip (change → mock_inference → postprocess)
            page.wait_for_timeout(3000)

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
            page.wait_for_timeout(1000)

            # Upload image
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

            # Verify upload succeeded
            assert page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be hidden"

            # Wait for full round-trip
            page.wait_for_timeout(3000)
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
            # (the script tag is Python→JS; JS→Python goes via props.value)
            has_point = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container canvas');
                var ctx = c.getContext('2d');
                // Check center area for non-zero pixels (the point marker)
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
            page.wait_for_timeout(1000)

            # Upload image
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

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
            page.wait_for_timeout(1000)

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


def test_settings_persist_after_image_upload():
    """Color swatches and settings controls should remain visible after image upload and Python round-trip."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Verify color swatches are present before image upload
            initial_obj_swatches = page.evaluate("""() => {
                return document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                ).length;
            }""")
            assert initial_obj_swatches > 0, "Object color swatches should be present initially"

            # Upload image
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

            # Wait for Python round-trip
            page.wait_for_timeout(3000)

            # Color swatches should still be present after round-trip
            post_obj_swatches = page.evaluate("""() => {
                return document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                ).length;
            }""")
            assert post_obj_swatches > 0, "Object color swatches should persist after Python round-trip"

            # Settings bar should be visible (not hidden)
            settings_visible = page.evaluate("""() => {
                var bar = document.querySelector('.sam-prompter-container .settings-bar');
                return bar && !bar.classList.contains('hidden');
            }""")
            assert settings_visible, "Settings bar should be visible after round-trip"

            # Object tabs should still be populated
            has_tabs = page.evaluate("""() => {
                return document.querySelectorAll(
                    '.sam-prompter-container .object-tabs .object-tab'
                ).length;
            }""")
            assert has_tabs > 0, "Object tabs should be present after round-trip"

            browser.close()
    finally:
        demo.close()


def test_color_swatch_clickable_after_round_trip():
    """Color swatches should remain interactive after a Python round-trip."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Upload image and wait for round-trip
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(4500)

            # Click the second object color swatch
            swatch_clicked = page.evaluate("""() => {
                var swatches = document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                );
                if (swatches.length < 2) return false;
                swatches[1].click();
                return true;
            }""")
            assert swatch_clicked, "Should be able to click a color swatch"

            page.wait_for_timeout(500)

            # The clicked swatch should now be active
            active_swatch_index = page.evaluate("""() => {
                var swatches = document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                );
                for (var i = 0; i < swatches.length; i++) {
                    if (swatches[i].classList.contains('active')) return i;
                }
                return -1;
            }""")
            assert active_swatch_index == 1, (
                f"Second swatch (index 1) should be active, got index {active_swatch_index}"
            )

            browser.close()
    finally:
        demo.close()


def test_slider_values_visible_on_initial_load():
    """Point size and mask opacity text values must be visible in the initial state."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(5000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Point size value should show the default (6)
            point_text = page.evaluate("""() => {
                var el = document.querySelector('.sam-prompter-container .point-size-value');
                return el ? el.textContent.trim() : '';
            }""")
            assert point_text == "6", f"Point size value should be '6', got '{point_text}'"

            # Mask opacity value should show the default (40%)
            opacity_text = page.evaluate("""() => {
                var el = document.querySelector('.sam-prompter-container .mask-opacity-value');
                return el ? el.textContent.trim() : '';
            }""")
            assert opacity_text == "40%", f"Mask opacity value should be '40%', got '{opacity_text}'"

            browser.close()
    finally:
        demo.close()


def test_slider_values_persist_after_round_trip():
    """Slider value labels remain visible after an image upload triggers a Python round-trip."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Upload image and wait for round-trip
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(4500)

            # Point size value should still be populated
            point_text = page.evaluate("""() => {
                var el = document.querySelector('.sam-prompter-container .point-size-value');
                return el ? el.textContent.trim() : '';
            }""")
            assert point_text != "", "Point size value should not be empty after round-trip"
            assert point_text == "6", f"Point size value should be '6', got '{point_text}'"

            # Mask opacity value should still be populated
            opacity_text = page.evaluate("""() => {
                var el = document.querySelector('.sam-prompter-container .mask-opacity-value');
                return el ? el.textContent.trim() : '';
            }""")
            assert opacity_text != "", "Mask opacity value should not be empty after round-trip"
            assert opacity_text == "40%", f"Mask opacity value should be '40%', got '{opacity_text}'"

            browser.close()
    finally:
        demo.close()


def test_toolbar_buttons_clickable_without_image():
    """Toolbar buttons (help, settings) should work even when no image is loaded."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Drop zone should be visible (no image loaded)
            assert not page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be visible when no image is loaded"

            # Click the help button — should open the help overlay, not trigger file upload
            page.click(".sam-prompter-container .help-btn")
            page.wait_for_timeout(300)

            help_visible = page.evaluate("""() => {
                var overlay = document.querySelector('.sam-prompter-container .help-overlay');
                return overlay && !overlay.classList.contains('hidden');
            }""")
            assert help_visible, "Help overlay should open when help button is clicked without an image"

            # Close help
            page.click(".sam-prompter-container .help-close-btn")
            page.wait_for_timeout(300)

            # Click the settings gear button — should toggle settings bar
            page.click(".sam-prompter-container .settings-btn")
            page.wait_for_timeout(300)

            settings_hidden = page.evaluate("""() => {
                var bar = document.querySelector('.sam-prompter-container .settings-bar');
                return bar && bar.classList.contains('hidden');
            }""")
            assert settings_hidden, "Settings bar should be hidden after clicking settings button"

            # Click again to re-open
            page.click(".sam-prompter-container .settings-btn")
            page.wait_for_timeout(300)

            settings_visible = page.evaluate("""() => {
                var bar = document.querySelector('.sam-prompter-container .settings-bar');
                return bar && !bar.classList.contains('hidden');
            }""")
            assert settings_visible, "Settings bar should be visible after toggling settings button again"

            browser.close()
    finally:
        demo.close()


def test_settings_interactive_without_image():
    """Color swatches and sliders in settings bar should be interactive without an image."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Click the second object color swatch without any image loaded
            swatch_clicked = page.evaluate("""() => {
                var swatches = document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                );
                if (swatches.length < 2) return false;
                swatches[1].click();
                return true;
            }""")
            assert swatch_clicked, "Should be able to click a color swatch without an image"

            page.wait_for_timeout(300)

            active_index = page.evaluate("""() => {
                var swatches = document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                );
                for (var i = 0; i < swatches.length; i++) {
                    if (swatches[i].classList.contains('active')) return i;
                }
                return -1;
            }""")
            assert active_index == 1, f"Second swatch (index 1) should be active, got index {active_index}"

            browser.close()
    finally:
        demo.close()


def test_object_color_swatch_active_on_initial_load():
    """Object color swatches should show an active indicator immediately on load."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(5000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Exactly one object color swatch should have .active class
            active_count = page.evaluate("""() => {
                return document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch.active'
                ).length;
            }""")
            assert active_count == 1, f"Exactly 1 object swatch should be active on load, got {active_count}"

            browser.close()
    finally:
        demo.close()


def test_zoom_out_to_min_resets_pan_wheel():
    """Zooming out to min (zoom=1) with scroll wheel should reset pan to (0,0)."""
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
            page.wait_for_timeout(1000)

            # Upload image
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

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


def test_clear_object_removes_stale_mask_immediately():
    """Clearing an object should null its mask canvas before the backend responds."""
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
            page.wait_for_timeout(2000)

            # Click canvas to add a foreground point to Object 1
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            page.wait_for_timeout(2500)

            # Add Object 2 and add a point
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(300)
            page.mouse.click(box["x"] + 130, box["y"] + 80)
            page.wait_for_timeout(2500)

            # Both objects should now have masks
            pre = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return {
                    len: s.maskCanvases.length,
                    has0: s.maskCanvases[0] !== null && s.maskCanvases[0] !== undefined,
                    has1: s.maskCanvases[1] !== null && s.maskCanvases[1] !== undefined
                };
            }""")
            assert pre["has0"], "Object 1 should have a mask before clearing"
            assert pre["has1"], "Object 2 should have a mask before clearing"

            # Select Object 1
            page.evaluate("""() => {
                document.querySelectorAll('.sam-prompter-container .object-tab')[0].click();
            }""")
            page.wait_for_timeout(300)

            # Click Clear — mask for Object 1 should be nulled
            page.click(".sam-prompter-container .clear-btn")
            # Wait for backend round-trip to complete
            page.wait_for_timeout(3000)

            post = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                var mc = s.maskCanvases;
                return {
                    len: mc.length,
                    mask0IsNull: mc.length < 1 || mc[0] === null || mc[0] === undefined,
                    has1: mc.length >= 2 && mc[1] !== null && mc[1] !== undefined,
                    obj0Points: s.objects[0].points.length,
                    obj1Points: s.objects[1].points.length
                };
            }""")
            assert post["mask0IsNull"], "Object 1 mask should be null after clear"
            assert post["has1"], (
                f"Object 2 mask should still exist after clearing Object 1 "
                f"(maskCanvases.length={post['len']}, obj0Points={post['obj0Points']}, "
                f"obj1Points={post['obj1Points']})"
            )

            browser.close()
    finally:
        demo.close()


def test_clear_object_preserves_other_object_mask_color():
    """After clearing one object, other objects' masks must keep their own color."""
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
            page.wait_for_timeout(2000)

            # Add a foreground point to Object 1
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            page.wait_for_timeout(2500)

            # Add Object 2 and a point
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(300)
            page.mouse.click(box["x"] + 130, box["y"] + 80)
            page.wait_for_timeout(2500)

            # Record Object 2 color
            obj2_color = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return s.objects[1].color;
            }""")

            # Select Object 1 and clear it
            page.evaluate("""() => {
                document.querySelectorAll('.sam-prompter-container .object-tab')[0].click();
            }""")
            page.wait_for_timeout(300)
            page.click(".sam-prompter-container .clear-btn")
            # Wait for backend round-trip
            page.wait_for_timeout(3000)

            # Object 2's mask should still use Object 2's color
            result = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                var mask1 = s.maskCanvases[1];
                if (!mask1) return {error: 'Object 2 mask is null after round-trip'};
                var ctx = mask1.getContext('2d');
                var d = ctx.getImageData(0, 0, mask1.width, mask1.height).data;
                for (var i = 0; i < d.length; i += 4) {
                    if (d[i+3] > 0) {
                        return {r: d[i], g: d[i+1], b: d[i+2]};
                    }
                }
                return {error: 'No non-transparent pixels in Object 2 mask'};
            }""")
            assert "error" not in result, result.get("error", "")

            # Parse expected RGB from Object 2's hex color
            er = int(obj2_color[1:3], 16)
            eg = int(obj2_color[3:5], 16)
            eb = int(obj2_color[5:7], 16)

            actual = (result["r"], result["g"], result["b"])
            expected = (er, eg, eb)
            assert actual == expected, (
                f"Object 2 mask should use color {obj2_color} "
                f"(R={er},G={eg},B={eb}), got R={result['r']},G={result['g']},B={result['b']}"
            )

            browser.close()
    finally:
        demo.close()


def test_clear_all_removes_all_masks():
    """Clear All should remove all masks and reset to a single empty object."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Upload image and add a point
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(2000)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            page.wait_for_timeout(2500)

            # Verify mask exists
            has_mask = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return s.maskCanvases.length > 0 && s.maskCanvases[0] !== null;
            }""")
            assert has_mask, "Should have a mask before Clear All"

            # Click Clear All
            page.click(".sam-prompter-container .clear-all-btn")
            page.wait_for_timeout(300)

            state = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return {
                    numObjects: s.objects.length,
                    maskLen: s.maskCanvases.length,
                    rawLen: s.rawMasks.length
                };
            }""")
            assert state["numObjects"] == 1, "Should have 1 object after Clear All"
            assert state["maskLen"] == 0, "maskCanvases should be empty after Clear All"
            assert state["rawLen"] == 0, "rawMasks should be empty after Clear All"

            browser.close()
    finally:
        demo.close()


def test_maximize_persists_after_canvas_click():
    """Maximized state should survive clicking the canvas (which triggers a Gradio round-trip)."""
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

            # Click the maximize button
            page.click(".sam-prompter-container .maximize-btn")
            page.wait_for_timeout(300)

            # Verify container is maximized
            is_maximized = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                return c.classList.contains('maximized');
            }""")
            assert is_maximized, "Container should have 'maximized' class after clicking maximize"

            # Click on the canvas to add a point (triggers emitPromptData → Gradio round-trip)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(
                box["x"] + box["width"] / 2,
                box["y"] + box["height"] / 2,
            )

            # Wait for the full Gradio round-trip (3 Svelte phases)
            page.wait_for_timeout(3000)

            # Container should STILL be maximized
            still_maximized = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                return c.classList.contains('maximized');
            }""")
            assert still_maximized, "Container should still have 'maximized' class after canvas click + round-trip"

            # JS state should agree
            state_maximized = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                return c.__samPrompterState.maximized;
            }""")
            assert state_maximized, "state.maximized should still be true after round-trip"

            browser.close()
    finally:
        demo.close()


def test_maximize_canvas_fits_within_wrapper():
    """In maximized mode the canvas should fit within the wrapper (not overflow/clip)."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Upload image
            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(1500)

            # Maximize
            page.click(".sam-prompter-container .maximize-btn")
            page.wait_for_timeout(500)

            # Canvas display rect should fit within the wrapper rect
            fits = page.evaluate("""() => {
                var wrapper = document.querySelector('.sam-prompter-container .canvas-wrapper');
                var canvas = wrapper.querySelector('canvas');
                var wr = wrapper.getBoundingClientRect();
                var cr = canvas.getBoundingClientRect();
                return {
                    canvasW: cr.width, canvasH: cr.height,
                    wrapperW: wr.width, wrapperH: wr.height,
                    fitsWidth: cr.width <= wr.width + 1,
                    fitsHeight: cr.height <= wr.height + 1
                };
            }""")
            assert fits["fitsWidth"], f"Canvas width {fits['canvasW']} should fit in wrapper width {fits['wrapperW']}"
            assert fits["fitsHeight"], (
                f"Canvas height {fits['canvasH']} should fit in wrapper height {fits['wrapperH']}"
            )

            # Click canvas to trigger round-trip, then check again
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(3000)

            fits_after = page.evaluate("""() => {
                var wrapper = document.querySelector('.sam-prompter-container .canvas-wrapper');
                var canvas = wrapper.querySelector('canvas');
                var wr = wrapper.getBoundingClientRect();
                var cr = canvas.getBoundingClientRect();
                return {
                    canvasW: cr.width, canvasH: cr.height,
                    wrapperW: wr.width, wrapperH: wr.height,
                    fitsWidth: cr.width <= wr.width + 1,
                    fitsHeight: cr.height <= wr.height + 1
                };
            }""")
            assert fits_after["fitsWidth"], (
                f"After round-trip: canvas width {fits_after['canvasW']} "
                f"should fit in wrapper width {fits_after['wrapperW']}"
            )
            assert fits_after["fitsHeight"], (
                f"After round-trip: canvas height {fits_after['canvasH']} "
                f"should fit in wrapper height {fits_after['wrapperH']}"
            )

            browser.close()
    finally:
        demo.close()


def test_active_swatch_has_double_ring_indicator():
    """Active swatch should use a double-ring box-shadow visible on any color."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(5000)
            page.goto(url)
            page.wait_for_timeout(1000)

            box_shadow = page.evaluate("""() => {
                var active = document.querySelector(
                    '.sam-prompter-container .color-swatch.active'
                );
                if (!active) return '';
                return window.getComputedStyle(active).boxShadow;
            }""")
            # Computed box-shadow should contain both a white ring and a dark ring
            assert "255, 255, 255" in box_shadow, (
                f"Active swatch box-shadow should contain white ring, got: {box_shadow}"
            )
            assert "0, 0, 0" in box_shadow, f"Active swatch box-shadow should contain dark ring, got: {box_shadow}"

            browser.close()
    finally:
        demo.close()


def test_debug_data_persists_after_canvas_click():
    """Debug JSON component must retain prompt data after a canvas click round-trip.

    Regression test: when SamPrompter was wired with .change() (instead of
    .input()), Gradio re-fired the handler when applying the output to the
    same component.  The second invocation received the postprocessed value
    (no ``prompts`` key), returned ``None, "{}"``, and cleared the debug
    component.
    """
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
            page.wait_for_timeout(2000)

            # Click on the canvas to add a foreground point
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(
                box["x"] + box["width"] / 2,
                box["y"] + box["height"] / 2,
            )

            # Wait for the full round-trip
            page.wait_for_timeout(3000)

            # Debug JSON component should contain prompt data (not be empty)
            debug_text = page.evaluate("""() => {
                var jsonEl = document.querySelector('[data-testid="json"]');
                return jsonEl ? jsonEl.textContent.trim() : '';
            }""")
            assert debug_text != "", "Debug JSON should not be empty after click"
            assert debug_text != "{}", "Debug JSON should not be '{}' after click"
            assert "prompts" in debug_text, "Debug JSON should contain 'prompts' key"

            browser.close()
    finally:
        demo.close()


def test_masks_not_cleared_during_canvas_click_round_trip():
    """Masks must not be temporarily cleared when a canvas click triggers a Gradio round-trip.

    Regression test: the Svelte three-phase re-evaluation used to echo back the
    JS prompt data (no ``masks`` key) in Phase 1, which caused handleDataUpdate()
    to clear ``state.maskCanvases``.  This produced a visible flicker on every click.
    """
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

            # Click on the canvas to add a foreground point (triggers round-trip → masks)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            page.mouse.click(cx, cy)

            # Wait for full round-trip so masks are decoded
            page.wait_for_timeout(3000)

            mask_count_before = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return s.maskCanvases.filter(function(c) { return c !== null; }).length;
            }""")
            assert mask_count_before > 0, "Should have at least one mask after first click"

            # Install a flicker detector: intercepts maskCanvases assignments
            # and records whether the array was ever emptied during a round-trip.
            page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                window.__maskFlickerLog = [];
                var origMaskCanvases = s.maskCanvases;
                Object.defineProperty(s, 'maskCanvases', {
                    get: function() { return origMaskCanvases; },
                    set: function(v) {
                        origMaskCanvases = v;
                        var count = v.filter(function(c) { return c !== null; }).length;
                        window.__maskFlickerLog.push(count);
                    },
                    configurable: true
                });
            }""")

            # Click again at a slightly different position to trigger another round-trip
            page.mouse.click(cx + 20, cy + 10)
            page.wait_for_timeout(3000)

            # Check that masks were never fully cleared during the round-trip
            flicker_log = page.evaluate("window.__maskFlickerLog")
            had_zero = any(count == 0 for count in flicker_log)
            assert not had_zero, (
                f"Masks were temporarily cleared during round-trip (flicker). maskCanvases count log: {flicker_log}"
            )

            # Verify masks are present after the round-trip
            mask_count_after = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return s.maskCanvases.filter(function(c) { return c !== null; }).length;
            }""")
            assert mask_count_after > 0, "Should have masks after second click"

            browser.close()
    finally:
        demo.close()


def test_slider_thumb_centered_on_track():
    """Range slider thumb should be vertically centered on the track."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(5000)
            page.goto(url)
            page.wait_for_timeout(1000)

            result = page.evaluate("""() => {
                var slider = document.querySelector('.sam-prompter-container .sp-slider');
                var style = window.getComputedStyle(slider);
                return {
                    appearance: style.getPropertyValue('appearance')
                        || style.getPropertyValue('-webkit-appearance')
                };
            }""")
            assert result["appearance"] == "none", f"Slider appearance should be 'none', got: {result['appearance']}"

            alignment = page.evaluate("""() => {
                var sliders = document.querySelectorAll('.sam-prompter-container .sp-slider');
                var results = [];
                for (var i = 0; i < sliders.length; i++) {
                    var rect = sliders[i].getBoundingClientRect();
                    results.push({ index: i, inputHeight: rect.height });
                }

                // Gradio injects css_template inside a nesting rule
                // (#html-xxx { ... }) in a <style> tag.  Pseudo-element
                // properties are not accessible via getComputedStyle in
                // Chromium, so verify the thumb margin-top rule by
                // searching the raw style text.
                var hasThumbMargin = false;
                var styles = document.querySelectorAll('style');
                for (var s = 0; s < styles.length; s++) {
                    var text = styles[s].textContent;
                    if (text.indexOf('-webkit-slider-thumb') !== -1
                        && text.indexOf('margin-top') !== -1
                        && text.indexOf('-5px') !== -1) {
                        hasThumbMargin = true;
                    }
                }
                return { sliders: results, hasThumbMargin: hasThumbMargin };
            }""")

            for info in alignment["sliders"]:
                assert info["inputHeight"] <= 6, (
                    f"Slider {info['index']}: input height should be ~4px (track), got {info['inputHeight']}px"
                )
            assert alignment["hasThumbMargin"], "CSS rule for ::-webkit-slider-thumb should contain margin-top: -5px"

            browser.close()
    finally:
        demo.close()


def test_no_backend_call_on_image_upload():
    """Uploading an image without any prompts should not trigger a backend call."""
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
            page.wait_for_timeout(500)

            # isProcessing should never become true (no emit happened)
            state = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                var s = c.__samPrompterState;
                return {
                    isProcessing: s.isProcessing,
                    hasImage: !!s.image
                };
            }""")
            assert state["hasImage"], "Image should be loaded on canvas"
            assert not state["isProcessing"], "isProcessing should be false — no backend call without prompts"

            # Wait and confirm isProcessing stays false (no backend call)
            page.wait_for_timeout(3000)

            state_after = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                var s = c.__samPrompterState;
                return { isProcessing: s.isProcessing };
            }""")
            assert not state_after["isProcessing"], "isProcessing should still be false after waiting"

            browser.close()
    finally:
        demo.close()


def test_no_backend_call_on_add_empty_object():
    """Adding an empty object should not trigger a backend call or reset masks."""
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
            page.wait_for_timeout(2000)

            # Add a foreground point to Object 1 (triggers backend)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            page.wait_for_timeout(3000)

            # Verify Object 1 has a mask
            pre = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return {
                    masks: s.maskCanvases.filter(function(c) { return c != null; }).length,
                    isProcessing: s.isProcessing
                };
            }""")
            assert pre["masks"] > 0, "Object 1 should have a mask"
            assert not pre["isProcessing"], "Should not be processing before add"

            # Click Add Object — should NOT trigger backend
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(200)

            state = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return {
                    isProcessing: s.isProcessing,
                    numObjects: s.objects.length,
                    activeIndex: s.activeObjectIndex,
                    masks: s.maskCanvases.filter(function(c) { return c != null; }).length
                };
            }""")
            assert not state["isProcessing"], "isProcessing should be false — adding empty object should not emit"
            assert state["numObjects"] == 2, "Should have 2 objects"
            assert state["activeIndex"] == 1, "New object should be active"
            assert state["masks"] > 0, "Existing masks should be preserved after adding empty object"

            browser.close()
    finally:
        demo.close()
