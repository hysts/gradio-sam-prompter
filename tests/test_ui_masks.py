"""Playwright UI tests for mask clearing and persistence."""

from _demo import demo
from _helpers import (
    upload_test_image,
    wait_for_container,
    wait_for_inference_complete,
    wait_for_masks_present,
)
from playwright.sync_api import sync_playwright


def test_clear_object_removes_stale_mask_immediately():
    """Clearing an object should null its mask canvas before the backend responds."""
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

            # Click canvas to add a foreground point to Object 1
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            wait_for_inference_complete(page)
            wait_for_masks_present(page)

            # Add Object 2 and add a point
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(300)
            page.mouse.click(box["x"] + 130, box["y"] + 80)
            wait_for_inference_complete(page)

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

            # Click Clear -- mask for Object 1 should be nulled
            page.click(".sam-prompter-container .clear-btn")
            # Wait for backend round-trip to complete
            wait_for_inference_complete(page)

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
            wait_for_container(page)

            # Upload image
            upload_test_image(page)

            # Add a foreground point to Object 1
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            wait_for_inference_complete(page)
            wait_for_masks_present(page)

            # Add Object 2 and a point
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(300)
            page.mouse.click(box["x"] + 130, box["y"] + 80)
            wait_for_inference_complete(page)

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
            wait_for_inference_complete(page)

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
            wait_for_container(page)

            # Upload image and add a point
            upload_test_image(page)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + 50, box["y"] + 40)
            wait_for_inference_complete(page)
            wait_for_masks_present(page)

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
            wait_for_container(page)

            # Upload image
            upload_test_image(page)

            # Click on the canvas to add a foreground point (triggers round-trip -> masks)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            page.mouse.click(cx, cy)

            # Wait for full round-trip so masks are decoded
            wait_for_inference_complete(page)
            wait_for_masks_present(page)

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
            wait_for_inference_complete(page)

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
