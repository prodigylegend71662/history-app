"use strict";

const App = {
    mobileMenuOpen: false,
    activeModal: null,
    loading: false,
    currentPlaybackSpeed: 1,
    initialized: false
};

document.addEventListener("DOMContentLoaded", initializeApplication);

function initializeApplication() {
    if (App.initialized) {
        return;
    }

    initializeFlashMessages();
    initializeMobileMenu();
    initializeLikeButtons();
    initializeBookmarkButtons();
    initializeFeedCards();
    initializeCreatePage();
    initializePlaybackButtons();
    initializeProgressBars();
    initializeSearch();
    initializeModals();
    initializeTooltips();
    initializeKeyboardShortcuts();
    initializeSmoothScroll();
    initializeAnimations();

    App.initialized = true;
}

function initializeFlashMessages() {
    const flashes = document.querySelectorAll(".flash-message");

    flashes.forEach((flash, index) => {
        setTimeout(() => {
            flash.classList.add("flash-visible");
        }, 100 * index);

        setTimeout(() => {
            flash.classList.remove("flash-visible");
            flash.classList.add("flash-hide");
        }, 5000);

        setTimeout(() => {
            flash.remove();
        }, 5600);
    });
}

function initializeMobileMenu() {
    const toggle = document.querySelector(".mobile-menu-toggle");
    const mobileMenu = document.querySelector(".mobile-menu");

    if (!toggle || !mobileMenu) {
        return;
    }

    toggle.addEventListener("click", () => {
        App.mobileMenuOpen = !App.mobileMenuOpen;
        mobileMenu.classList.toggle("mobile-menu-open", App.mobileMenuOpen);
        toggle.classList.toggle("mobile-toggle-active", App.mobileMenuOpen);
    });
}

function initializeFeedCards() {
    const cards = document.querySelectorAll(".feed-card");

    cards.forEach(card => {
        card.addEventListener("mousemove", (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty("--mouse-x", `${x}px`);
            card.style.setProperty("--mouse-y", `${y}px`);
        });

        card.addEventListener("mouseenter", () => {
            card.classList.add("feed-card-active");
        });

        card.addEventListener("mouseleave", () => {
            card.classList.remove("feed-card-active");
        });
    });
}

function initializeLikeButtons() {
    const buttons = document.querySelectorAll(".like-button");

    buttons.forEach(button => {
        button.addEventListener("click", async () => {
            if (button.dataset.loading === "true") {
                return;
            }

            const postId = button.dataset.postId;
            if (!postId) {
                return;
            }

            button.dataset.loading = "true";
            button.classList.add("button-loading");

            try {
                const response = await fetch(`/api/like/${postId}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    }
                });
                let data = null;
                const contentType = response.headers.get("content-type") || "";
                if (contentType.includes("application/json")) {
                    data = await response.json();
                }

                if (response.ok && data?.success) {
                    const count = button.querySelector(".like-count");
                    if (count) {
                        count.textContent = Number(data.likes || 0);
                    }
                    button.classList.add("liked-pulse");
                    setTimeout(() => button.classList.remove("liked-pulse"), 700);
                } else {
                    console.warn("Like API error:", data?.message || response.statusText || "Non-JSON response");
                }
            } catch (error) {
                console.error("Like failed:", error);
            } finally {
                button.dataset.loading = "false";
                button.classList.remove("button-loading");
            }
        });
    });
}

function initializeBookmarkButtons() {
    const buttons = document.querySelectorAll(".bookmark-button");

    buttons.forEach(button => {
        button.addEventListener("click", async () => {
            const postId = button.dataset.postId;
            if (!postId) {
                return;
            }

            button.classList.add("button-loading");

            try {
                const response = await fetch(`/api/bookmark/${postId}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    }
                });
                let data = null;
                const contentType = response.headers.get("content-type") || "";
                if (contentType.includes("application/json")) {
                    data = await response.json();
                }

                if (response.ok && data?.success) {
                    button.classList.toggle("bookmarked", data.bookmarked);
                } else {
                    console.warn("Bookmark API error:", data?.message || response.statusText || "Non-JSON response");
                }
            } catch (error) {
                console.error("Bookmark failed:", error);
            } finally {
                button.classList.remove("button-loading");
            }
        });
    });
}

