"""Playwright UI tests for the 'N' keyboard shortcut (add new object)."""

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


def _get_object_count(page: Page) -> int:
    return page.evaluate("""() => {
        var c = document.querySelector('.sam-prompter-container');
        return c.__samPrompterState.objects.length;
    }""")


def _hover_container(page: Page) -> None:
    """Move mouse over the container to activate keyboard shortcuts."""
    container = page.locator(".sam-prompter-container")
    box = container.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def test_n_key_adds_object_after_hover():
    """Pressing 'n' while hovering over the container should add a new object."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            before = _get_object_count(page)
            assert before == 1, f"Should start with 1 object, got {before}"

            _hover_container(page)
            page.keyboard.press("n")
            page.wait_for_timeout(300)

            after = _get_object_count(page)
            assert after == 2, f"Should have 2 objects after pressing N, got {after}"

            browser.close()
    finally:
        demo.close()


def test_n_key_after_canvas_click():
    """Pressing 'n' after clicking on the canvas should add a new object."""
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

            before = _get_object_count(page)
            assert before == 1, f"Should start with 1 object, got {before}"

            # Click on the canvas (mouse ends up over container)
            canvas = page.locator(".sam-prompter-container canvas")
            box = canvas.bounding_box()
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(500)

            # Press 'n' — mouse is still over the container
            page.keyboard.press("n")
            page.wait_for_timeout(300)

            after = _get_object_count(page)
            assert after == 2, f"Should have 2 objects after pressing N, got {after}"

            browser.close()
    finally:
        demo.close()


def test_n_key_after_image_upload():
    """Pressing 'n' after image upload while hovering should add object."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            page.evaluate(UPLOAD_IMAGE_JS)
            page.wait_for_timeout(2000)

            before = _get_object_count(page)
            assert before == 1, f"Should start with 1 object, got {before}"

            _hover_container(page)
            page.keyboard.press("n")
            page.wait_for_timeout(300)

            after = _get_object_count(page)
            assert after == 2, f"Should have 2 objects after pressing N, got {after}"

            browser.close()
    finally:
        demo.close()


def test_n_key_ignored_when_mouse_outside():
    """Pressing 'n' when the mouse is NOT over the container should not add an object."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            before = _get_object_count(page)
            assert before == 1, f"Should start with 1 object, got {before}"

            # Move mouse outside the container (to top-left corner of viewport)
            page.mouse.move(5, 5)
            page.wait_for_timeout(100)

            page.keyboard.press("n")
            page.wait_for_timeout(300)

            after = _get_object_count(page)
            assert after == 1, f"Should still have 1 object when mouse is outside, got {after}"

            browser.close()
    finally:
        demo.close()


def test_n_key_after_clicking_add_button():
    """Pressing 'n' after clicking + Add button should add another object."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Click the + Add button (mouse is now over the container)
            page.click(".sam-prompter-container .add-object-btn")
            page.wait_for_timeout(300)

            mid = _get_object_count(page)
            assert mid == 2, f"Should have 2 objects after clicking + Add, got {mid}"

            # Press 'n' — mouse is still over the container
            page.keyboard.press("n")
            page.wait_for_timeout(300)

            after = _get_object_count(page)
            assert after == 3, f"Should have 3 objects after pressing N, got {after}"

            browser.close()
    finally:
        demo.close()


def test_n_key_while_slider_focused():
    """Pressing 'n' while a slider has focus (mouse over container) should add object."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            before = _get_object_count(page)
            assert before == 1, f"Should start with 1 object, got {before}"

            # Click on the slider (focus goes to INPUT, mouse is over container)
            page.click(".sam-prompter-container .point-size-slider")
            page.wait_for_timeout(300)

            page.keyboard.press("n")
            page.wait_for_timeout(300)

            after = _get_object_count(page)
            assert after == 2, f"Should have 2 objects after pressing N while slider focused, got {after}"

            browser.close()
    finally:
        demo.close()


def test_multiple_n_presses():
    """Pressing 'n' multiple times should add multiple objects up to the limit."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(url)
            page.wait_for_timeout(1000)

            _hover_container(page)

            for _i in range(3):
                page.keyboard.press("n")
                page.wait_for_timeout(100)

            after = _get_object_count(page)
            assert after == 4, f"Should have 4 objects after pressing N 3 times, got {after}"

            browser.close()
    finally:
        demo.close()
