"""Minimal Gradio demo with max_objects=2 for boundary tests."""

import json

import gradio as gr
import numpy as np
from _mock_inference import apply_bg_points, apply_boxes, apply_fg_points
from PIL import Image

from sam_prompter import SamPrompter


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
        has_fg = apply_fg_points(mask, obj, h, w)
        has_box = apply_boxes(mask, obj, h, w)
        apply_bg_points(mask, obj, h, w)
        if has_fg or has_box:
            masks.append({"mask": mask})

    return (image, masks), json.dumps(data, indent=2)


with gr.Blocks(title="SAM Prompter Max2 Test") as demo:
    prompter = SamPrompter(label="SAM Prompter", max_objects=2)
    debug_json = gr.JSON(label="Prompt Data (debug)")
    prompter.input(fn=mock_inference, inputs=prompter, outputs=[prompter, debug_json])
