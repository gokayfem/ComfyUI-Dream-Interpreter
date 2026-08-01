"""Interactive 360-degree dream viewer for ComfyUI."""

from __future__ import annotations

import os
from typing import Any

import folder_paths
import numpy as np
from PIL import Image

try:
    from .dream_nodes import (
        NODE_CLASS_MAPPINGS as TOOL_NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS as TOOL_NODE_DISPLAY_NAME_MAPPINGS,
    )
except (ImportError, ModuleNotFoundError):  # Standalone import used by pytest.
    from dream_nodes import (  # type: ignore[no-redef]
        NODE_CLASS_MAPPINGS as TOOL_NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS as TOOL_NODE_DISPLAY_NAME_MAPPINGS,
    )


def _as_pil(image: Any) -> Image.Image:
    array = image.detach().cpu().float().numpy()
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0)
    array = np.clip(array, 0.0, 1.0)
    if array.ndim == 2:
        mode = "L"
    elif array.ndim == 3 and array.shape[-1] == 1:
        array = array[..., 0]
        mode = "L"
    elif array.ndim == 3 and array.shape[-1] >= 3:
        array = array[..., :3]
        mode = "RGB"
    else:
        raise ValueError(f"Expected an HxW, HxWx1, or HxWx3+ image, got {array.shape}.")
    return Image.fromarray((array * 255.0).round().astype(np.uint8), mode=mode).convert(
        "RGB"
    )


def _save_panorama(image: Image.Image, batch_number: int) -> dict[str, str]:
    output_dir = folder_paths.get_temp_directory()
    full_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
        "dream_viewer",
        output_dir,
        image.width,
        image.height,
    )
    filename = filename.replace("%batch_num%", str(batch_number))
    image_name = f"{filename}_{counter:05}_panorama.png"
    image.save(os.path.join(full_folder, image_name), compress_level=1)
    return {"filename": image_name, "subfolder": subfolder, "type": "temp"}


class DreamViewer:
    """Explore an equirectangular panorama with its dream interpretation."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dream_interpretation": (
                    "STRING",
                    {"multiline": True, "default": ""},
                ),
                "hdri_image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("panorama", "interpretation")
    OUTPUT_NODE = True
    FUNCTION = "process_inputs"
    CATEGORY = "visualization/3D"
    DESCRIPTION = (
        "Displays an equirectangular image as an interactive 360-degree panorama "
        "alongside the supplied dream interpretation."
    )

    def process_inputs(self, dream_interpretation, hdri_image):
        interpretation = str(dream_interpretation)
        panoramas = [
            _save_panorama(_as_pil(image), index)
            for index, image in enumerate(hdri_image)
        ]
        return {
            "ui": {
                "hdri_image": panoramas,
                "dream_interpretation": [interpretation],
            },
            "result": (hdri_image, interpretation),
        }


NODE_CLASS_MAPPINGS = {"DreamViewer": DreamViewer, **TOOL_NODE_CLASS_MAPPINGS}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DreamViewer": "Dream Panorama Viewer Pro",
    **TOOL_NODE_DISPLAY_NAME_MAPPINGS,
}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
