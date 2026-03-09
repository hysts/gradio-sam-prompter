"""Playwright UI tests for settings panel, swatches, sliders, and toolbar buttons."""

from _demo import demo
from _helpers import upload_test_image, wait_for_container, wait_for_inference_complete
from playwright.sync_api import sync_playwright


def test_settings_persist_after_image_upload():
    """Color swatches and settings controls should remain visible after image upload and Python round-trip."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Verify color swatches are present before image upload
            initial_obj_swatches = page.evaluate("""() => {
                return document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                ).length;
            }""")
            assert initial_obj_swatches > 0, "Object color swatches should be present initially"

            # Upload image
            upload_test_image(page)

            # Wait for Python round-trip
            wait_for_inference_complete(page)

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
            wait_for_container(page)

            # Upload image and wait for round-trip
            upload_test_image(page)
            wait_for_inference_complete(page)

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
            wait_for_container(page)

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
            wait_for_container(page)

            # Upload image and wait for round-trip
            upload_test_image(page)
            wait_for_inference_complete(page)

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
            wait_for_container(page)

            # Drop zone should be visible (no image loaded)
            assert not page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be visible when no image is loaded"

            # Click the help button -- should open the help overlay, not trigger file upload
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

            # Click the settings gear button -- should toggle settings bar
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
            wait_for_container(page)

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
            wait_for_container(page)

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


def test_color_swatches_pre_rendered_with_data_attributes():
    """All 12 color swatches should be pre-rendered with data-color attributes."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(5000)
            page.goto(url)
            wait_for_container(page)

            info = page.evaluate("""() => {
                var swatches = document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                );
                var colors = [];
                for (var i = 0; i < swatches.length; i++) {
                    colors.push(swatches[i].getAttribute('data-color'));
                }
                return { count: swatches.length, colors: colors };
            }""")
            assert info["count"] == 12, f"Expected 12 color swatches, got {info['count']}"
            for i, color in enumerate(info["colors"]):
                assert color is not None, f"Swatch {i} should have a data-color attribute"
                assert color.startswith("#"), f"Swatch {i} data-color should be hex, got {color!r}"

            browser.close()
    finally:
        demo.close()


def test_color_swatch_click_updates_object_state():
    """Clicking a swatch should update the active object's color in JS state."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(5000)
            page.goto(url)
            wait_for_container(page)

            result = page.evaluate("""() => {
                var swatches = document.querySelectorAll(
                    '.sam-prompter-container .obj-color-swatches .color-swatch'
                );
                if (swatches.length < 3) return null;
                var container = document.querySelector('.sam-prompter-container');
                var colorBefore = container.__samPrompterState.objects[0].color;
                var targetColor = swatches[2].getAttribute('data-color');
                swatches[2].click();
                var colorAfter = container.__samPrompterState.objects[0].color;
                return {
                    colorBefore: colorBefore,
                    targetColor: targetColor,
                    colorAfter: colorAfter
                };
            }""")
            assert result is not None, "Should have at least 3 swatches"
            assert result["colorAfter"] == result["targetColor"], (
                f"Object color should change to {result['targetColor']}, "
                f"got {result['colorAfter']} (was {result['colorBefore']})"
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
            wait_for_container(page)

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


def test_slider_thumb_centered_on_track():
    """Range slider thumb should be vertically centered on the track."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(5000)
            page.goto(url)
            wait_for_container(page)

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
