"""Gradio demo with gr.Examples for testing SamPrompter examples gallery."""

import tempfile
from pathlib import Path

import gradio as gr
from PIL import Image

from sam_prompter import SamPrompter

_EXAMPLES_DIR = Path(tempfile.mkdtemp(prefix="sam_prompter_ex_"))


def _make_image(name: str, color: tuple[int, int, int]) -> str:
    path = _EXAMPLES_DIR / name
    Image.new("RGB", (200, 150), color=color).save(path)
    return str(path)


_IMAGES = [
    _make_image("a.png", (200, 100, 100)),
    _make_image("b.png", (100, 200, 100)),
]

with gr.Blocks(title="SAM Prompter Examples Test") as demo:
    prompter = SamPrompter(label="SAM Prompter")
    gr.Examples(examples=[[p] for p in _IMAGES], inputs=[prompter])
