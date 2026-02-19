"""Playwright UI tests for platform-aware Alt/Option key label in help overlay."""

from _demo import demo
from playwright.sync_api import sync_playwright


def test_help_shows_alt_on_non_mac():
    """On non-Mac platforms the help overlay should display 'Alt + Click'."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(5000)
            page.goto(url)
            page.wait_for_timeout(1000)

            # Open help overlay
            page.click(".sam-prompter-container .help-btn")
            page.wait_for_timeout(300)

            kbd_text = page.evaluate("""() => {
                var kbds = document.querySelectorAll(
                    '.sam-prompter-container .help-overlay kbd'
                );
                for (var i = 0; i < kbds.length; i++) {
                    if (kbds[i].textContent.indexOf('Click') !== -1
                        && (kbds[i].textContent.indexOf('Alt') !== -1
                            || kbds[i].textContent.indexOf('Option') !== -1)) {
                        return kbds[i].textContent;
                    }
                }
                return '';
            }""")
            assert "Alt" in kbd_text, f"Expected 'Alt' on Linux, got: {kbd_text!r}"
            assert "Option" not in kbd_text, f"Should not show 'Option' on Linux, got: {kbd_text!r}"

            browser.close()
    finally:
        demo.close()


def test_help_shows_option_on_mac():
    """On Mac the help overlay should display '⌥ Option + Click'."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(5000)

            # Spoof navigator.platform to MacIntel before any scripts run
            page.add_init_script("""
                Object.defineProperty(navigator, 'platform', {
                    get: function() { return 'MacIntel'; }
                });
            """)

            page.goto(url)
            page.wait_for_timeout(1000)

            # Open help overlay
            page.click(".sam-prompter-container .help-btn")
            page.wait_for_timeout(300)

            kbd_text = page.evaluate("""() => {
                var kbds = document.querySelectorAll(
                    '.sam-prompter-container .help-overlay kbd'
                );
                for (var i = 0; i < kbds.length; i++) {
                    if (kbds[i].textContent.indexOf('Click') !== -1
                        && (kbds[i].textContent.indexOf('Alt') !== -1
                            || kbds[i].textContent.indexOf('Option') !== -1)) {
                        return kbds[i].textContent;
                    }
                }
                return '';
            }""")
            assert "⌥ Option" in kbd_text, f"Expected '⌥ Option' on Mac, got: {kbd_text!r}"
            assert kbd_text.startswith("⌥ Option"), f"Should start with '⌥ Option', got: {kbd_text!r}"

            context.close()
            browser.close()
    finally:
        demo.close()
