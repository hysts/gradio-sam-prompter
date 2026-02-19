import json
from typing import Any

import gradio as gr
import numpy as np
import spaces
import torch
from PIL import Image
from sam_prompter import SamPrompter
from transformers import Sam2Model, Sam2Processor

MODEL_ID = "facebook/sam2.1-hiera-small"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
dtype = torch.float16 if device.type == "cuda" else torch.float32

print(f"Loading {MODEL_ID} on {device} ({dtype}) ...")  # noqa: T201
processor: Sam2Processor = Sam2Processor.from_pretrained(MODEL_ID)
model: Sam2Model = Sam2Model.from_pretrained(MODEL_ID, torch_dtype=dtype).to(device).eval()
print("Model loaded.")  # noqa: T201


def _compute_image_embeddings(image: Image.Image) -> list[torch.Tensor]:
    """Compute image embeddings (no caching — safe for concurrent requests)."""
    inputs = processor(images=image, return_tensors="pt").to(device=device, dtype=dtype)
    with torch.no_grad():
        return model.get_image_embeddings(inputs["pixel_values"])


def _predict_mask_for_object(
    obj: dict[str, Any],
    image: Image.Image,
    image_embeddings: list[torch.Tensor],
) -> np.ndarray | None:
    """Run the mask decoder for a single object's prompts.

    Returns a binary (H, W) uint8 array, or None if the object has no prompts.
    """
    points = obj.get("points", [])
    labels = obj.get("labels", [])
    boxes = obj.get("boxes", [])

    if not points and not boxes:
        return None

    # Build processor kwargs. We pass the image so the processor can compute
    # the correct coordinate scaling, but we discard pixel_values and reuse
    # cached image embeddings instead.
    proc_kwargs: dict[str, Any] = {"images": image, "return_tensors": "pt"}
    if points:
        proc_kwargs["input_points"] = [[points]]
        proc_kwargs["input_labels"] = [[labels]]
    if boxes:
        proc_kwargs["input_boxes"] = [boxes]

    inputs = processor(**proc_kwargs)

    # Keep only the prompt tensors (discard pixel_values).
    model_inputs: dict[str, Any] = {"image_embeddings": image_embeddings}
    for key in ("input_points", "input_labels", "input_boxes"):
        if key in inputs:
            # Labels are integer indices for an embedding layer — keep their dtype.
            if key == "input_labels":
                model_inputs[key] = inputs[key].to(device=device)
            else:
                model_inputs[key] = inputs[key].to(device=device, dtype=dtype)

    # SAM recommendation: multimask_output=True for ambiguous single-point
    # prompts (pick best by predicted IoU), False otherwise.
    has_single_point_only = len(points) == 1 and not boxes
    model_inputs["multimask_output"] = has_single_point_only

    with torch.no_grad():
        outputs = model(**model_inputs)

    # Post-process to original image size.
    masks = processor.post_process_masks(
        outputs.pred_masks.cpu(),
        original_sizes=inputs.get("original_sizes", [list(reversed(image.size))]),
    )

    # masks is a list (batch) of tensors with shape (num_masks, H, W).
    mask_tensor = masks[0].squeeze(0)  # (num_masks, H, W)

    if has_single_point_only:
        # Pick the mask with the highest predicted IoU score.
        iou_scores = outputs.iou_scores.squeeze()  # (num_masks,)
        best_idx = iou_scores.argmax().item()
        best_mask = mask_tensor[best_idx]
    else:
        best_mask = mask_tensor[0]

    return (best_mask > 0).cpu().numpy().astype(np.uint8)


@spaces.GPU
def segment(
    data: dict | None,
) -> tuple[
    tuple[Image.Image, list[dict[str, Any]]] | None,
    list[Image.Image],
    list[Image.Image],
    str,
]:
    """Run SAM2 inference on the current prompts."""
    empty: tuple[None, list, list, str] = (None, [], [], "{}")

    if data is None:
        return empty

    image_path = data.get("imagePath")
    if not image_path:
        return None, [], [], json.dumps(data, indent=2)

    image = Image.open(image_path).convert("RGB")
    prompts = data.get("prompts", [])

    if not prompts:
        return (image, []), [], [], json.dumps(data, indent=2)

    image_embeddings = _compute_image_embeddings(image)

    masks: list[dict[str, Any]] = []
    cutout_images: list[Image.Image] = []
    mask_images: list[Image.Image] = []
    image_rgba = np.array(image.convert("RGBA"))

    for obj in prompts:
        mask = _predict_mask_for_object(obj, image, image_embeddings)
        if mask is not None:
            masks.append({"mask": mask})

            cutout = image_rgba.copy()
            cutout[mask == 0] = [0, 0, 0, 0]
            cutout_images.append(Image.fromarray(cutout))

            mask_images.append(Image.fromarray(mask * 255))

    return (image, masks), cutout_images, mask_images, json.dumps(data, indent=2)


with gr.Blocks(title="SAM2 Demo") as demo:
    gr.Markdown(
        "## SAM2 Prompter Demo (Real Inference)\n"
        "Drop an image, then left-click for foreground points, "
        "right-click for background points, or drag a box."
    )

    prompter = SamPrompter(label="SAM2 Prompter")
    with gr.Row():
        cutout_gallery = gr.Gallery(label="Cutouts", columns=3, object_fit="contain", height="auto")
        mask_gallery = gr.Gallery(label="Masks", columns=3, object_fit="contain", height="auto")
    debug_json = gr.JSON(label="Prompt Data (debug)")

    prompter.input(
        fn=segment,
        inputs=prompter,
        outputs=[prompter, cutout_gallery, mask_gallery, debug_json],
    )


if __name__ == "__main__":
    demo.launch()
