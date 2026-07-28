"""Minimal ComfyUI module shim used while pytest collects this package."""

from __future__ import annotations

import sys
import types


try:
    import folder_paths  # noqa: F401
except ModuleNotFoundError:
    sys.modules["folder_paths"] = types.ModuleType("folder_paths")