function initializeCreatePage() {
    const createForm = document.querySelector(".create-form");
    if (!createForm) {
        return;
    }

    initializePostTypeSwitcher();
    initializeSpeakerEditor();
    initializeVoiceLoading();
    initializeSyntaxHighlighting();
    initializeLivePreview();
    initializeAudioUploadPreview();
    initializePlaybackSpeedControl();
}

function initializePostTypeSwitcher() {
    const selector = document.querySelector("#postType");
    if (!selector) {
        return;
    }

    const dialogueSection = document.querySelector(".dialogue-editor-section");
    const audioSection = document.querySelector(".audio-upload-section");
    const readonlySection = document.querySelector(".readonly-editor-section");

    function updateSections() {
        const value = selector.value;
        hideAllCreateSections();

        if (value === "dialogue") {
            dialogueSection?.classList.add("section-visible");
        } else if (value === "audio") {
            audioSection?.classList.add("section-visible");
        } else if (value === "read-only") {
            readonlySection?.classList.add("section-visible");
        }
    }

    selector.addEventListener("change", updateSections);
    updateSections();
}

function hideAllCreateSections() {
    const sections = document.querySelectorAll(".create-section");
    sections.forEach(section => {
        section.classList.remove("section-visible");
    });
}

function initializeSpeakerEditor() {
    const addSpeakerButton = document.getElementById("addSpeaker");
    const speakerList = document.querySelector(".speaker-list");
    const editor = document.querySelector(".dialogue-script-editor");

    if (!addSpeakerButton || !speakerList || !editor) {
        return;
    }

    addSpeakerButton.addEventListener("click", () => {
        addSpeakerCard(speakerList, editor);
    });

    editor.addEventListener("input", debounce(() => {
        syncSpeakerCardsWithEditor(speakerList, editor);
    }, 300));

    syncSpeakerCardsWithEditor(speakerList, editor);
}

function syncSpeakerCardsWithEditor(speakerList, editor) {
    const parsed = parseScript(editor.value);
    speakerList.innerHTML = "";

    if (parsed.length === 0) {
        addSpeakerCard(speakerList, editor, null, { skipSync: true });
        return;
    }

    parsed.forEach(block => {
        addSpeakerCard(speakerList, editor, block, { skipSync: true });
    });
}

