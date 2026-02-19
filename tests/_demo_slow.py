"""Gradio demo with slow mock inference for processing-lock tests.

The inference function adds a 1-second delay when actual prompts are
present, giving Playwright enough time to interact with the UI while
isProcessing is true.  Initial image loads (empty prompts) are fast.
"""

import json
import time

import gradio as gr
import numpy as np
from PIL import Image

from sam_prompter import SamPrompter

_MOCK_MASK_RADIUS = 50
_INFERENCE_DELAY = 1.0


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


def mock_slow_inference(
    data: dict | None,
) -> tuple[tuple[Image.Image, list[dict]] | None, str]:
    if data is None:
        return None, "{}"

    image_path = data.get("imagePath")
    if not image_path:
        return None, json.dumps(data, indent=2)

    image = Image.open(image_path).convert("RGB")
    prompts = data.get("prompts", [])

    # Delay only when actual prompts exist (not the initial image load)
    has_prompts = any(obj.get("points") or obj.get("boxes") for obj in prompts)
    if has_prompts:
        time.sleep(_INFERENCE_DELAY)

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


with gr.Blocks(title="SAM Prompter Slow Test") as demo:
    prompter = SamPrompter(label="SAM Prompter")
    debug_json = gr.JSON(label="Prompt Data (debug)")
    prompter.input(fn=mock_slow_inference, inputs=prompter, outputs=[prompter, debug_json])
