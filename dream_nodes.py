"""Offline panorama and creative dream-journaling utilities for ComfyUI."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

import numpy as np
from PIL import Image


PANORAMA_CATEGORY = "panorama/dream toolkit"
JOURNAL_CATEGORY = "text/dream journal"


def _numpy_batch(images: Any) -> np.ndarray:
    array = images.detach().cpu().float().numpy()
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0)
    if array.ndim == 3:
        array = array[None, ...]
    if array.ndim != 4:
        raise ValueError(f"Expected a BHWC image batch, got {array.shape}.")
    if array.shape[-1] == 1:
        array = np.repeat(array, 3, axis=-1)
    elif array.shape[-1] < 3:
        raise ValueError(f"Expected one or at least three channels, got {array.shape}.")
    return np.clip(array[..., :3], 0.0, 1.0).astype(np.float32, copy=False)


def _torch(array: np.ndarray):
    import torch

    return torch.from_numpy(np.ascontiguousarray(array, dtype=np.float32))


def _bilinear_wrap(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    x = np.mod(x, width)
    y = np.clip(y, 0.0, height - 1.0)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = (x0 + 1) % width
    y1 = np.minimum(y0 + 1, height - 1)
    wx = (x - x0)[..., None]
    wy = (y - y0)[..., None]
    top = image[y0, x0] * (1.0 - wx) + image[y0, x1] * wx
    bottom = image[y1, x0] * (1.0 - wx) + image[y1, x1] * wx
    return top * (1.0 - wy) + bottom * wy


def _resize(image: np.ndarray, width: int, height: int) -> np.ndarray:
    pil = Image.fromarray((image * 255.0).round().astype(np.uint8), "RGB")
    return np.asarray(pil.resize((width, height), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0


class DreamPanoramaValidate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "panorama": ("IMAGE",),
                "repair_aspect": ("BOOLEAN", {"default": False}),
                "target_width": ("INT", {"default": 2048, "min": 256, "max": 8192, "step": 64}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("validated_panorama", "report_json")
    FUNCTION = "validate"
    CATEGORY = PANORAMA_CATEGORY
    DESCRIPTION = "Checks 2:1 equirectangular geometry, seam energy, range, and optionally repairs aspect ratio."

    def validate(self, panorama, repair_aspect, target_width):
        batch = _numpy_batch(panorama)
        source_h, source_w = batch.shape[1:3]
        seam = float(np.mean(np.abs(batch[:, :, 0, :] - batch[:, :, -1, :])))
        pole_variance = float((batch[:, 0].var() + batch[:, -1].var()) * 0.5)
        repaired = bool(repair_aspect and source_w != source_h * 2)
        if repaired:
            width = int(target_width)
            height = width // 2
            batch = np.stack([_resize(image, width, height) for image in batch])
        report = {
            "source_resolution": [int(source_w), int(source_h)],
            "output_resolution": [int(batch.shape[2]), int(batch.shape[1])],
            "is_2_to_1": source_w == source_h * 2,
            "aspect_repaired": repaired,
            "seam_mae": round(seam, 6),
            "pole_variance": round(pole_variance, 6),
            "guidance": "Use a 2:1 equirectangular panorama; inspect the seam before immersive viewing.",
        }
        return (_torch(batch), json.dumps(report, indent=2))


class DreamEquirectToPerspective:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "panorama": ("IMAGE",),
                "yaw": ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "pitch": ("FLOAT", {"default": 0.0, "min": -89.0, "max": 89.0, "step": 1.0}),
                "roll": ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "field_of_view": ("FLOAT", {"default": 80.0, "min": 20.0, "max": 150.0, "step": 1.0}),
                "width": ("INT", {"default": 1024, "min": 128, "max": 4096, "step": 64}),
                "height": ("INT", {"default": 768, "min": 128, "max": 4096, "step": 64}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("perspective_view",)
    FUNCTION = "project"
    CATEGORY = PANORAMA_CATEGORY
    DESCRIPTION = "Renders a rectilinear camera view from an equirectangular panorama."

    def project(self, panorama, yaw, pitch, roll, field_of_view, width, height):
        batch = _numpy_batch(panorama)
        out_w, out_h = int(width), int(height)
        yy, xx = np.mgrid[0:out_h, 0:out_w]
        aspect = out_w / out_h
        scale = np.tan(np.deg2rad(float(field_of_view)) * 0.5)
        x = (2.0 * (xx + 0.5) / out_w - 1.0) * scale * aspect
        y = (1.0 - 2.0 * (yy + 0.5) / out_h) * scale
        rays = np.stack((x, y, np.ones_like(x)), axis=-1)
        rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
        yr, pr, rr = np.deg2rad([yaw, pitch, roll])
        cy, sy, cp, sp, cr, sr = np.cos(yr), np.sin(yr), np.cos(pr), np.sin(pr), np.cos(rr), np.sin(rr)
        yaw_m = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        pitch_m = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        roll_m = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
        rays = rays @ (yaw_m @ pitch_m @ roll_m).T
        longitude = np.arctan2(rays[..., 0], rays[..., 2])
        latitude = np.arcsin(np.clip(rays[..., 1], -1.0, 1.0))
        outputs = []
        for image in batch:
            source_h, source_w = image.shape[:2]
            sx = (longitude / (2.0 * np.pi) + 0.5) * source_w - 0.5
            sy_coord = (0.5 - latitude / np.pi) * source_h - 0.5
            outputs.append(_bilinear_wrap(image, sx, sy_coord))
        return (_torch(np.stack(outputs)),)


class DreamPanoramaSeamBlend:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "panorama": ("IMAGE",),
                "blend_width": ("INT", {"default": 48, "min": 1, "max": 512}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("seam_repaired", "seam_proof", "report")
    FUNCTION = "blend"
    CATEGORY = PANORAMA_CATEGORY
    DESCRIPTION = "Crossfades the wrap seam and emits a centered proof strip for visual inspection."

    def blend(self, panorama, blend_width):
        batch = _numpy_batch(panorama)
        result = batch.copy()
        width = result.shape[2]
        blend = min(int(blend_width), max(1, width // 4))
        before = float(np.mean(np.abs(result[:, :, 0, :] - result[:, :, -1, :])))
        for offset in range(blend):
            t = (offset + 1) / (blend + 1)
            left = result[:, :, offset, :].copy()
            right = result[:, :, width - 1 - offset, :].copy()
            merged = left * t + right * (1.0 - t)
            result[:, :, offset, :] = merged
            result[:, :, width - 1 - offset, :] = merged
        after = float(np.mean(np.abs(result[:, :, 0, :] - result[:, :, -1, :])))
        shifted = np.roll(result, width // 2, axis=2)
        proof_width = min(width, max(128, blend * 6))
        center = width // 2
        proof = shifted[:, :, center - proof_width // 2 : center + proof_width // 2, :]
        return (_torch(result), _torch(proof), json.dumps({"seam_mae_before": before, "seam_mae_after": after, "blend_width": blend}, indent=2))


class DreamLittlePlanet:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "panorama": ("IMAGE",),
                "size": ("INT", {"default": 1024, "min": 256, "max": 4096, "step": 64}),
                "rotation": ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "zoom": ("FLOAT", {"default": 1.0, "min": 0.25, "max": 3.0, "step": 0.05}),
                "background": (["transparent black", "zenith color", "edge stretch"],),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("little_planet", "planet_mask")
    FUNCTION = "project"
    CATEGORY = PANORAMA_CATEGORY
    DESCRIPTION = "Creates a stereographic little-planet projection and a reusable circular mask."

    def project(self, panorama, size, rotation, zoom, background):
        batch = _numpy_batch(panorama)
        out = int(size)
        yy, xx = np.mgrid[0:out, 0:out]
        nx = (xx + 0.5 - out / 2) / (out / 2)
        ny = (yy + 0.5 - out / 2) / (out / 2)
        radius = np.sqrt(nx * nx + ny * ny) / max(float(zoom), 1e-6)
        theta = np.arctan2(ny, nx) + np.deg2rad(float(rotation))
        latitude = np.pi / 2.0 - 2.0 * np.arctan(radius)
        mask = (radius <= 1.35).astype(np.float32)
        outputs = []
        for image in batch:
            h, w = image.shape[:2]
            sx = (theta / (2.0 * np.pi) + 0.5) * w - 0.5
            sy = (0.5 - latitude / np.pi) * h - 0.5
            sampled = _bilinear_wrap(image, sx, sy)
            if background == "transparent black":
                sampled *= mask[..., None]
            elif background == "zenith color":
                zenith = image[: max(1, h // 32)].mean(axis=(0, 1))
                sampled = sampled * mask[..., None] + zenith * (1.0 - mask[..., None])
            outputs.append(sampled)
        return (_torch(np.stack(outputs)), _torch(np.repeat(mask[None, ...], len(batch), axis=0)))


class DreamPromptBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "dream_text": ("STRING", {"multiline": True, "default": ""}),
                "purpose": (["panorama generation", "image generation", "video generation", "creative reflection"],),
                "visual_style": (["cinematic surrealism", "dreamlike realism", "storybook", "dark fantasy", "ethereal minimalism", "custom"],),
                "mood": (["mysterious", "calm", "joyful", "uneasy", "melancholic", "awe-filled", "mixed"],),
                "palette": (["moonlit blue", "warm sunrise", "jewel tones", "monochrome", "pastel haze", "natural", "custom"],),
                "custom_direction": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt", "negative_prompt", "creative_brief_json")
    FUNCTION = "build"
    CATEGORY = JOURNAL_CATEGORY
    DESCRIPTION = "Builds deterministic creative prompts; it does not make psychological or clinical claims."

    def build(self, dream_text, purpose, visual_style, mood, palette, custom_direction):
        source = " ".join(str(dream_text).split())
        direction = f" Additional direction: {custom_direction.strip()}" if custom_direction.strip() else ""
        projection = "seamless 2:1 equirectangular 360 panorama, level horizon," if purpose == "panorama generation" else ""
        prompt = (
            f"{projection} translate this remembered dream into {visual_style}: {source}. "
            f"Mood: {mood}. Palette: {palette}. Preserve symbolic ambiguity, coherent spatial relationships, "
            f"specific materials, intentional lighting, and a clear visual focal path.{direction}"
        ).strip()
        negative = "literal text labels, watermark, UI, accidental duplicates, broken perspective, low detail, clinical diagnosis"
        brief = {"schema": "comfyui-dream-creative-brief/v1", "purpose": purpose, "style": visual_style, "mood": mood, "palette": palette, "source": source, "disclaimer": "Creative reflection only; not a psychological assessment."}
        return (prompt, negative, json.dumps(brief, ensure_ascii=False, indent=2))


class DreamMotifTags:
    LEXICON = {
        "water": ("ocean", "sea", "river", "rain", "water", "flood", "lake"),
        "flight": ("fly", "flew", "flying", "floating", "wings", "sky"),
        "threshold": ("door", "gate", "window", "bridge", "stairs", "portal"),
        "pursuit": ("chase", "chasing", "escape", "running", "followed"),
        "home": ("home", "house", "room", "bedroom", "kitchen"),
        "nature": ("forest", "tree", "mountain", "garden", "animal", "flower"),
        "transformation": ("transform", "changed", "became", "shapeshift", "melted"),
        "cosmic": ("star", "moon", "planet", "space", "galaxy", "sun"),
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"dream_text": ("STRING", {"multiline": True, "default": ""}), "max_tags": ("INT", {"default": 8, "min": 1, "max": 32})}}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("comma_tags", "tag_report_json")
    FUNCTION = "tag"
    CATEGORY = JOURNAL_CATEGORY
    DESCRIPTION = "Finds descriptive creative motifs with an offline keyword lexicon; no universal-symbol claims."

    def tag(self, dream_text, max_tags):
        words = re.findall(r"[\w'-]+", str(dream_text).lower())
        scores = {tag: sum(words.count(term) for term in terms) for tag, terms in self.LEXICON.items()}
        ranked = [tag for tag, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])) if score > 0][: int(max_tags)]
        report = {"tags": ranked, "matched_counts": {tag: scores[tag] for tag in ranked}, "method": "descriptive offline keyword matching", "disclaimer": "Tags support creative organization, not interpretation or diagnosis."}
        return (", ".join(ranked), json.dumps(report, indent=2))


class DreamJournalEntry:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "title": ("STRING", {"default": "Untitled dream"}),
                "dream_text": ("STRING", {"multiline": True, "default": ""}),
                "reflection": ("STRING", {"multiline": True, "default": ""}),
                "mood": ("STRING", {"default": ""}),
                "tags": ("STRING", {"default": ""}),
                "save_to_output": ("BOOLEAN", {"default": False}),
                "filename_prefix": ("STRING", {"default": "dream_journal/dream"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("markdown", "structured_json", "saved_path")
    FUNCTION = "compose"
    CATEGORY = JOURNAL_CATEGORY
    DESCRIPTION = "Creates a portable Markdown/JSON journal entry and optionally saves it inside ComfyUI output."

    def compose(self, title, dream_text, reflection, mood, tags, save_to_output, filename_prefix):
        clean_title = str(title).strip() or "Untitled dream"
        tag_list = [item.strip() for item in str(tags).split(",") if item.strip()]
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        data = {"schema": "comfyui-dream-journal/v1", "created_at": stamp, "title": clean_title, "dream": str(dream_text), "reflection": str(reflection), "mood": str(mood), "tags": tag_list, "disclaimer": "Personal creative reflection only; not medical or psychological advice."}
        markdown = (
            f"# {clean_title}\n\n**Created:** {stamp}  \n**Mood:** {mood or '—'}  \n"
            f"**Tags:** {', '.join(tag_list) or '—'}\n\n## Dream\n\n{dream_text}\n\n"
            f"## Reflection\n\n{reflection or '—'}\n\n---\n*Creative journal entry; not a clinical interpretation.*\n"
        )
        saved = ""
        if save_to_output:
            import folder_paths

            output_root = os.path.realpath(folder_paths.get_output_directory())
            safe_parts = [re.sub(r"[^A-Za-z0-9._-]+", "_", part).strip("._") for part in str(filename_prefix).replace("\\", "/").split("/")]
            safe_parts = [part for part in safe_parts if part]
            if not safe_parts:
                safe_parts = ["dream_journal", "dream"]
            directory = os.path.join(output_root, *safe_parts[:-1])
            os.makedirs(directory, exist_ok=True)
            stem = safe_parts[-1]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            saved = os.path.realpath(os.path.join(directory, f"{stem}_{timestamp}.md"))
            if os.path.commonpath((output_root, saved)) != output_root:
                raise ValueError("Journal path must remain inside the ComfyUI output directory.")
            with open(saved, "x", encoding="utf-8", newline="\n") as handle:
                handle.write(markdown)
        return (markdown, json.dumps(data, ensure_ascii=False, indent=2), saved)


NODE_CLASS_MAPPINGS = {
    "DreamPanoramaValidate": DreamPanoramaValidate,
    "DreamEquirectToPerspective": DreamEquirectToPerspective,
    "DreamPanoramaSeamBlend": DreamPanoramaSeamBlend,
    "DreamLittlePlanet": DreamLittlePlanet,
    "DreamPromptBuilder": DreamPromptBuilder,
    "DreamMotifTags": DreamMotifTags,
    "DreamJournalEntry": DreamJournalEntry,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DreamPanoramaValidate": "Validate Dream Panorama",
    "DreamEquirectToPerspective": "Panorama Camera View",
    "DreamPanoramaSeamBlend": "Repair Panorama Seam",
    "DreamLittlePlanet": "Dream Little Planet",
    "DreamPromptBuilder": "Dream Creative Prompt Builder",
    "DreamMotifTags": "Dream Motif Tags",
    "DreamJournalEntry": "Dream Journal Entry",
}