function addSpeakerCard(speakerList, editor, block = null, options = {}) {
    const card = document.createElement("div");
    card.className = "speaker-card";
    card.dataset.speakerId = block?.speakerId || `p${speakerList.children.length + 1}`;

    card.innerHTML = `
        <div class="speaker-card-header">
            <div><strong>Speaker ${speakerList.children.length + 1}</strong></div>
            <button type="button" class="speaker-remove">Remove</button>
        </div>
        <label>Name
            <input type="text" class="speaker-name" value="${block?.name || ""}" placeholder="Speaker name">
        </label>
        <label>Language
            <select class="speaker-lang">
                <option value="en-US">English (US)</option>
                <option value="en-GB">English (UK)</option>
                <option value="fr-CA">French (Canada)</option>
                <option value="fr-FR">French (France)</option>
                <option value="es-ES">Spanish</option>
                <option value="de-DE">German</option>
                <option value="it-IT">Italian</option>
                <option value="pt-BR">Portuguese (Brazil)</option>
            </select>
        </label>
        <label>Voice
            <select class="speaker-voice-select"></select>
        </label>
        <label>Pitch
            <input type="number" min="0.5" max="2" step="0.1" class="speaker-pitch" value="${block?.pitch ?? 1}">
        </label>
        <label>Rate
            <input type="number" min="0.5" max="2" step="0.1" class="speaker-rate" value="${block?.rate ?? 1}">
        </label>
        <label>Dialogue Text
            <textarea class="speaker-text" placeholder="Enter the dialogue for this speaker">${block?.text || ""}</textarea>
        </label>
    `;

    speakerList.appendChild(card);

    const langSelect = card.querySelector(".speaker-lang");
    const voiceSelect = card.querySelector(".speaker-voice-select");
    const nameInput = card.querySelector(".speaker-name");
    const pitchInput = card.querySelector(".speaker-pitch");
    const rateInput = card.querySelector(".speaker-rate");
    const textInput = card.querySelector(".speaker-text");
    const removeButton = card.querySelector(".speaker-remove");

    if (langSelect && block?.lang) {
        langSelect.value = block.lang;
    }

    populateVoiceDropdowns();

    if (voiceSelect && block?.voice) {
        voiceSelect.value = block.voice;
    }

    const inputs = [nameInput, langSelect, voiceSelect, pitchInput, rateInput, textInput].filter(Boolean);
    inputs.forEach(input => {
        input.addEventListener("input", () => {
            updateDialogueEditorFromSpeakerCards(speakerList, editor);
        });
    });

    if (removeButton) {
        removeButton.addEventListener("click", () => {
            card.remove();
            updateSpeakerCardHeaders(speakerList);
            updateDialogueEditorFromSpeakerCards(speakerList, editor);
        });
    }

    if (!options.skipSync) {
        updateDialogueEditorFromSpeakerCards(speakerList, editor);
    }
}

function updateSpeakerCardHeaders(speakerList) {
    const cards = speakerList.querySelectorAll(".speaker-card");
    cards.forEach((card, index) => {
        const header = card.querySelector(".speaker-card-header strong");
        if (header) {
            header.textContent = `Speaker ${index + 1}`;
        }
        card.dataset.speakerId = `p${index + 1}`;
    });
}

function updateDialogueEditorFromSpeakerCards(speakerList, editor) {
    const cards = speakerList.querySelectorAll(".speaker-card");
    const script = [...cards].map(card => {
        const speakerId = card.dataset.speakerId || "p1";
        const name = cleanMetaValue(card.querySelector(".speaker-name")?.value || "Unknown Speaker");
        const lang = card.querySelector(".speaker-lang")?.value || "en-US";
        const voice = cleanMetaValue(card.querySelector(".speaker-voice-select")?.value || "");
        const pitch = parseFloat(card.querySelector(".speaker-pitch")?.value) || 1;
        const rate = parseFloat(card.querySelector(".speaker-rate")?.value) || 1;
        const text = (card.querySelector(".speaker-text")?.value || "").trim();
        if (!text) {
            return null;
        }

        const metadata = [`[${speakerId}`, `name=${name}`, `lang=${lang}`];
        if (voice) {
            metadata.push(`voice=${voice}`);
        }
        metadata.push(`pitch=${clamp(pitch, 0.5, 2)}`);
        metadata.push(`rate=${clamp(rate, 0.5, 2)}`);
        return `${metadata.join("|")}]\n${text}`;
    }).filter(Boolean);

    editor.value = script.join("\n\n");
}

function cleanMetaValue(value) {
    return value.replace(/[\[\]\r\n|=]/g, " ").trim();
}

