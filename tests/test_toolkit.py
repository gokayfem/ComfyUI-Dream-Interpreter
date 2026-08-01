from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

import dream_nodes as nodes


def panorama(height=32, width=64):
    x = torch.linspace(0, 1, width).view(1, 1, width, 1)
    y = torch.linspace(0, 1, height).view(1, height, 1, 1)
    return torch.cat((x.repeat(1, height, 1, 1), y.repeat(1, 1, width, 1), torch.ones((1, height, width, 1)) * 0.25), dim=-1)


def test_validate_and_perspective_projection():
    source = panorama()
    validated, report = nodes.DreamPanoramaValidate().validate(source, False, 1024)
    view, = nodes.DreamEquirectToPerspective().project(source, 20, -10, 0, 75, 80, 48)
    assert validated.shape == source.shape
    assert json.loads(report)["is_2_to_1"] is True
    assert view.shape == (1, 48, 80, 3)
    assert np.isfinite(view.numpy()).all()


def test_seam_repair_reduces_error_and_emits_proof():
    source = panorama()
    fixed, proof, report = nodes.DreamPanoramaSeamBlend().blend(source, 8)
    metrics = json.loads(report)
    assert metrics["seam_mae_after"] < metrics["seam_mae_before"]
    assert proof.shape[2] <= fixed.shape[2]


def test_little_planet_and_mask_are_video_ready():
    planet, mask = nodes.DreamLittlePlanet().project(
        panorama(), 128, 30, 1.0, "transparent black"
    )
    assert planet.shape == (1, 128, 128, 3)
    assert mask.shape == (1, 128, 128)
    assert mask.min() == 0 and mask.max() == 1


def test_prompt_and_motif_nodes_make_no_clinical_claims():
    prompt, negative, brief = nodes.DreamPromptBuilder().build(
        "I flew over a moonlit ocean through a doorway",
        "panorama generation", "cinematic surrealism", "awe-filled", "moonlit blue", ""
    )
    tags, report = nodes.DreamMotifTags().tag("I flew over an ocean to the moon", 8)
    assert "2:1 equirectangular" in prompt
    assert "clinical diagnosis" in negative
    assert "not a psychological assessment" in json.loads(brief)["disclaimer"].lower()
    assert {"water", "flight", "cosmic"}.issubset(set(tags.split(", ")))
    assert "not interpretation" in json.loads(report)["disclaimer"].lower()


def test_journal_save_is_confined_to_output(monkeypatch, tmp_path):
    import folder_paths

    monkeypatch.setattr(folder_paths, "get_output_directory", lambda: str(tmp_path), raising=False)
    markdown, structured, saved = nodes.DreamJournalEntry().compose(
        "Sky room", "A room above the clouds", "A visual idea", "calm", "sky, room", True, "dream_journal/test"
    )
    assert markdown.startswith("# Sky room")
    assert json.loads(structured)["schema"].endswith("/v1")
    assert Path(saved).is_file()
    assert Path(saved).is_relative_to(tmp_path)
