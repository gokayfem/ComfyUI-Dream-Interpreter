import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_only_extension_entrypoint_uses_js_suffix():
    javascript_files = sorted(
        path.relative_to(ROOT).as_posix() for path in (ROOT / "web").rglob("*.js")
    )
    assert javascript_files == ["web/visualization.js"]


def test_frontend_has_no_runtime_cdn_dependency():
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "web").rglob("*")
        if path.suffix in {".html", ".js", ".mjs", ".css"}
        and "vendor" not in path.parts
    )
    assert "https://" not in frontend_text
    assert "http://" not in frontend_text
    assert "@latest" not in frontend_text


def test_vendored_three_modules_are_present():
    vendor = ROOT / "web" / "vendor"
    expected = {
        "three.module.min.mjs",
        "OrbitControls.mjs",
        "THREE-LICENSE.txt",
    }
    assert expected.issubset({path.name for path in vendor.iterdir()})


def test_example_workflow_is_valid_json():
    workflow = json.loads(
        (ROOT / "dream_interpretation_workflow.json").read_text(encoding="utf-8")
    )
    assert any(node.get("type") == "DreamViewer" for node in workflow["nodes"])
