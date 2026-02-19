"""Unit tests for sam_prompter Python helpers and SamPrompter methods."""

import json
import tempfile
from pathlib import Path

import gradio as gr
import numpy as np
from PIL import Image

from sam_prompter import (
    _COLOR_PALETTE,
    SamPrompter,
    _encode_mask_to_rle,
    _hex_to_rgb,
    _load_image,
    parse_prompt_value,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_image(directory: str | Path, name: str = "test.png", w: int = 100, h: int = 80) -> Path:
    path = Path(directory) / name
    Image.new("RGB", (w, h), color=(100, 150, 200)).save(path)
    return path


def _decode_rle(rle: dict) -> np.ndarray:
    """Decode RLE back to a binary mask for round-trip verification."""
    h, w = rle["size"]
    flat = np.zeros(h * w, dtype=np.uint8)
    pos = 0
    for i, count in enumerate(rle["counts"]):
        if i % 2 == 1:
            flat[pos : pos + count] = 1
        pos += count
    return flat.reshape((h, w), order="F")


# ===========================================================================
# _load_image
# ===========================================================================


def test_load_image_from_path_string():
    with tempfile.TemporaryDirectory() as d:
        p = _make_test_image(d)
        img = _load_image(str(p))
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.size == (100, 80)


def test_load_image_from_path_object():
    with tempfile.TemporaryDirectory() as d:
        p = _make_test_image(d)
        img = _load_image(p)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"


def test_load_image_from_pil_converts_to_rgb():
    rgba = Image.new("RGBA", (50, 40), color=(100, 150, 200, 128))
    img = _load_image(rgba)
    assert img.mode == "RGB"
    assert img.size == (50, 40)


def test_load_image_from_pil_rgb_passthrough():
    original = Image.new("RGB", (50, 40), color=(100, 150, 200))
    img = _load_image(original)
    assert img.mode == "RGB"
    assert img.size == (50, 40)


def test_load_image_from_numpy():
    arr = np.full((40, 50, 3), [100, 150, 200], dtype=np.uint8)
    img = _load_image(arr)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.size == (50, 40)


# ===========================================================================
# _hex_to_rgb
# ===========================================================================


def test_hex_to_rgb_standard():
    assert _hex_to_rgb("#FF6B6B") == [255, 107, 107]


def test_hex_to_rgb_black_white():
    assert _hex_to_rgb("#000000") == [0, 0, 0]
    assert _hex_to_rgb("#FFFFFF") == [255, 255, 255]


def test_hex_to_rgb_palette_coverage():
    for hex_color in _COLOR_PALETTE:
        rgb = _hex_to_rgb(hex_color)
        assert len(rgb) == 3
        assert all(0 <= c <= 255 for c in rgb)


# ===========================================================================
# _encode_mask_to_rle
# ===========================================================================


def test_rle_all_zeros():
    mask = np.zeros((3, 4), dtype=np.uint8)
    rle = _encode_mask_to_rle(mask)
    assert rle["size"] == [3, 4]
    assert rle["counts"] == [12]


def test_rle_all_ones():
    mask = np.ones((3, 4), dtype=np.uint8)
    rle = _encode_mask_to_rle(mask)
    assert rle["size"] == [3, 4]
    assert rle["counts"][0] == 0
    assert sum(rle["counts"]) == 12


def test_rle_column_pattern():
    """First column all 1s, rest all 0s (column-major order)."""
    mask = np.zeros((3, 3), dtype=np.uint8)
    mask[:, 0] = 1
    rle = _encode_mask_to_rle(mask)
    assert rle["size"] == [3, 3]
    # Column-major flat: [1,1,1, 0,0,0, 0,0,0] → [0, 3, 6]
    assert rle["counts"] == [0, 3, 6]


def test_rle_single_pixel():
    mask = np.zeros((5, 5), dtype=np.uint8)
    mask[2, 3] = 1
    rle = _encode_mask_to_rle(mask)
    assert rle["size"] == [5, 5]
    decoded = _decode_rle(rle)
    np.testing.assert_array_equal(decoded, mask)


def test_rle_round_trip_random():
    rng = np.random.default_rng(42)
    mask = (rng.random((64, 48)) > 0.5).astype(np.uint8)
    rle = _encode_mask_to_rle(mask)
    assert rle["size"] == [64, 48]
    decoded = _decode_rle(rle)
    np.testing.assert_array_equal(decoded, mask)


# ===========================================================================
# parse_prompt_value
# ===========================================================================


def test_parse_prompt_value_none():
    assert parse_prompt_value(None) is None


def test_parse_prompt_value_empty_string():
    assert parse_prompt_value("") is None


def test_parse_prompt_value_invalid_json():
    assert parse_prompt_value("{broken") is None


def test_parse_prompt_value_json_without_prompts_key():
    assert parse_prompt_value('{"image": "test.png"}') is None


def test_parse_prompt_value_non_dict_json():
    assert parse_prompt_value("[1, 2, 3]") is None


def test_parse_prompt_value_valid():
    data = {"prompts": [{"points": [[10, 20]], "labels": [1]}], "imagePath": "/data/img.png"}
    result = parse_prompt_value(json.dumps(data))
    assert result is not None
    assert result["prompts"] == data["prompts"]
    assert result["imagePath"] == "/data/img.png"


# ===========================================================================
# SamPrompter.preprocess
# ===========================================================================


def test_preprocess_none():
    with gr.Blocks():
        comp = SamPrompter()
    assert comp.preprocess(None) is None


def test_preprocess_empty_string():
    with gr.Blocks():
        comp = SamPrompter()
    assert comp.preprocess("") is None


def test_preprocess_invalid_json():
    with gr.Blocks():
        comp = SamPrompter()
    assert comp.preprocess("{broken") is None


def test_preprocess_echo_postprocessed():
    """Postprocessed output (has 'image' but no 'prompts') returns None."""
    with gr.Blocks():
        comp = SamPrompter()
    assert comp.preprocess('{"image": "/gradio_api/file=x.webp", "width": 100}') is None


def test_preprocess_valid():
    data = {"prompts": [{"points": [[10, 20]], "labels": [1]}], "imagePath": "/data/img.png"}
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.preprocess(json.dumps(data))
    assert result is not None
    assert result["prompts"] == data["prompts"]
    assert result["imagePath"] == "/data/img.png"


# ===========================================================================
# SamPrompter.postprocess
# ===========================================================================


def test_postprocess_none():
    with gr.Blocks():
        comp = SamPrompter()
    assert comp.postprocess(None) is None


def test_postprocess_plain_image_path():
    with tempfile.TemporaryDirectory() as d:
        p = _make_test_image(d, w=120, h=90)
        with gr.Blocks():
            comp = SamPrompter()
        result = comp.postprocess(str(p))
    payload = json.loads(result)
    assert payload["width"] == 120
    assert payload["height"] == 90
    assert payload["masks"] == []
    assert payload["image"].startswith("/gradio_api/file=")
    assert payload["colors"] == _COLOR_PALETTE


def test_postprocess_pil_image():
    img = Image.new("RGB", (60, 40), color=(200, 100, 50))
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess(img)
    payload = json.loads(result)
    assert payload["width"] == 60
    assert payload["height"] == 40
    assert payload["masks"] == []


def test_postprocess_numpy_array():
    arr = np.full((40, 60, 3), 128, dtype=np.uint8)
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess(arr)
    payload = json.loads(result)
    assert payload["width"] == 60
    assert payload["height"] == 40


def test_postprocess_with_masks():
    img = Image.new("RGB", (100, 80), color=(100, 150, 200))
    mask = np.zeros((80, 100), dtype=np.uint8)
    mask[10:30, 20:50] = 1
    masks_list = [{"mask": mask}]
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess((img, masks_list))
    payload = json.loads(result)
    assert len(payload["masks"]) == 1
    m = payload["masks"][0]
    assert "rle" in m
    assert m["rle"]["size"] == [80, 100]
    assert m["color"] == _hex_to_rgb(_COLOR_PALETTE[0])
    assert m["alpha"] == 0.4


def test_postprocess_mask_rle_round_trip():
    """Verify the encoded mask in postprocess output decodes back correctly."""
    img = Image.new("RGB", (50, 40), color=(0, 0, 0))
    mask = np.zeros((40, 50), dtype=np.uint8)
    mask[5:15, 10:30] = 1
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess((img, [{"mask": mask}]))
    rle = json.loads(result)["masks"][0]["rle"]
    decoded = _decode_rle(rle)
    np.testing.assert_array_equal(decoded, mask)


def test_postprocess_custom_mask_color_and_alpha():
    img = Image.new("RGB", (50, 40), color=(0, 0, 0))
    mask = np.ones((40, 50), dtype=np.uint8)
    masks_list = [{"mask": mask, "color": [255, 0, 0], "alpha": 0.8}]
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess((img, masks_list))
    m = json.loads(result)["masks"][0]
    assert m["color"] == [255, 0, 0]
    assert m["alpha"] == 0.8


def test_postprocess_multiple_masks_use_palette_colors():
    img = Image.new("RGB", (50, 40), color=(0, 0, 0))
    masks_list = [{"mask": np.ones((40, 50), dtype=np.uint8)} for _ in range(3)]
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess((img, masks_list))
    payload = json.loads(result)
    assert len(payload["masks"]) == 3
    for i in range(3):
        assert payload["masks"][i]["color"] == _hex_to_rgb(_COLOR_PALETTE[i])


def test_postprocess_pil_mask():
    """Mask provided as PIL Image instead of numpy array."""
    img = Image.new("RGB", (50, 40), color=(0, 0, 0))
    mask_pil = Image.new("L", (50, 40), color=255)
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess((img, [{"mask": mask_pil}]))
    payload = json.loads(result)
    assert len(payload["masks"]) == 1
    assert payload["masks"][0]["rle"]["size"] == [40, 50]


# ===========================================================================
# SamPrompter.clear
# ===========================================================================


def test_clear_none_returns_clear_prompts_only():
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess(SamPrompter.clear())
    payload = json.loads(result)
    assert payload == {"clearPrompts": True}


def test_clear_with_image_includes_clear_flag():
    img = Image.new("RGB", (60, 40), color=(0, 0, 0))
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess(SamPrompter.clear(img))
    payload = json.loads(result)
    assert payload["clearPrompts"] is True
    assert payload["width"] == 60
    assert payload["height"] == 40
    assert payload["masks"] == []
    assert payload["image"].startswith("/gradio_api/file=")


def test_clear_with_image_and_masks():
    img = Image.new("RGB", (50, 40), color=(0, 0, 0))
    mask = np.ones((40, 50), dtype=np.uint8)
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess(SamPrompter.clear((img, [{"mask": mask}])))
    payload = json.loads(result)
    assert payload["clearPrompts"] is True
    assert len(payload["masks"]) == 1
    assert payload["image"].startswith("/gradio_api/file=")


def test_postprocess_without_clear_has_no_flag():
    img = Image.new("RGB", (60, 40), color=(0, 0, 0))
    with gr.Blocks():
        comp = SamPrompter()
    result = comp.postprocess(img)
    payload = json.loads(result)
    assert "clearPrompts" not in payload


# ===========================================================================
# SamPrompter.api_info
# ===========================================================================


def test_api_info_structure():
    with gr.Blocks():
        comp = SamPrompter()
    info = comp.api_info()
    assert info["type"] == "object"
    assert "description" in info
    assert "prompts" in info["description"]
