"use strict";

/* =========================================================
   HIS STORY OF HISTORY
   tts.js
   Cinematic multi-speaker TTS engine
========================================================= */

/* =========================================================
   GLOBAL STATE
========================================================= */

const TTS_SUPPORTED = typeof speechSynthesis !== "undefined" && typeof SpeechSynthesisUtterance !== "undefined";

const TTS = {

    voices: [],
    voiceMap: new Map(),

    queue: [],
    currentIndex: 0,

    isPlaying: false,
    isPaused: false,

    currentUtterance: null,

    speed: 1,

    currentScript: null,

    onUpdate: null,
    onCaption: null,
    onEnd: null
};

/* =========================================================
   INIT
========================================================= */

document.addEventListener("DOMContentLoaded", () => {

    initVoices();

});

/* =========================================================
   VOICE SYSTEM
========================================================= */

function initVoices() {

    if (!TTS_SUPPORTED) {
        console.warn("Speech synthesis is not supported in this browser.");
        return;
    }

    loadVoices();

    if (speechSynthesis.onvoiceschanged !== undefined) {

        speechSynthesis.onvoiceschanged = () => {

            loadVoices();
        };
    }
}

function loadVoices() {

    if (!TTS_SUPPORTED) {
        return;
    }

    const voices = speechSynthesis.getVoices();

    if (!voices || voices.length === 0) {

        setTimeout(loadVoices, 200);

        return;
    }

    TTS.voices = voices;

    TTS.voiceMap.clear();

    for (const v of voices) {

        if (!TTS.voiceMap.has(v.lang)) {

            TTS.voiceMap.set(v.lang, []);
        }

        TTS.voiceMap.get(v.lang).push(v);
    }
}

/* =========================================================
   PUBLIC API
========================================================= */

/**
 * Load and play a dialogue script
 */
function playScript(script, options = {}) {

    if (!TTS_SUPPORTED) {
        emitCaption("TTS is not available in this browser.");
        return;
    }

    stop();

    TTS.currentScript = script;

    TTS.speed = options.speed || 1;

    const parsed = parseScript(script);

    TTS.queue = buildQueue(parsed);

    TTS.currentIndex = 0;

    TTS.isPlaying = true;

    TTS.isPaused = false;

    playNext();

}

/**
 * Pause playback
 */
function pause() {

    if (!TTS.isPlaying) return;

    speechSynthesis.pause();

    TTS.isPaused = true;

}

/**
 * Resume playback
 */
function resume() {

    if (!TTS.isPaused) return;

    speechSynthesis.resume();

    TTS.isPaused = false;

}

/**
 * Stop playback completely
 */
function stop() {

    speechSynthesis.cancel();

    TTS.queue = [];

    TTS.currentIndex = 0;

    TTS.isPlaying = false;

    TTS.isPaused = false;

    TTS.currentUtterance = null;

}

/* =========================================================
   SCRIPT PARSER (SAFE)
========================================================= */

function parseScript(script) {

    if (!script) return [];

    const blocks = [];

    const regex = /\[(.*?)\]\s*(.*?)(?=\n\[|$)/gs;

    let match;

    while ((match = regex.exec(script)) !== null) {

        const metaRaw = match[1];

        const text = sanitizeText(match[2]);

        const metaParts = metaRaw.split("|");

        const speakerId = metaParts[0];

        const meta = {

            speakerId,

            name: "Unknown",
            lang: "en-US",
            voice: null,
            pitch: 1,
            rate: 1
        };

        for (const part of metaParts.slice(1)) {

            const [k, v] = part.split("=");

            if (!k || !v) continue;

            const key = k.trim();
            const val = v.trim();

            if (key === "name") meta.name = val;
            if (key === "lang") meta.lang = val;
            if (key === "voice") meta.voice = val;
            if (key === "pitch") meta.pitch = clamp(Number(val), 0.5, 2);
            if (key === "rate") meta.rate = clamp(Number(val), 0.5, 2);
        }

        if (text) {

            blocks.push({
                ...meta,
                text
            });
        }
    }

    return blocks;
}

/* =========================================================
   QUEUE BUILDER
========================================================= */

function buildQueue(parsed) {

    const queue = [];

    for (const block of parsed) {

        const sentences = splitSentences(block.text);

        for (const sentence of sentences) {

            queue.push({

                ...block,
                text: sentence
            });
        }
    }

    return queue;
}

/* =========================================================
   PLAYBACK ENGINE
========================================================= */

function playNext() {

    if (!TTS.isPlaying) return;

    if (TTS.currentIndex >= TTS.queue.length) {

        stop();

        if (TTS.onEnd) {
            TTS.onEnd();
        }

        return;
    }

    const item = TTS.queue[TTS.currentIndex];

    const utterance = new SpeechSynthesisUtterance(item.text);

    utterance.rate = item.rate * TTS.speed;

    utterance.pitch = item.pitch;

    const voice = selectVoice(item.lang, item.voice);

    if (voice) {

        utterance.voice = voice;
    }

    TTS.currentUtterance = utterance;

    utterance.onstart = () => {

        emitCaption(item.text);

        if (TTS.onUpdate) {

            TTS.onUpdate({
                index: TTS.currentIndex,
                total: TTS.queue.length
            });
        }
    };

    utterance.onend = () => {

        TTS.currentIndex++;

        setTimeout(playNext, 80);
    };

    utterance.onerror = () => {

        TTS.currentIndex++;

        setTimeout(playNext, 80);
    };

    speechSynthesis.speak(utterance);

}

/* =========================================================
   VOICE SELECTION
========================================================= */

function selectVoice(lang, preferredVoice) {

    const voices = TTS.voiceMap.get(lang) || [];

    if (preferredVoice) {

        const match = TTS.voices.find(v =>
            v.name === preferredVoice
        );

        if (match) return match;
    }

    if (voices.length > 0) return voices[0];

    return TTS.voices.find(v =>
        v.lang.startsWith(lang.split("-")[0])
    );
}

/* =========================================================
   CAPTION SYSTEM
========================================================= */

function emitCaption(text) {

    const clean = sanitizeText(text);

    if (TTS.onCaption) {

        TTS.onCaption(clean);
    }

    const captionBox =
        document.querySelector(".tts-caption");

    if (captionBox) {

        captionBox.textContent = clean;
    }
}

/* =========================================================
   UTILITIES
========================================================= */

function sanitizeText(text) {

    return text
        .replace(/\[(.*?)\]/g, "")
        .replace(/\s+/g, " ")
        .trim();
}

function splitSentences(text) {

    return text
        .split(/(?<=[.!?])\s+/)
        .map(s => s.trim())
        .filter(Boolean);
}

function clamp(v, min, max) {

    return Math.max(min, Math.min(max, v));
}

/* =========================================================
   SPEED CONTROL
========================================================= */

function setSpeed(value) {

    TTS.speed = clamp(value, 0.5, 2);
}

/* =========================================================
   EVENT HOOKS (OPTIONAL UI CONNECTORS)
========================================================= */

function onUpdate(callback) {

    TTS.onUpdate = callback;
}

function onCaption(callback) {

    TTS.onCaption = callback;
}

function onEnd(callback) {

    TTS.onEnd = callback;
}

/* =========================================================
   EXPORT GLOBAL
========================================================= */

window.TTS = {

    supported: TTS_SUPPORTED,
    playScript,
    pause,
    resume,
    stop,
    setSpeed,
    onUpdate,
    onCaption,
    onEnd
};