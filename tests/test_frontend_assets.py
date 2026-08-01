import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_only_extension_entrypoint_uses_js_suffix():
    javascript_files = sorted(
        path.relative_to(ROOT).as_posix() for path in (ROOT / "web").rglob("*.js")
    )
    assert javascript_files == ["web/viewer_extension_3_0.js"]


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


def test_vendored_three_modules_are_complete():
    vendor = ROOT / "web" / "vendor"
    expected = {
        "three.module.min.mjs",
        "three.core.min.mjs",
        "OrbitControls.mjs",
        "THREE-LICENSE.txt",
    }
    assert expected.issubset({path.name for path in vendor.iterdir()})
    assert './three.core.min.mjs' in (vendor / "three.module.min.mjs").read_text(
        encoding="utf-8"
    )


def test_example_workflows_are_self_contained_json():
    original = json.loads(
        (ROOT / "dream_interpretation_workflow.json").read_text(encoding="utf-8")
    )
    live = json.loads(
        (ROOT / "examples" / "workflows" / "Dream-Toolkit-Live.json").read_text(
            encoding="utf-8"
        )
    )
    assert any(node.get("type") == "DreamViewer" for node in original["nodes"])
    assert any(node.get("type") == "DreamViewer" for node in live["nodes"])


def test_viewer_bridge_is_reload_and_cache_safe():
    entrypoint = (ROOT / "web" / "viewer_extension_3_0.js").read_text(encoding="utf-8")
    assert 'api.addEventListener("executed"' in entrypoint
    assert 'app.nodeOutputs?.[this.id]' in entrypoint
    assert 'window.setInterval' in entrypoint
    assert 'lastOutput' in entrypoint
    assert 'api.fetchApi("/history?max_items=32")' in entrypoint
    assert 'class_type === "DreamViewer"' in entrypoint
