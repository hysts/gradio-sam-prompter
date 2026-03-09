"""Playwright UI tests for debug data persistence and no-backend-call behavior."""

from _demo import demo
from _helpers import (
    upload_test_image,
    wait_for_container,
    wait_for_inference_complete,
    wait_for_masks_present,
)
from playwright.sync_api import sync_playwright


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
            wait_for_container(page)

            # Upload image
            upload_test_image(page)

            # Click on the canvas to add a foreground point
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(
                box["x"] + box["width"] / 2,
                box["y"] + box["height"] / 2,
            )

            # Wait for the full round-trip
            wait_for_inference_complete(page)

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


def test_no_backend_call_on_image_upload():
    """Uploading an image without any prompts should not trigger a backend call."""
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
            assert not state["isProcessing"], "isProcessing should be false -- no backend call without prompts"

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


def test_object_tab_click_switches_active_object():
    """Clicking an object tab should switch the active object index."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Add a second object
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(200)

            # Active should be object 1 (index 1)
            assert page.evaluate("""() => {
                return document.querySelector('.sam-prompter-container').__samPrompterState.activeObjectIndex;
            }""") == 1

            # Click the first object tab
            page.evaluate("""() => {
                document.querySelectorAll('.sam-prompter-container .object-tab')[0].click();
            }""")
            page.wait_for_timeout(200)

            result = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                var tab = document.querySelectorAll('.sam-prompter-container .object-tab')[0];
                return {
                    activeIndex: s.activeObjectIndex,
                    tabHasActiveClass: tab.classList.contains('active')
                };
            }""")
            assert result["activeIndex"] == 0, f"Active index should be 0, got {result['activeIndex']}"
            assert result["tabHasActiveClass"], "First tab should have .active class"

            browser.close()
    finally:
        demo.close()


def test_visibility_toggle_hides_object():
    """Clicking the visibility toggle on a tab should toggle the object's visible state."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Object 0 should be visible by default
            assert page.evaluate("""() => {
                return document.querySelector('.sam-prompter-container').__samPrompterState.objects[0].visible;
            }"""), "Object 0 should be visible initially"

            # Click the visibility toggle on the first tab
            page.evaluate("""() => {
                document.querySelector('.sam-prompter-container .object-tab .visibility-toggle').click();
            }""")
            page.wait_for_timeout(200)

            result = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                var tab = document.querySelector('.sam-prompter-container .object-tab');
                return {
                    visible: s.objects[0].visible,
                    tabHasHiddenClass: tab.classList.contains('hidden-object')
                };
            }""")
            assert not result["visible"], "Object 0 should be hidden after toggle"
            assert result["tabHasHiddenClass"], "Tab should have .hidden-object class"

            browser.close()
    finally:
        demo.close()


def test_delete_tab_removes_object():
    """Clicking the delete button on a tab should remove that object."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            wait_for_container(page)

            # Add two more objects (3 total)
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(100)
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(200)

            assert page.evaluate("""() => {
                return document.querySelector('.sam-prompter-container').__samPrompterState.objects.length;
            }""") == 3, "Should have 3 objects"

            # Click the delete button on the second tab (index 1)
            page.evaluate("""() => {
                var btn = document.querySelector(
                    '.sam-prompter-container .object-tab [data-delete="1"]'
                );
                btn.click();
            }""")
            page.wait_for_timeout(200)

            result = page.evaluate("""() => {
                var s = document.querySelector('.sam-prompter-container').__samPrompterState;
                return {
                    numObjects: s.objects.length,
                    numTabs: document.querySelectorAll('.sam-prompter-container .object-tab').length
                };
            }""")
            assert result["numObjects"] == 2, f"Should have 2 objects after delete, got {result['numObjects']}"
            assert result["numTabs"] == 2, f"Should have 2 tabs after delete, got {result['numTabs']}"

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
            wait_for_container(page)

            # Upload image
            upload_test_image(page)

            # Add a foreground point to Object 1 (triggers backend)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            wait_for_inference_complete(page)
            wait_for_masks_present(page)

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

            # Click Add Object -- should NOT trigger backend
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
            assert not state["isProcessing"], "isProcessing should be false -- adding empty object should not emit"
            assert state["numObjects"] == 2, "Should have 2 objects"
            assert state["activeIndex"] == 1, "New object should be active"
            assert state["masks"] > 0, "Existing masks should be preserved after adding empty object"

            browser.close()
    finally:
        demo.close()
