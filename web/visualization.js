import { api } from "../../scripts/api.js";
import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "gokayfem.dream-interpreter";
const PATCHED = Symbol("dreamViewerPatched");
const VIEWER_URL = new URL("./html/threeVisualizer.html", import.meta.url).href;

function chainCallback(previous, next) {
    return function chainedCallback(...args) {
        const result = previous?.apply(this, args);
        next.apply(this, args);
        return result;
    };
}

function createViewer(node) {
    const container = document.createElement("div");
    Object.assign(container.style, {
        width: "100%",
        height: "100%",
        minHeight: "440px",
        overflow: "hidden",
        borderRadius: "8px",
        background: "#0c0d12",
    });

    const iframe = document.createElement("iframe");
    iframe.title = "Interactive 360-degree dream panorama";
    iframe.src = VIEWER_URL;
    iframe.loading = "eager";
    iframe.setAttribute(
        "sandbox",
        "allow-scripts allow-same-origin allow-downloads",
    );
    Object.assign(iframe.style, {
        width: "100%",
        height: "100%",
        border: "0",
        display: "block",
        background: "#0c0d12",
    });
    container.append(iframe);

    const channel = globalThis.crypto?.randomUUID?.()
        ?? `dream-${Date.now()}-${Math.random()}`;
    let ready = false;
    let pendingOutput = null;

    const post = (type, payload = {}) => {
        iframe.contentWindow?.postMessage(
            {
                source: EXTENSION_NAME,
                channel,
                type,
                ...payload,
            },
            window.location.origin,
        );
    };

    const initialize = () => {
        post("initialize", { viewUrl: api.apiURL("/view") });
        if (pendingOutput) {
            post("update", { output: pendingOutput });
            pendingOutput = null;
        }
    };

    const onMessage = (event) => {
        if (
            event.origin !== window.location.origin
            || event.source !== iframe.contentWindow
            || event.data?.source !== EXTENSION_NAME
            || event.data?.channel !== channel
            || event.data?.type !== "ready"
        ) {
            return;
        }
        ready = true;
        initialize();
    };

    window.addEventListener("message", onMessage);
    iframe.addEventListener("load", () => {
        ready = false;
        post("connect");
    });

    const widget = node.addDOMWidget("dream_preview", "DREAM_PREVIEW", container, {
        canvasOnly: true,
        hideOnZoom: false,
    });
    widget.serialize = false;
    widget.computeLayoutSize = () => ({
        minWidth: 540,
        minHeight: 440,
    });

    const currentWidth = node.size?.[0] ?? 0;
    const currentHeight = node.size?.[1] ?? 0;
    if (currentWidth < 580 || currentHeight < 540) {
        node.setSize([
            Math.max(currentWidth, 580),
            Math.max(currentHeight, 540),
        ]);
    }

    node.__dreamViewerUpdate = (output) => {
        if (!output?.hdri_image?.length) {
            return;
        }
        if (!ready) {
            pendingOutput = output;
            return;
        }
        post("update", { output });
    };

    node.onRemoved = chainCallback(node.onRemoved, () => {
        window.removeEventListener("message", onMessage);
        post("dispose");
        iframe.src = "about:blank";
    });
}

app.registerExtension({
    name: EXTENSION_NAME,

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "DreamViewer" || nodeType.prototype[PATCHED]) {
            return;
        }
        nodeType.prototype[PATCHED] = true;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function onDreamViewerCreated(...args) {
            const result = onNodeCreated?.apply(this, args);
            createViewer(this);
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function onDreamViewerExecuted(message) {
            const result = onExecuted?.apply(this, arguments);
            this.__dreamViewerUpdate?.({
                hdri_image: message?.hdri_image ?? [],
                dream_interpretation: message?.dream_interpretation ?? [""],
            });
            return result;
        };
    },
});