function parseScript(script) {
    if (!script) {
        return [];
    }

    const pattern = /\[(.*?)\]\s*(.*?)(?=\n\[|$)/gs;
    const blocks = [];
    let match;

    while ((match = pattern.exec(script)) !== null) {
        const metaRaw = match[1];
        const text = match[2].trim();
        if (!text) {
            continue;
        }

        const metaParts = metaRaw.split("|");
        const speakerId = metaParts[0]?.trim() || "p1";
        const block = {
            speakerId,
            name: "Unknown Speaker",
            lang: "en-US",
            voice: "",
            pitch: 1,
            rate: 1,
            text: text.replace(/\[(.*?)\]/g, "").trim()
        };

        metaParts.slice(1).forEach(part => {
            const [key, value] = part.split("=");
            if (!key || !value) {
                return;
            }
            const normalized = key.trim().toLowerCase();
            const cleaned = value.trim();
            if (normalized === "name") {
                block.name = cleaned;
            } else if (normalized === "lang") {
                block.lang = cleaned;
            } else if (normalized === "voice") {
                block.voice = cleaned;
            } else if (normalized === "pitch") {
                block.pitch = clamp(Number(cleaned), 0.5, 2);
            } else if (normalized === "rate") {
                block.rate = clamp(Number(cleaned), 0.5, 2);
            }
        });

        blocks.push(block);
    }

    return blocks;
}

function clamp(value, min, max) {
    if (Number.isNaN(value)) {
        return min;
    }
    return Math.max(min, Math.min(value, max));
}

let cachedVoices = [];

function initializeVoiceLoading() {
    loadVoices();
    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = () => {
            loadVoices();
        };
    }
}

function loadVoices() {
    const voices = speechSynthesis.getVoices();
    if (!voices.length) {
        setTimeout(loadVoices, 200);
        return;
    }
    cachedVoices = voices;
    populateVoiceDropdowns();
}

function populateVoiceDropdowns() {
    const dropdowns = document.querySelectorAll(".speaker-voice-select");
    dropdowns.forEach(dropdown => {
        dropdown.innerHTML = "";

        if (!cachedVoices.length) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "Default voice";
            dropdown.appendChild(option);
            return;
        }

        const voicesByLang = {};
        cachedVoices.forEach(voice => {
            if (!voicesByLang[voice.lang]) {
                voicesByLang[voice.lang] = [];
            }
            voicesByLang[voice.lang].push(voice);
        });

        Object.keys(voicesByLang).forEach(lang => {
            const optgroup = document.createElement("optgroup");
            optgroup.label = lang;
            voicesByLang[lang].forEach(voice => {
                const option = document.createElement("option");
                option.value = voice.name;
                option.textContent = `${voice.name}`;
                optgroup.appendChild(option);
            });
            dropdown.appendChild(optgroup);
        });
    });
}

function initializeSyntaxHighlighting() {
    const editor = document.querySelector(".dialogue-script-editor");
    if (!editor) {
        return;
    }

    editor.addEventListener("input", () => {
        highlightDialogueSyntax(editor);
    });
}

function highlightDialogueSyntax(editor) {
    const lines = editor.value.split("\n");
    const preview = document.querySelector(".syntax-preview");
    if (!preview) {
        return;
    }
    preview.innerHTML = "";

    lines.forEach(line => {
        const div = document.createElement("div");
        div.className = "syntax-line";
        if (line.trim().startsWith("[")) {
            div.classList.add("syntax-metadata");
        } else {
            div.classList.add("syntax-dialogue");
        }
        div.textContent = line;
        preview.appendChild(div);
    });
}

function initializeLivePreview() {
    const titleInput = document.querySelector("#title");
    const editor = document.querySelector(".dialogue-script-editor");
    const previewTitle = document.querySelector(".preview-title");
    const previewCaption = document.querySelector(".preview-caption");

    if (!titleInput || !previewTitle) {
        return;
    }

    titleInput.addEventListener("input", () => {
        previewTitle.textContent = titleInput.value || "Untitled Story";
    });

    if (editor && previewCaption) {
        editor.addEventListener("input", () => {
            const text = editor.value.replace(/\[(.*?)\]/g, "").trim();
            previewCaption.textContent = text.slice(0, 180) || "Dialogue preview...";
        });
    }
}

function initializeAudioUploadPreview() {
    const input = document.querySelector("#audioUpload");
    const label = document.querySelector(".audio-upload-label");
    if (!input || !label) {
        return;
    }

    input.addEventListener("change", () => {
        const file = input.files[0];
        if (!file) {
            label.textContent = "Choose audio file";
            return;
        }
        label.textContent = `${file.name} selected`;
    });
}

