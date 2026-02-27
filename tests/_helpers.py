"""Shared test helpers for Playwright E2E tests.

Centralises the ``UPLOAD_IMAGE_JS`` constant, image creation utilities,
and condition-based wait functions so that individual test files stay
focused on assertions rather than setup boilerplate.
"""

from pathlib import Path

from PIL import Image
from playwright.sync_api import Page

# ---------------------------------------------------------------------------
# Synthetic image upload (DataTransfer API)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Test-image factory (for unit tests)
# ---------------------------------------------------------------------------


def make_test_image(directory: str | Path, name: str = "test.png", w: int = 100, h: int = 80) -> Path:
    """Create a solid-color PNG in *directory* and return its path."""
    path = Path(directory) / name
    Image.new("RGB", (w, h), color=(100, 150, 200)).save(path)
    return path


# ---------------------------------------------------------------------------
# Condition-based wait helpers
# ---------------------------------------------------------------------------

_CONTAINER_SEL = ".sam-prompter-container"


def wait_for_container(page: Page, *, timeout: float = 10_000) -> None:
    """Wait until the SamPrompter container element is attached to the DOM."""
    page.wait_for_selector(_CONTAINER_SEL, timeout=timeout)


def wait_for_image_loaded(page: Page, *, timeout: float = 10_000) -> None:
    """Wait until the component reports an image is present."""
    page.wait_for_function(
        """() => {
            var c = document.querySelector('.sam-prompter-container');
            return c && c.__samPrompterState && !!c.__samPrompterState.image;
        }""",
        timeout=timeout,
    )


def wait_for_inference_complete(page: Page, *, timeout: float = 15_000) -> None:
    """Wait until ``isProcessing`` becomes false (inference round-trip done)."""
    page.wait_for_function(
        """() => {
            var c = document.querySelector('.sam-prompter-container');
            return c && c.__samPrompterState && !c.__samPrompterState.isProcessing;
        }""",
        timeout=timeout,
    )


def wait_for_masks_present(page: Page, *, timeout: float = 15_000) -> None:
    """Wait until at least one non-null mask canvas exists."""
    page.wait_for_function(
        """() => {
            var c = document.querySelector('.sam-prompter-container');
            if (!c || !c.__samPrompterState) return false;
            var mc = c.__samPrompterState.maskCanvases;
            return mc.some(function(m) { return m !== null; });
        }""",
        timeout=timeout,
    )


def upload_test_image(page: Page) -> None:
    """Inject a synthetic image and wait until the component has rendered it.

    After the image is loaded the component schedules ``renderAll()`` via
    ``requestAnimationFrame``, which calls ``syncVisibility()`` to hide the
    drop zone.  We wait for that rAF-deferred render to complete so callers
    can assert on the visible state immediately.
    """
    page.evaluate(UPLOAD_IMAGE_JS)
    wait_for_image_loaded(page)
    # renderAll (which hides the drop zone) runs on the next animation frame
    page.evaluate("() => new Promise(r => requestAnimationFrame(r))")
