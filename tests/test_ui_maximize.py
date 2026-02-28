"""Playwright UI tests for maximize mode."""

from _demo import demo
from _helpers import upload_test_image, wait_for_container, wait_for_inference_complete
from playwright.sync_api import sync_playwright


def test_maximize_persists_after_canvas_click():
    """Maximized state should survive clicking the canvas (which triggers a Gradio round-trip)."""
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

            # Click the maximize button
            page.click(".sam-prompter-container .maximize-btn")
            page.wait_for_timeout(300)

            # Verify element wrapper is maximized
            is_maximized = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                return c.parentElement.classList.contains('sp-maximized');
            }""")
            assert is_maximized, "Element wrapper should have 'sp-maximized' class after clicking maximize"

            # Click on the canvas to add a point (triggers emitPromptData -> Gradio round-trip)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(
                box["x"] + box["width"] / 2,
                box["y"] + box["height"] / 2,
            )

            # Wait for the full Gradio round-trip (3 Svelte phases)
            wait_for_inference_complete(page)

            # Element wrapper should STILL be maximized
            still_maximized = page.evaluate("""() => {
                var c = document.querySelector('.sam-prompter-container');
                return c.parentElement.classList.contains('sp-maximized');
            }""")
            assert still_maximized, (
                "Element wrapper should still have 'sp-maximized' class after canvas click + round-trip"
            )

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
            wait_for_container(page)

            # Upload image
            upload_test_image(page)

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
            wait_for_inference_complete(page)

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
