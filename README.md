# ComfyUI Dream Interpreter

Turn an equirectangular dream image into an interactive 360-degree panorama
inside ComfyUI and keep the written interpretation available alongside it.

![Dream Interpreter](https://github.com/gokayfem/ComfyUI-Dream-Interpreter/assets/88277926/668985f9-9211-47f5-b489-22821c97c003)

## Features

- Modern ComfyUI DOM-widget integration
- Smooth 360-degree orbit and zoom controls
- Batch panorama selector
- Safe, readable interpretation panel
- PNG screenshots
- Pinned local Three.js assets with no CDN requirement
- Correct resize, copy/paste, collapse, and removal lifecycle
- Stale-load cancellation, texture disposal, and visible errors

## Installation

Install with ComfyUI Manager, or clone manually:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/gokayfem/ComfyUI-Dream-Interpreter.git
python -m pip install -r ComfyUI-Dream-Interpreter/requirements.txt
```

Restart ComfyUI after installation.

## Usage

1. Generate an equirectangular 2:1 panorama using any image workflow.
2. Produce or write a dream interpretation as a `STRING`.
3. Add **Dream Viewer** from `visualization/3D`.
4. Connect both inputs and queue the workflow.

The included `dream_interpretation_workflow.json` is a full example and uses
additional custom-node packs. Missing third-party nodes will be shown by
ComfyUI when that workflow is loaded; the Dream Viewer itself only requires
this repository.

## Development

```bash
python -m pip install pytest
pytest -q
```

The browser assets are vendored from Three.js 0.185.1. Its MIT license is in
`web/vendor/THREE-LICENSE.txt`.

## Acknowledgements

The original viewer was inspired by
[ComfyUI-Flowty-TripoSR](https://github.com/flowtyone/ComfyUI-Flowty-TripoSR).
