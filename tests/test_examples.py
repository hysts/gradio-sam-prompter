"""Tests for SamPrompter.process_example and gr.Examples integration."""

import re
import tempfile
from pathlib import Path

import gradio as gr
import numpy as np
from _demo_examples import demo
from PIL import Image
from playwright.sync_api import sync_playwright

from sam_prompter import SamPrompter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_image(directory: str | Path, name: str = "test.png", w: int = 100, h: int = 80) -> Path:
    path = Path(directory) / name
    Image.new("RGB", (w, h), color=(100, 150, 200)).save(path)
    return path


# ---------------------------------------------------------------------------
# Unit tests — process_example()
# ---------------------------------------------------------------------------


def test_process_example_none_returns_none():
    with gr.Blocks():
        comp = SamPrompter()
    assert comp.process_example(None) is None


def test_process_example_path_returns_img_tag():
    with tempfile.TemporaryDirectory() as d:
        p = _make_test_image(d)
        with gr.Blocks():
            comp = SamPrompter()
        result = comp.process_example(str(p))
    assert result is not None
    assert result.startswith("<img ")
    assert 'alt="example"' in result
    assert "max-height:5rem" in result
    assert "object-fit:contain" in result
    assert "border-radius:4px" in result


def test_process_example_pil_returns_img_tag():
    img = Image.new("RGB", (100, 80), color=(100, 150, 200))
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.process_example(img)
    assert result is not None
    assert result.startswith("<img ")


def test_process_example_numpy_returns_img_tag():
    arr = np.full((80, 100, 3), 128, dtype=np.uint8)
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.process_example(arr)
    assert result is not None
    assert result.startswith("<img ")


def test_process_example_tuple_uses_first_element():
    """(image, masks) tuple — only image is used for the thumbnail."""
    with tempfile.TemporaryDirectory() as d:
        p = _make_test_image(d)
        with gr.Blocks():
            comp = SamPrompter()
        result = comp.process_example((str(p), [{"mask": np.zeros((80, 100), dtype=np.uint8)}]))
    assert result is not None
    assert result.startswith("<img ")


def test_process_example_cached_file_is_webp():
    """The cached thumbnail should be saved as webp."""
    with tempfile.TemporaryDirectory() as d:
        p = _make_test_image(d)
        with gr.Blocks():
            comp = SamPrompter()
        result = comp.process_example(str(p))
    m = re.search(r'src="(/gradio_api/file=([^"]+))"', result)
    assert m is not None
    cached_path = m.group(2)
    assert Path(cached_path).exists()
    assert cached_path.endswith(".webp")


# ---------------------------------------------------------------------------
# E2E tests — gr.Examples gallery UX
# ---------------------------------------------------------------------------


def test_examples_gallery_shows_thumbnails():
    """The examples gallery must show <img> thumbnails, not raw JSON text."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10_000)
            page.goto(url)
            page.wait_for_timeout(2000)

            count = page.locator('img[alt="example"]').count()
            assert count >= 2, f"Expected >= 2 example thumbnails, got {count}"

            browser.close()
    finally:
        demo.close()


def test_examples_thumbnails_not_oversized():
    """Example thumbnails must be height-constrained (max 5rem ≈ 80px)."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10_000)
            page.goto(url)
            page.wait_for_timeout(2000)

            imgs = page.locator('img[alt="example"]')
            count = imgs.count()
            assert count >= 2, f"Expected >= 2 example thumbnails, got {count}"

            for i in range(count):
                box = imgs.nth(i).bounding_box()
                assert box is not None, f"Thumbnail {i} has no bounding box"
                assert box["height"] <= 100, (
                    f"Thumbnail {i} is too tall: {box['height']:.0f}px "
                    f"(expected <= 100px)"
                )

            browser.close()
    finally:
        demo.close()


def test_examples_click_loads_image():
    """Clicking an example thumbnail must load the image into SamPrompter."""
    _, url, _ = demo.launch(prevent_thread_lock=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10_000)
            page.goto(url)
            page.wait_for_timeout(2000)

            # Drop zone visible before loading
            assert page.evaluate(
                "!document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be visible initially"

            # Click the first example thumbnail
            page.locator('img[alt="example"]').first.click()
            page.wait_for_timeout(3000)

            # Drop zone should be hidden (image loaded)
            assert page.evaluate(
                "document.querySelector('.sam-prompter-container .drop-zone').classList.contains('hidden')"
            ), "Drop zone should be hidden after clicking an example"

            browser.close()
    finally:
        demo.close()
