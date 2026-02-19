"""Gradio demo with clear buttons for SamPrompter.clear() API tests.

Provides three clear buttons that exercise each variant of the API:
- Clear (keep image): ``SamPrompter.clear()``
- Clear (re-send image): ``SamPrompter.clear(image)``
- Clear (re-send with masks): ``SamPrompter.clear((image, masks))``
"""

import json

import gradio as gr
import numpy as np
from PIL import Image

from sam_prompter import SamPrompter, _ClearPrompts

_MOCK_MASK_RADIUS = 50


def _apply_fg_points(mask: np.ndarray, obj: dict, h: int, w: int) -> bool:
    has_content = False
    for i, pt in enumerate(obj.get("points", [])):
        label = obj["labels"][i] if i < len(obj.get("labels", [])) else 1
        if label == 1:
            yy, xx = np.ogrid[:h, :w]
            dist = np.sqrt((xx - pt[0]) ** 2 + (yy - pt[1]) ** 2)
            mask[dist <= _MOCK_MASK_RADIUS] = 1
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
            mask[dist <= _MOCK_MASK_RADIUS] = 0


def mock_inference(
    data: dict | None,
) -> tuple[tuple[Image.Image, list[dict]] | None, Image.Image | None, str]:
    if data is None:
        return None, None, "{}"

    image_path = data.get("imagePath")
    if not image_path:
        return None, None, json.dumps(data, indent=2)

    image = Image.open(image_path).convert("RGB")
    prompts = data.get("prompts", [])
    if not prompts:
        return (image, []), image, json.dumps(data, indent=2)

    w, h = image.size
    masks = []
    for obj in prompts:
        mask = np.zeros((h, w), dtype=np.uint8)
        has_fg = _apply_fg_points(mask, obj, h, w)
        has_box = _apply_boxes(mask, obj, h, w)
        _apply_bg_points(mask, obj, h, w)
        if has_fg or has_box:
            masks.append({"mask": mask})

    return (image, masks), image, json.dumps(data, indent=2)


def on_clear_keep_image() -> _ClearPrompts:
    return SamPrompter.clear()


def on_clear_resend_image(img: Image.Image | None) -> _ClearPrompts:
    if img is None:
        return SamPrompter.clear()
    return SamPrompter.clear(img)


def on_clear_resend_with_masks(img: Image.Image | None) -> _ClearPrompts:
    if img is None:
        return SamPrompter.clear()
    w, h = img.size
    mask = np.ones((h, w), dtype=np.uint8)
    return SamPrompter.clear((img, [{"mask": mask}]))


with gr.Blocks(title="SAM Prompter Clear API Test") as demo:
    prompter = SamPrompter(label="SAM Prompter")
    image_state = gr.State(None)
    debug_json = gr.JSON(label="Prompt Data (debug)")

    with gr.Row():
        clear_keep_btn = gr.Button("Clear (keep image)", elem_id="clear-keep")
        clear_resend_btn = gr.Button("Clear (re-send image)", elem_id="clear-resend")
        clear_masks_btn = gr.Button("Clear (re-send with masks)", elem_id="clear-masks")

    prompter.input(
        fn=mock_inference,
        inputs=prompter,
        outputs=[prompter, image_state, debug_json],
    )
    clear_keep_btn.click(fn=on_clear_keep_image, outputs=[prompter])
    clear_resend_btn.click(fn=on_clear_resend_image, inputs=[image_state], outputs=[prompter])
    clear_masks_btn.click(fn=on_clear_resend_with_masks, inputs=[image_state], outputs=[prompter])
