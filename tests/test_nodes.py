from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pytest


class FakeTensor:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=np.float32)

    def detach(self):
        return self

    def cpu(self):
        return self

    def float(self):
        return self

    def numpy(self):
        return self.array


@pytest.fixture()
def dream_module(tmp_path, monkeypatch):
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_temp_directory = lambda: str(tmp_path)

    def get_save_image_path(prefix, output_dir, width, height):
        assert width > 0 and height > 0
        return output_dir, f"{prefix}_%batch_num%", 1, "", prefix

    folder_paths.get_save_image_path = get_save_image_path
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)

    module_path = Path(__file__).parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("dream_viewer_test_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module, tmp_path


def test_processes_every_panorama_and_preserves_interpretation(dream_module):
    module, output_dir = dream_module
    batch = [
        FakeTensor(np.zeros((8, 16, 3))),
        FakeTensor(np.ones((8, 16, 3))),
    ]

    result = module.DreamViewer().process_inputs("A calm ocean", batch)["ui"]

    assert result["dream_interpretation"] == ["A calm ocean"]
    assert len(result["hdri_image"]) == 2
    for descriptor in result["hdri_image"]:
        assert descriptor["type"] == "temp"
        assert (output_dir / descriptor["filename"]).is_file()


def test_rejects_invalid_image_shape(dream_module):
    module, _ = dream_module

    with pytest.raises(ValueError, match="Expected an HxW"):
        module._as_pil(FakeTensor(np.zeros((2, 3, 4, 5))))
