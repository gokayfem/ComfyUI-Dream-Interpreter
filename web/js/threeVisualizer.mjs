import * as THREE from "three";
import { OrbitControls } from "../vendor/OrbitControls.mjs";

const SOURCE = "gokayfem.dream-interpreter.viewer";
const container = document.querySelector("#canvas-container");
const statusElement = document.querySelector("#status");
const errorElement = document.querySelector("#error");
const batchSelect = document.querySelector("#batch-select");
const interpretationPanel = document.querySelector("#interpretation-panel");
const interpretationElement = document.querySelector("#interpretation");

const renderer = new THREE.WebGLRenderer({
    antialias: true,
    preserveDrawingBuffer: true,
    powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
container.append(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0c0d12);
const camera = new THREE.PerspectiveCamera(70, 1, 0.01, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.enablePan = false;
controls.minDistance = 0.01;
controls.maxDistance = 0.1;
controls.rotateSpeed = -0.3;

let channel = null;
let viewUrl = null;
let output = null;
let panorama = null;
let updateVersion = 0;
let animationFrame = null;
let disposed = false;
let contextLost = false;
let inViewport = true;
const clock = new THREE.Clock();
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (reduceMotion) {
    document.querySelector("#auto-rotate").disabled = true;
    document.querySelector("#auto-rotate").title = "Disabled by prefers-reduced-motion";
}

function setStatus(message) {
    statusElement.textContent = message;
    statusElement.hidden = false;
    errorElement.hidden = true;
}

function setError(error) {
    console.error("[Dream Viewer]", error);
    errorElement.textContent = error instanceof Error ? error.message : String(error);
    errorElement.hidden = false;
    statusElement.hidden = true;
}

function resetCamera() {
    camera.position.set(0, 0, 0.01);
    controls.target.set(0, 0, -1);
    controls.update();
}

function resize() {
    const width = Math.max(container.clientWidth, 1);
    const height = Math.max(container.clientHeight, 1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(container);
resetCamera();
resize();

function removePanorama() {
    if (!panorama) {
        return;
    }
    scene.remove(panorama);
    panorama.geometry.dispose();
    panorama.material.map?.dispose();
    panorama.material.dispose();
    panorama = null;
}

function imageUrl(descriptor) {
    if (!viewUrl) {
        throw new Error("The ComfyUI API URL has not been initialized.");
    }
    const url = new URL(viewUrl, window.location.origin);
    url.search = new URLSearchParams({
        filename: descriptor.filename,
        subfolder: descriptor.subfolder ?? "",
        type: descriptor.type ?? "temp",
    }).toString();
    return url.href;
}

function loadTexture(descriptor) {
    return new Promise((resolve, reject) => {
        new THREE.TextureLoader().load(
            imageUrl(descriptor),
            (texture) => {
                texture.colorSpace = THREE.SRGBColorSpace;
                texture.anisotropy = Math.min(
                    8,
                    renderer.capabilities.getMaxAnisotropy(),
                );
                resolve(texture);
            },
            undefined,
            () => reject(new Error(`Unable to load ${descriptor.filename}.`)),
        );
    });
}

async function showFrame(index) {
    const descriptor = output?.hdri_image?.[index];
    if (!descriptor) {
        setError("The selected panorama is missing.");
        return;
    }

    const version = ++updateVersion;
    setStatus(`Loading panorama ${index + 1}…`);
    try {
        const texture = await loadTexture(descriptor);
        if (version !== updateVersion || disposed) {
            texture.dispose();
            return;
        }
        texture.mapping = THREE.EquirectangularReflectionMapping;
        removePanorama();
        panorama = new THREE.Mesh(
            new THREE.SphereGeometry(10, 96, 64),
            new THREE.MeshBasicMaterial({
                map: texture,
                side: THREE.BackSide,
            }),
        );
        scene.add(panorama);
        resetCamera();
        interpretationElement.textContent = String(
            output?.dream_interpretation?.[index]
            ?? output?.dream_interpretation?.[0]
            ?? "",
        );
        const ratio = texture.image.width / Math.max(texture.image.height, 1);
        if (Math.abs(ratio - 2) > 0.02) {
            setStatus(`Aspect warning: ${texture.image.width}×${texture.image.height}; immersive panoramas should be 2:1.`);
        } else {
            statusElement.hidden = true;
        }
    } catch (error) {
        if (version === updateVersion) {
            removePanorama();
            setError(error);
        }
    }
}

function setOutput(nextOutput) {
    const count = nextOutput?.hdri_image?.length ?? 0;
    if (!count) {
        setError("ComfyUI returned no panorama images.");
        return;
    }
    output = nextOutput;
    interpretationElement.textContent = String(nextOutput.dream_interpretation?.[0] ?? "");

    batchSelect.replaceChildren();
    for (let index = 0; index < count; index += 1) {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = `${index + 1} / ${count}`;
        batchSelect.append(option);
    }
    batchSelect.disabled = count === 1;
    batchSelect.value = "0";
    void showFrame(0);
}

function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function takeScreenshot() {
    renderer.render(scene, camera);
    renderer.domElement.toBlob((blob) => {
        if (blob) {
            download(blob, "dream-panorama.png");
        }
    }, "image/png");
}

function animate() {
    if (disposed) {
        return;
    }
    animationFrame = requestAnimationFrame(animate);
    if (
        document.querySelector("#auto-rotate").checked
        && !reduceMotion
        && panorama
        && inViewport
    ) {
        panorama.rotation.y += Math.min(clock.getDelta(), 0.1) * 0.08;
    } else {
        clock.getDelta();
    }
    if (document.visibilityState === "visible" && inViewport && !contextLost) {
        controls.update();
        renderer.render(scene, camera);
    }
}

const intersectionObserver = new IntersectionObserver(([entry]) => {
    inViewport = entry?.isIntersecting ?? true;
});
intersectionObserver.observe(container);
renderer.domElement.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    contextLost = true;
    setError("The browser paused this WebGL context. It will recover automatically.");
});
renderer.domElement.addEventListener("webglcontextrestored", () => {
    contextLost = false;
    setStatus("WebGL restored; rebuilding panorama…");
    void showFrame(Number(batchSelect.value || 0));
});
animate();

batchSelect.addEventListener("change", () => {
    void showFrame(Number(batchSelect.value));
});
document.querySelector("#reset-camera").addEventListener("click", resetCamera);
document.querySelector("#screenshot").addEventListener("click", takeScreenshot);
document.querySelector("#field-of-view").addEventListener("input", (event) => {
    camera.fov = Number(event.target.value);
    camera.updateProjectionMatrix();
    document.querySelector("#field-of-view-value").value = `${camera.fov}°`;
});
document.querySelector("#toggle-interpretation").addEventListener("click", () => {
    interpretationPanel.hidden = !interpretationPanel.hidden;
});
document.querySelector("#close-interpretation").addEventListener("click", () => {
    interpretationPanel.hidden = true;
});

window.addEventListener("message", (event) => {
    if (
        event.origin !== window.location.origin
        || event.source !== window.parent
        || event.data?.source !== SOURCE
    ) {
        return;
    }
    if (event.data.type === "connect") {
        channel = event.data.channel;
        window.parent.postMessage(
            { source: SOURCE, channel, type: "ready" },
            window.location.origin,
        );
        return;
    }
    if (event.data.channel !== channel) {
        return;
    }
    if (event.data.type === "initialize") {
        viewUrl = event.data.viewUrl;
        setStatus("Viewer connected — queue a panorama to begin.");
    } else if (event.data.type === "update") {
        setOutput(event.data.output);
    } else if (event.data.type === "dispose") {
        disposed = true;
        updateVersion += 1;
        cancelAnimationFrame(animationFrame);
        intersectionObserver.disconnect();
        removePanorama();
        controls.dispose();
        renderer.dispose();
    }
});
