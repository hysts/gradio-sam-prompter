import json
from collections.abc import Callable

import gradio as gr
import numpy as np
from PIL import Image, ImageDraw

from sam_prompter import SamPrompter

MOCK_MASK_RADIUS = 50


def _make_sample_image(width: int = 640, height: int = 480) -> Image.Image:
    """Create a sample image with geometric shapes for demonstration."""
    img = Image.new("RGB", (width, height), "#4a90d9")
    draw = ImageDraw.Draw(img)
    draw.ellipse([150, 80, 350, 280], fill="#e74c3c")
    draw.rectangle([400, 100, 560, 280], fill="#2ecc71")
    draw.ellipse([80, 300, 250, 420], fill="#f1c40f")
    draw.rectangle([340, 320, 540, 440], fill="#9b59b6")
    return img


def _ellipse_mask(cx: int, cy: int, rx: int, ry: int, h: int, w: int) -> np.ndarray:
    yy, xx = np.ogrid[:h, :w]
    return (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0).astype(np.uint8)


def _rect_mask(x1: int, y1: int, x2: int, y2: int, h: int, w: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y1:y2, x1:x2] = 1
    return mask


# ---------------------------------------------------------------------------
# Preset examples
# ---------------------------------------------------------------------------

IMG_W, IMG_H = 640, 480


def _make_single_mask() -> tuple[Image.Image, list[dict]]:
    """One mask covering the red circle."""
    return _make_sample_image(), [{"mask": _ellipse_mask(250, 180, 100, 100, IMG_H, IMG_W)}]


def _make_multi_object() -> tuple[Image.Image, list[dict]]:
    """Four masks, one per shape — auto-assigned palette colors."""
    return _make_sample_image(), [
        {"mask": _ellipse_mask(250, 180, 100, 100, IMG_H, IMG_W)},
        {"mask": _rect_mask(400, 100, 560, 280, IMG_H, IMG_W)},
        {"mask": _ellipse_mask(165, 360, 85, 60, IMG_H, IMG_W)},
        {"mask": _rect_mask(340, 320, 540, 440, IMG_H, IMG_W)},
    ]


def _make_custom_colors() -> tuple[Image.Image, list[dict]]:
    """Two masks with explicit colors."""
    return _make_sample_image(), [
        {"mask": _ellipse_mask(250, 180, 100, 100, IMG_H, IMG_W), "color": [255, 215, 0]},
        {"mask": _rect_mask(400, 100, 560, 280, IMG_H, IMG_W), "color": [0, 191, 255]},
    ]


def _make_varying_alpha() -> tuple[Image.Image, list[dict]]:
    """Three masks with different opacity levels."""
    return _make_sample_image(), [
        {"mask": _ellipse_mask(250, 180, 100, 100, IMG_H, IMG_W), "alpha": 0.8},
        {"mask": _rect_mask(400, 100, 560, 280, IMG_H, IMG_W), "alpha": 0.4},
        {"mask": _ellipse_mask(165, 360, 85, 60, IMG_H, IMG_W), "alpha": 0.15},
    ]


_EXAMPLE_BUILDERS: dict[str, Callable[[], tuple[Image.Image, list[dict]]]] = {
    "Single mask": _make_single_mask,
    "Multi-object (4 masks)": _make_multi_object,
    "Custom colors": _make_custom_colors,
    "Varying alpha": _make_varying_alpha,
}


# ---------------------------------------------------------------------------
# Mock inference (generates circle/rectangle masks from prompts)
# ---------------------------------------------------------------------------


def _apply_fg_points(mask: np.ndarray, obj: dict, h: int, w: int) -> bool:
    has_content = False
    for i, pt in enumerate(obj.get("points", [])):
        label = obj["labels"][i] if i < len(obj.get("labels", [])) else 1
        if label == 1:
            yy, xx = np.ogrid[:h, :w]
            dist = np.sqrt((xx - pt[0]) ** 2 + (yy - pt[1]) ** 2)
            mask[dist <= MOCK_MASK_RADIUS] = 1
            has_content = True
    return has_content


def _apply_boxes(mask: np.ndarray, obj: dict, h: int, w: int) -> bool:
    has_content = False
    for box in obj.get("boxes", []):
        x1, y1, x2, y2 = box
        x1, x2 = max(0, min(x1, w)), max(0, min(x2, w))
        y1, y2 = max(0, min(y1, h)), max(0, min(y2, h))
        mask[int(y1) : int(y2), int(x1) : int(x2)] = 1
        has_content = True
    return has_content


def _apply_bg_points(mask: np.ndarray, obj: dict, h: int, w: int) -> None:
    for i, pt in enumerate(obj.get("points", [])):
        label = obj["labels"][i] if i < len(obj.get("labels", [])) else 1
        if label == 0:
            yy, xx = np.ogrid[:h, :w]
            dist = np.sqrt((xx - pt[0]) ** 2 + (yy - pt[1]) ** 2)
            mask[dist <= MOCK_MASK_RADIUS] = 0


def mock_inference(
    data: dict | None,
) -> tuple[tuple[Image.Image, list[dict]] | None, str]:
    if data is None:
        return None, "{}"

    image_path = data.get("imagePath")
    if not image_path:
        return None, json.dumps(data, indent=2)

    image = Image.open(image_path).convert("RGB")
    prompts = data.get("prompts", [])
    if not prompts:
        return (image, []), json.dumps(data, indent=2)

    w, h = image.size
    masks = []
    for obj in prompts:
        mask = np.zeros((h, w), dtype=np.uint8)
        has_fg = _apply_fg_points(mask, obj, h, w)
        has_box = _apply_boxes(mask, obj, h, w)
        _apply_bg_points(mask, obj, h, w)
        if has_fg or has_box:
            masks.append({"mask": mask})

    return (image, masks), json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


def get_example(choice: str) -> tuple[Image.Image, list[dict]] | None:
    builder = _EXAMPLE_BUILDERS.get(choice)
    if builder is None:
        return None
    return builder()


initial_value = get_example("Multi-object (4 masks)")

with gr.Blocks(title="SAM Prompter Showcase") as demo:
    gr.Markdown(
        "# SAM Prompter\n"
        "Select a preset to preview mask overlays, or drop your own image and draw prompts "
        "(left-click foreground, right-click background, drag for box). "
        "Mock inference generates circle/box masks."
    )

    prompter = SamPrompter(value=initial_value, label="SAM Prompter")

    selector = gr.Radio(
        choices=[
            "Single mask",
            "Multi-object (4 masks)",
            "Custom colors",
            "Varying alpha",
            "Clear",
        ],
        value="Multi-object (4 masks)",
        label="Preset examples",
    )
    debug_json = gr.JSON(label="Prompt Data (debug)")

    selector.input(fn=get_example, inputs=selector, outputs=prompter)
    prompter.input(fn=mock_inference, inputs=prompter, outputs=[prompter, debug_json])

if __name__ == "__main__":
    demo.launch()