function initializePlaybackButtons() {
    const buttons = document.querySelectorAll(".play-button");
    buttons.forEach(button => {
        button.addEventListener("click", () => {
            const card = button.closest(".feed-card, .post-page");
            if (!card) {
                return;
            }
            button.classList.add("play-button-active");
            setTimeout(() => button.classList.remove("play-button-active"), 500);
        });
    });
}

function initializeProgressBars() {
    const bars = document.querySelectorAll(".progress-fill");
    bars.forEach(bar => {
        const percent = parseFloat(bar.dataset.progress || 0);
        requestAnimationFrame(() => {
            bar.style.width = `${percent}%`;
        });
    });
}

function initializePlaybackSpeedControl() {
    const speed = document.querySelector("#playbackSpeed");
    if (!speed) {
        return;
    }

    speed.addEventListener("change", () => {
        App.currentPlaybackSpeed = parseFloat(speed.value);
    });
}

function initializeSearch() {
    const input = document.querySelector(".feed-search");
    if (!input) {
        return;
    }

    input.addEventListener("input", debounce(() => {
        const cards = document.querySelectorAll(".feed-card");
        const query = input.value.toLowerCase();
        cards.forEach(card => {
            const title = card.dataset.title || "";
            const visible = title.toLowerCase().includes(query);
            card.style.display = visible ? "" : "none";
        });
    }, 200));
}

function initializeModals() {
    const triggers = document.querySelectorAll("[data-modal]");
    triggers.forEach(trigger => {
        trigger.addEventListener("click", () => {
            const modalId = trigger.dataset.modal;
            openModal(modalId);
        });
    });

    const closers = document.querySelectorAll(".modal-close");
    closers.forEach(closer => {
        closer.addEventListener("click", closeModal);
    });
}

function openModal(id) {
    const modal = document.querySelector(`#${id}`);
    if (!modal) {
        return;
    }
    modal.classList.add("modal-visible");
    App.activeModal = modal;
}

function closeModal() {
    if (!App.activeModal) {
        return;
    }
    App.activeModal.classList.remove("modal-visible");
    App.activeModal = null;
}

function initializeTooltips() {
    const items = document.querySelectorAll("[data-tooltip]");
    items.forEach(item => {
        item.addEventListener("mouseenter", () => {
            const tooltip = document.createElement("div");
            tooltip.className = "tooltip";
            tooltip.textContent = item.dataset.tooltip;
            document.body.appendChild(tooltip);
            const rect = item.getBoundingClientRect();
            tooltip.style.left = `${rect.left}px`;
            tooltip.style.top = `${rect.top - 40}px`;
            item._tooltip = tooltip;
        });

        item.addEventListener("mouseleave", () => {
            if (item._tooltip) {
                item._tooltip.remove();
                item._tooltip = null;
            }
        });
    });
}

function initializeKeyboardShortcuts() {
    document.addEventListener("keydown", e => {
        if (e.key === "Escape") {
            closeModal();
        }
    });
}

function initializeSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');
    links.forEach(link => {
        link.addEventListener("click", e => {
            const target = document.querySelector(link.getAttribute("href"));
            if (!target) {
                return;
            }
            e.preventDefault();
            target.scrollIntoView({ behavior: "smooth" });
        });
    });
}

function initializeAnimations() {
    const animated = document.querySelectorAll(".animate-on-load");
    animated.forEach((el, index) => {
        setTimeout(() => {
            el.classList.add("animated-visible");
        }, index * 120);
    });
}

function debounce(callback, delay = 250) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => callback(...args), delay);
    };
}

window.addEventListener("error", event => {
    console.error("Frontend Error:", event.message, event.error || "no stack");
});

window.addEventListener("unhandledrejection", event => {
    console.error("Unhandled Promise Rejection:", event.reason);
});

window.addEventListener("beforeunload", () => {
    document.body.classList.add("page-transition-out");
});
