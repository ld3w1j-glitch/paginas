import { env, pipeline } from "../vendor/transformers/transformers.min.js";

env.allowRemoteModels = false;
env.allowLocalModels = true;
env.localModelPath = "/static/ingles/models/";
env.useBrowserCache = true;

const availableThreads = Number(self.navigator?.hardwareConcurrency || 2);
const wasmThreads = self.crossOriginIsolated
    ? Math.max(1, Math.min(4, Math.floor(availableThreads / 2)))
    : 1;

if (env.backends.onnx?.wasm) {
    env.backends.onnx.wasm.wasmPaths = "/static/ingles/vendor/transformers/";
    env.backends.onnx.wasm.numThreads = wasmThreads;
    env.backends.onnx.wasm.proxy = false;
}

const QUALITY_PROFILES = {
    fast: {
        label: "modo rápido",
        chunkLength: 620,
        generation: {max_new_tokens: 280, num_beams: 1},
    },
    balanced: {
        label: "modo equilibrado",
        chunkLength: 520,
        generation: {
            max_new_tokens: 360,
            num_beams: 3,
            no_repeat_ngram_size: 3,
            repetition_penalty: 1.04,
        },
    },
    quality: {
        label: "qualidade máxima",
        chunkLength: 420,
        generation: {
            max_new_tokens: 420,
            num_beams: 5,
            no_repeat_ngram_size: 3,
            repetition_penalty: 1.08,
            length_penalty: 1.0,
            early_stopping: true,
        },
    },
};

let translatorPromise;

function progressLabel(progress) {
    const file = String(progress.file || "");
    if (file.includes("encoder")) return "Carregando compreensão do inglês";
    if (file.includes("decoder")) return "Carregando geração em português";
    if (file.includes("tokenizer") || file.includes("spm") || file.includes("vocab")) {
        return "Carregando vocabulário neural";
    }
    return "Preparando IA neural offline";
}

function getTranslator() {
    if (!translatorPromise) {
        translatorPromise = pipeline("translation", "opus-mt-en-ROMANCE", {
            device: "wasm",
            dtype: "q8",
            progress_callback: (progress) => {
                const percent = Number.isFinite(progress.progress)
                    ? Math.max(0, Math.min(100, Math.round(progress.progress)))
                    : null;
                self.postMessage({
                    type: "progress",
                    label: progressLabel(progress),
                    percent,
                    status: progress.status || "loading",
                });
            },
        }).catch((error) => {
            translatorPromise = null;
            throw error;
        });
    }
    return translatorPromise;
}

function normalizeKey(value) {
    return String(value || "").trim().toLocaleLowerCase("en-US").replace(/\s+/g, " ");
}

function splitLongUnit(value, maxLength) {
    const words = value.split(/\s+/).filter(Boolean);
    const chunks = [];
    let current = "";
    for (const word of words) {
        if (current && current.length + word.length + 1 > maxLength) {
            chunks.push(current);
            current = word;
        } else {
            current = current ? `${current} ${word}` : word;
        }
    }
    if (current) chunks.push(current);
    return chunks;
}

function buildTranslationPlan(text, memorySegments, maxLength) {
    const memory = new Map(
        (memorySegments || [])
            .filter((item) => item?.source && item?.translation)
            .map((item) => [normalizeKey(item.source), String(item.translation).trim()]),
    );
    const units = text.replace(/\r\n?/g, "\n").match(/[^.!?\n]+(?:[.!?]+|$)|\n+/g) || [text];
    const plan = [];
    let current = "";

    const flush = () => {
        if (current.trim()) plan.push({type: "neural", source: current.trim()});
        current = "";
    };

    for (const rawUnit of units) {
        if (/^\n+$/.test(rawUnit)) {
            flush();
            plan.push({type: "separator", value: rawUnit.length > 1 ? "\n\n" : "\n"});
            continue;
        }
        const unit = rawUnit.trim();
        if (!unit) continue;
        const learned = memory.get(normalizeKey(unit));
        if (learned) {
            flush();
            plan.push({type: "memory", source: unit, translation: learned});
            continue;
        }
        if (unit.length > maxLength) {
            flush();
            splitLongUnit(unit, maxLength).forEach((part) => plan.push({type: "neural", source: part}));
            continue;
        }
        if (current && current.length + unit.length + 1 > maxLength) flush();
        current = current ? `${current} ${unit}` : unit;
    }
    flush();
    return plan;
}

function cleanupPiece(original, translated) {
    let value = String(translated || "")
        .replace(/>>[^<]+<</g, "")
        .replace(/\s+([,.;:!?])/g, "$1")
        .replace(/[ \t]{2,}/g, " ")
        .trim();
    const source = original.toLowerCase();
    if (/\b(?:turn|switch)\s+on\b/.test(source) && /\bpower\b/.test(source)) {
        value = value.replace(/\bpotência\b/gi, "energia");
    }
    return value;
}

function assemble(parts) {
    let value = "";
    for (const part of parts) {
        if (part.type === "separator") {
            value = `${value.trimEnd()}${part.value}`;
        } else {
            if (value && !/\s$/.test(value)) value += " ";
            value += part.translation;
        }
    }
    return value.replace(/ *\n */g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}

self.onmessage = async (event) => {
    if (event.data?.type !== "translate") return;
    const requestId = event.data.requestId;
    const text = String(event.data.text || "").trim();
    const quality = Object.hasOwn(QUALITY_PROFILES, event.data.quality)
        ? event.data.quality
        : "balanced";
    const profile = QUALITY_PROFILES[quality];
    if (!text) {
        self.postMessage({type: "error", requestId, error: "O texto está vazio."});
        return;
    }
    try {
        self.postMessage({
            type: "status",
            requestId,
            label: `Iniciando IA offline · ${profile.label} · ${wasmThreads} thread${wasmThreads > 1 ? "s" : ""}`,
        });
        const translator = await getTranslator();
        const plan = buildTranslationPlan(text, event.data.memorySegments, profile.chunkLength);
        const translatableCount = plan.filter((item) => item.type === "neural").length;
        const usedMemory = plan.filter((item) => item.type === "memory").length;
        let translatedIndex = 0;

        for (const item of plan) {
            if (item.type === "separator") continue;
            if (item.type === "memory") continue;
            translatedIndex += 1;
            self.postMessage({
                type: "status",
                requestId,
                label: translatableCount > 1
                    ? `Traduzindo bloco ${translatedIndex} de ${translatableCount} · ${profile.label}`
                    : `Interpretando o contexto · ${profile.label}`,
            });
            const output = await translator(`>>pt_BR<< ${item.source}`, profile.generation);
            item.translation = cleanupPiece(item.source, output[0]?.translation_text || "");
        }

        self.postMessage({
            type: "result",
            requestId,
            translation: assemble(plan),
            quality,
            qualityLabel: profile.label,
            usedMemory,
            chunks: translatableCount,
            threads: wasmThreads,
        });
    } catch (error) {
        self.postMessage({
            type: "error",
            requestId,
            error: error instanceof Error ? error.message : String(error),
        });
    }
};
