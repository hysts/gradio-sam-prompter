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
