from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gradio as gr
import numpy as np
from gradio import processing_utils
from PIL import Image

_STATIC_DIR = Path(__file__).parent / "static"

_COLOR_PALETTE = [
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
    "#96CEB4",
    "#FFEAA7",
    "#DDA0DD",
    "#98D8C8",
    "#F7DC6F",
]


class _ClearPrompts:
    """Wrapper that signals the frontend to clear all user-drawn prompts."""

    __slots__ = ("value", "max_objects")

    def __init__(
        self,
        value: str | Path | Image.Image | np.ndarray | tuple[Any, list[dict[str, Any]]] | None = None,
        *,
        max_objects: int | None = None,
    ) -> None:
        self.value = value
        self.max_objects = max_objects


def _load_image(source: str | Path | Image.Image | np.ndarray) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if isinstance(source, np.ndarray):
        return Image.fromarray(source).convert("RGB")
    return Image.open(source).convert("RGB")


def _save_image_to_cache(img: Image.Image, cache_dir: str) -> str:
    cached_path = processing_utils.save_pil_to_cache(img, cache_dir, format="webp")
    return f"/gradio_api/file={cached_path}"


def _encode_mask_to_rle(mask: np.ndarray) -> dict[str, Any]:
    h, w = mask.shape[:2]
    flat = mask.astype(np.uint8).ravel(order="F")
    change_idx = np.flatnonzero(np.diff(flat))
    runs = np.diff(np.concatenate([[-1], change_idx, [len(flat) - 1]]))
    counts = runs.tolist()
    if flat[0] == 1:
        counts = [0, *counts]
    return {"counts": counts, "size": [h, w]}


