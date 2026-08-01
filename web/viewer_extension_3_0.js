// Versioned entrypoint prevents stale browser modules after major upgrades.
import { api } from "../../scripts/api.js";
import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "gokayfem.dream-interpreter.viewer";
const PATCHED = Symbol("dreamViewerPatched");
const VIEWER_URL = new URL("./html/threeVisualizer.html?v=3.0.0", import.meta.url).href;

function normalizeOutput(message) {
    const payload = message?.output ?? message ?? {};
    return {
        hdri_image: payload.hdri_image ?? [],
        dream_interpretation: payload.dream_interpretation ?? [""],
    };
}

function hasViewerOutput(message) {
    const payload = message?.output ?? message ?? {};
    return (payload.hdri_image?.length ?? 0) > 0;
}

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
    iframe.loading = "lazy";
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
    const channel = globalThis.crypto?.randomUUID?.()
        ?? `dream-${Date.now()}-${Math.random()}`;
    let ready = false;
    let lastOutput = null;
    let restoring = false;

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
        if (lastOutput) {
            post("update", { output: lastOutput });
        }
    };

    const restoreLatestOutput = async () => {
        if (lastOutput || restoring) {
            return;
        }
        restoring = true;
        try {
            const response = await api.fetchApi("/history?max_items=32");
            if (!response.ok) {
                return;
            }
            const histories = Object.values(await response.json()).reverse();
            for (const history of histories) {
                const nodeId = String(node.id);
                const graph = history?.prompt?.[2];
                const output = history?.outputs?.[nodeId];
                if (
                    graph?.[nodeId]?.class_type === "DreamViewer"
                    && hasViewerOutput(output)
                ) {
                    lastOutput = normalizeOutput(output);
                    if (ready) {
                        post("update", { output: lastOutput });
                    }
                    break;
                }
            }
        } catch (error) {
            console.debug("[Dream Viewer] Cached output restore skipped.", error);
        } finally {
            restoring = false;
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
        void restoreLatestOutput();
    };

    window.addEventListener("message", onMessage);
    iframe.addEventListener("load", () => {
        ready = false;
        post("connect");
    });
    iframe.src = VIEWER_URL;
    container.append(iframe);
    const connectTimer = window.setInterval(() => {
        if (!ready) {
            post("connect");
        }
    }, 500);

    const widget = node.addDOMWidget("dream_preview", "DREAM_PREVIEW", container, {
        canvasOnly: true,
        hideOnZoom: true,
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
        lastOutput = output;
        if (!ready) {
            return;
        }
        post("update", { output });
    };

    const onExecution = ({ detail }) => {
        const outputNodeId = String(detail?.node ?? "").split(":")[0];
        if (outputNodeId === String(node.id)) {
            node.__dreamViewerUpdate?.(normalizeOutput(detail?.output));
        }
    };
    const onExecutionCached = () => {
        void restoreLatestOutput();
    };
    api.addEventListener("executed", onExecution);
    api.addEventListener("execution_cached", onExecutionCached);

    node.onRemoved = chainCallback(node.onRemoved, () => {
        window.clearInterval(connectTimer);
        api.removeEventListener("executed", onExecution);
        api.removeEventListener("execution_cached", onExecutionCached);
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
            requestAnimationFrame(() => {
                const cached = app.nodeOutputs?.[this.id];
                if (cached) {
                    this.__dreamViewerUpdate?.(normalizeOutput(cached));
                }
            });
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function onDreamViewerExecuted(message) {
            const result = onExecuted?.apply(this, arguments);
            this.__dreamViewerUpdate?.(normalizeOutput(message));
            return result;
        };
    },
});
