# SAM Prompter

Interactive Gradio component for [Segment Anything Model (SAM)](https://segment-anything.com/) prompt input and mask visualization. Built on `gr.HTML` with vanilla JavaScript — no custom JS framework required.

Users can upload images, place foreground/background points, draw bounding boxes, and view predicted segmentation masks in real time, all within a single Gradio component.

## Features

- **Point prompts** — Left-click for foreground, right-click for background
- **Box prompts** — Click and drag to draw bounding boxes
- **Multi-object** — Manage up to 8 independent segmentation objects with color-coded prompts
- **Mask overlay** — Real-time display of predicted masks with adjustable opacity
- **Cutout view** — Foreground-only display with checkerboard background
- **Zoom & pan** — Scroll to zoom (1-20×), middle-button or Space+drag to move; double-click to reset
- **Move mode** — Dedicated toggle button or hold Space for temporary move mode
- **Undo** — Per-object undo history
- **Clear prompts** — Toolbar buttons to clear the active object, all objects, or remove the image entirely; `SamPrompter.clear()` API for programmatic clearing (undoable)
- **Prompt deletion** — Alt+click to remove individual points or boxes
- **Processing lock** — Canvas blocks new input while waiting for a Python response
- **Settings bar** — Per-object color swatches, point size, box outline width, and mask opacity sliders
- **Coordinate display** — Live pixel coordinates shown on hover
- **Maximize mode** — Full-screen canvas toggle
- **Keyboard shortcuts** — Comprehensive shortcuts for all actions (press `?` to view)
- **Examples gallery** — `gr.Examples` support with image thumbnails via `process_example()`
- **State persistence** — UI state survives Gradio round-trips via MutationObserver

## Installation

Requires Python >= 3.12.

```bash
pip install .
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install .
```

## Quick Start

```python
import gradio as gr
from sam_prompter import SamPrompter


def predict(data):
    if data is None:
        return None

    image_path = data.get("imagePath")
    if not image_path:
        return None

    prompts = data.get("prompts", [])

    # Run your SAM model here to get masks
    # masks = sam_model.predict(image_path, prompts)

    image = Image.open(image_path)
    masks_list = [{"mask": mask_array} for mask_array in masks]
    return (image, masks_list)


with gr.Blocks() as demo:
    prompter = SamPrompter(label="SAM Prompter")
    prompter.input(fn=predict, inputs=prompter, outputs=prompter)

demo.launch()
```

## API

### `SamPrompter`

```python
SamPrompter(
    value=None,
    *,
    label: str | None = None,
    max_objects: int = 8,       # Maximum number of segmentation objects
    point_radius: int = 6,      # Display radius of prompt points (px)
    mask_alpha: float = 0.4,    # Default mask overlay opacity (0-1)
    **kwargs,                   # Forwarded to gr.HTML
)
```

**Input format** (`preprocess`): The component's `preprocess` method automatically parses the JSON string from the frontend into a `dict | None`. Event handlers receive a dict with keys `prompts` (always present), plus `imagePath` and `imageSize` when the user uploaded an image. Returns `None` for empty, invalid, or echo-back values.

**Output format** (`postprocess`): Accepts either a plain image or an `(image, masks_list)` tuple.

- **Plain image** — File path (`str` / `Path`), `PIL.Image`, or `numpy.ndarray`. Displayed with no masks.
- **Tuple** `(image, masks_list)` where:
  - `image` — File path, `PIL.Image`, or `numpy.ndarray`
  - `masks_list` — List of dicts, each with:
    - `"mask"`: `numpy.ndarray` or `PIL.Image` (H x W binary mask)
    - `"color"`: `[R, G, B]` (optional, auto-assigned from palette)
    - `"alpha"`: `float` (optional, defaults to `mask_alpha`)

### Clear buttons

The toolbar provides three clear buttons:

| Button | Scope | Effect |
|--------|-------|--------|
| **Clear** | Active object | Removes points and boxes from the current object (undoable with `Z`) |
| **Clear All** | All objects | Resets to a single empty object and removes all masks |
| **Remove image** (`×`) | Entire canvas | Removes the uploaded image, all objects, and all masks |

Each button is automatically disabled when there is nothing to clear.

### `SamPrompter.clear`

```python
SamPrompter.clear(
    value=None,       # image or (image, masks_list), same formats as postprocess
    *,
    max_objects=None,  # dynamically update the maximum number of objects
) -> _ClearPrompts
```

Returns a wrapper that, when passed as a return value from an event handler, clears all user-drawn prompts (points and boxes) on the frontend.

| Variant | Prompts | Masks | Image |
|---------|---------|-------|-------|
| `clear()` | Cleared | Cleared | Kept as-is |
| `clear(image)` | Cleared | Cleared | Replaced |
| `clear((image, masks_list))` | Cleared | Replaced | Replaced |

```python
prompter = SamPrompter()


# Clear prompts and masks, keep the current image as-is
def on_clear():
    return SamPrompter.clear()


# Clear prompts and masks, re-send the image
def on_clear_with_image(image):
    return SamPrompter.clear(image)


# Clear prompts, re-send image with new masks, and change max objects
def on_reset(image, masks):
    return SamPrompter.clear((image, masks), max_objects=4)
```

### `parse_prompt_value`

```python
parse_prompt_value(value: str | None) -> dict | None
```

Parses the JSON string emitted by the component into a dict. Returns `None` when the value is empty, unparseable, or missing the `prompts` key.

> **Note:** `SamPrompter.preprocess` calls this function automatically, so manual invocation is normally unnecessary.

**Returned dict structure:**

```json
{
    "imagePath": "/tmp/gradio/.../image.png",
    "imageSize": {"width": 1280, "height": 720},
    "prompts": [
        {
            "points": [[x, y], ...],
            "labels": [1, 0, ...],
            "boxes": [[x1, y1, x2, y2], ...]
        }
    ]
}
```

- `imagePath` — Server filesystem path to the uploaded image; present only when the user uploaded an image
- `imageSize` — Present only when the user uploaded an image
- `labels` — `1` = foreground, `0` = background

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Left Click | Add foreground point |
| Right Click | Add background point |
| Left Drag | Draw bounding box |
| Alt + Click | Delete nearest point / box |
| Scroll | Zoom in / out |
| Middle Drag | Pan |
| Double-click | Reset zoom (move mode) |
| `1`-`8` | Switch active object |
| `N` | Add new object |
| `Z` | Undo last prompt |
| `M` | Toggle mask display |
| `I` | Toggle image display |
| `H` | Toggle object visibility |
| `C` | Toggle cutout view |
| `V` | Toggle settings bar |
| `F` | Toggle maximize mode |
| `+` / `=` / `-` / `0` | Zoom in / out / reset |
| `Space` (hold) | Temporary move mode |
| `Delete` / `Backspace` | Delete active object |
| `Escape` | Cancel box drawing / close help / exit maximize |
| `?` | Show help overlay |

## Mask Encoding

Masks are transferred between Python and JavaScript using column-major Run-Length Encoding (RLE) for efficiency:

```json
{"counts": [n1, n2, ...], "size": [H, W]}
```

The `_encode_mask_to_rle` function flattens the mask in Fortran (column-major) order and encodes alternating runs of 0s and 1s.

## Demo

```bash
uv run python demo/showcase/app.py
```

The showcase demo provides preset examples: single mask, multi-object masks, custom colors, and varying alpha — plus interactive mock inference.

Model-specific demos are also available (require `transformers`, `torch`, and `spaces`):

```bash
uv run python demo/sam/app.py     # SAM (facebook/sam-vit-base)
uv run python demo/sam2/app.py    # SAM2 (facebook/sam2.1-hiera-small)
uv run python demo/sam3/app.py    # SAM3 (facebook/sam3)
```

## Testing

The project includes Playwright-based UI tests and Python unit tests.

```bash
uv run playwright install chromium
uv run pytest tests/
```

## Development

```bash
uv sync
uv run ruff format .
uv run ruff check . --fix
```

## License

[MIT](LICENSE)