class SamPrompter(gr.HTML):
    def __init__(
        self,
        value: str | Path | Image.Image | np.ndarray | tuple[Any, list[dict[str, Any]]] | None = None,
        *,
        label: str | None = None,
        max_objects: int = 8,
        point_radius: int = 6,
        mask_alpha: float = 0.4,
        **kwargs: Any,  # noqa: ANN401 - forwarded to gr.HTML
    ) -> None:
        self.max_objects = max_objects
        self.point_radius = point_radius
        self.mask_alpha = mask_alpha

        html_template = (_STATIC_DIR / "template.html").read_text(encoding="utf-8")
        css_template = (_STATIC_DIR / "style.css").read_text(encoding="utf-8")
        js_on_load = (_STATIC_DIR / "script.js").read_text(encoding="utf-8")

        html_template = html_template.replace("${max_objects}", str(max_objects))
        html_template = html_template.replace("${point_radius}", str(point_radius))
        html_template = html_template.replace("${mask_alpha}", str(mask_alpha))

        super().__init__(
            value=value,
            label=label,
            show_label=label is not None,
            container=label is not None,
            html_template=html_template,
            css_template=css_template,
            js_on_load=js_on_load,
            **kwargs,
        )

    @staticmethod
    def clear(
        value: str | Path | Image.Image | np.ndarray | tuple[Any, list[dict[str, Any]]] | None = None,
        *,
        max_objects: int | None = None,
    ) -> _ClearPrompts:
        """Return a value that clears all user-drawn prompts (points and boxes).

        Pass this as a return value from an event handler to clear the prompts
        while optionally keeping (or replacing) the displayed image and masks.

        * ``clear()`` — clears prompts and masks; the current image stays.
        * ``clear(image)`` — clears prompts and masks; re-sends the image.
        * ``clear((image, masks))`` — clears prompts; re-sends image with
          new masks.

        Parameters
        ----------
        value:
            Image or (image, masks) tuple to display after clearing.
        max_objects:
            If given, dynamically update the maximum number of objects the
            frontend allows.

        Example usage::

            prompter = SamPrompter()


            # Clear prompts and masks, keep the current image as-is
            def on_clear():
                return SamPrompter.clear()


            # Clear prompts and masks, re-send the image
            def on_clear_with_image(image):
                return SamPrompter.clear(image)
        """
        return _ClearPrompts(value, max_objects=max_objects)

    def postprocess(
        self,
        value: str | Path | Image.Image | np.ndarray | tuple[Any, list[dict[str, Any]]] | _ClearPrompts | None,
    ) -> str | None:
        clear_prompts = False
        max_objects_override: int | None = None
        if isinstance(value, _ClearPrompts):
            clear_prompts = True
            max_objects_override = value.max_objects
            value = value.value

        if value is None:
            if clear_prompts:
                result: dict[str, Any] = {"clearPrompts": True}
                if max_objects_override is not None:
                    result["maxObjects"] = max_objects_override
                return json.dumps(result)
            return None

        if isinstance(value, tuple):
            image_source, masks_list = value
        else:
            image_source, masks_list = value, []
        img = _load_image(image_source)
        image_url = _save_image_to_cache(img, self.GRADIO_CACHE)

        encoded_masks = []
        for i, mask_info in enumerate(masks_list):
            mask_array = mask_info["mask"]
            if isinstance(mask_array, Image.Image):
                mask_array = np.array(mask_array)
            binary = (mask_array > 0).astype(np.uint8)
            color = mask_info.get("color") or _hex_to_rgb(_COLOR_PALETTE[i % len(_COLOR_PALETTE)])
            alpha = mask_info.get("alpha", self.mask_alpha)
            encoded_masks.append(
                {
                    "rle": _encode_mask_to_rle(binary),
                    "color": color,
                    "alpha": alpha,
                }
            )

        payload = {
            "image": image_url,
            "width": img.width,
            "height": img.height,
            "masks": encoded_masks,
            "colors": _COLOR_PALETTE,
        }
        if clear_prompts:
            payload["clearPrompts"] = True
        if max_objects_override is not None:
            payload["maxObjects"] = max_objects_override
        return json.dumps(payload)

    def preprocess(self, payload: Any) -> dict[str, Any] | None:  # noqa: ANN401 - Gradio override
        """Parse the raw JSON string from the frontend into a dict.

        Delegates to :func:`parse_prompt_value` so that event handlers
        receive a ready-to-use ``dict | None`` instead of a raw string.
        """
        return parse_prompt_value(payload)

    def process_example(self, value: Any) -> str | None:  # noqa: ANN401 - Gradio override
        """Return an HTML ``<img>`` tag for the ``gr.Examples`` gallery.

        ``gr.Examples`` calls ``process_example()`` (via ``as_example()``) to
        obtain display HTML for the examples gallery.  The default
        implementation delegates to ``postprocess()``, which returns a JSON
        payload — resulting in raw JSON text in the gallery.  This override
        produces a proper thumbnail instead.
        """
        if value is None:
            return None
        image_source = value[0] if isinstance(value, tuple) else value
        img = _load_image(image_source)
        url = _save_image_to_cache(img, self.GRADIO_CACHE)
        return f'<img src="{url}" alt="example" style="max-width:100%;height:auto;display:block;border-radius:4px;">'

    def api_info(self) -> dict[str, Any]:
        return {
            "type": "object",
            "description": (
                "JSON string with SAM prompter data. "
                "Input from JS: {imagePath?: string, imageSize?: {width, height}, "
                "prompts: [{points: [[x,y],...], labels: [1,0,...], boxes: [[x1,y1,x2,y2],...]},...]}. "
                "Output from Python: a plain image (str path, PIL Image, or ndarray) "
                "or a tuple (image, masks_list) where masks_list is "
                "[{rle: {counts: [int,...], size: [H,W]}, color: [R,G,B], alpha: float},...]. "
                "Serialized as {image: string, width: int, height: int, masks: [...], colors: [...]}"
            ),
        }


def parse_prompt_value(value: str | None) -> dict[str, Any] | None:
    """Parse the JSON string emitted by SamPrompter into a dict.

    Returns a dict with keys: ``prompts`` (always present),
    ``imagePath`` and ``imageSize`` (present when the user uploaded
    an image directly into the component).  Returns ``None`` when
    *value* is empty, unparseable, or missing the ``prompts`` key
    (e.g. a round-trip echo of the postprocessed output).

    .. note::

        ``SamPrompter.preprocess`` calls this function automatically,
        so event handlers receive ``dict | None`` directly.  Manual
        invocation is normally unnecessary.
    """
    if not value:
        return None
    try:
        data = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or "prompts" not in data:
        return None
    return data


def _hex_to_rgb(hex_color: str) -> list[int]:
    h = hex_color.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)]
