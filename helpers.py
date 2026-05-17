import os
import re
import random
from datetime import datetime
from functools import wraps

from flask import redirect, render_template, session, request, jsonify

# =========================================================
# CONFIG
# =========================================================

ALLOWED_AUDIO_EXTENSIONS = {
    "mp3",
    "wav",
    "ogg",
    "m4a"
}

SUPPORTED_LANGUAGES = {
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "fr-CA": "French (Canada)",
    "fr-FR": "French (France)",
    "es-ES": "Spanish",
    "de-DE": "German",
    "it-IT": "Italian",
    "pt-BR": "Portuguese (Brazil)"
}

DEFAULT_LANGUAGE = "en-US"

DEFAULT_VOICE = "Default"

DEFAULT_AVATARS = [
    "👤",
    "👑",
    "⚔️",
    "🏛️",
    "📜",
    "🛡️",
    "🗡️",
    "🐎",
    "🏰",
    "🕰️",
    "🌍",
    "🎩",
    "🪶",
]

# =========================================================
# AUTH DECORATOR
# =========================================================

def login_required(f):
    """
    Protect routes requiring authentication.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if session.get("user_id") is None:
            if request.path.startswith("/api"):
                return jsonify({"success": False, "message": "Authentication required."}), 401
            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function


# =========================================================
# APOLOGY / ERROR RENDERER
# =========================================================

def apology(message, code=400):
    """
    Render cinematic error page.
    """

    return render_template(
        "apology.html",
        top=code,
        bottom=message,
        title="Error"
    ), code


# =========================================================
# AUDIO VALIDATION
# =========================================================

def allowed_audio_file(filename):
    """
    Validate uploaded audio file extension.
    """

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_AUDIO_EXTENSIONS


# =========================================================
# AVATAR GENERATOR
# =========================================================

def generate_avatar():
    """
    Return random emoji avatar.
    """

    return random.choice(DEFAULT_AVATARS)


def sanitize_avatar(value):
    """
    Ensure avatars are emoji-only and avoid legacy image values.
    """

    if not value or not isinstance(value, str):
        return "👤"

    avatar = value.strip()

    if not avatar:
        return "👤"

    if re.search(r'[A-Za-z0-9_/\\.]', avatar):
        return "👤"

    return avatar


# =========================================================
# LANGUAGE HELPERS
# =========================================================

def get_language_name(code):
    """
    Convert language code into readable label.
    """

    return SUPPORTED_LANGUAGES.get(code, "Unknown")


def validate_language(code):
    """
    Validate language support.
    """

    return code in SUPPORTED_LANGUAGES


# =========================================================
# TIME FORMATTING
# =========================================================

def format_timestamp(timestamp):
    """
    Convert database timestamp into relative time.
    """

    try:

        dt = datetime.strptime(
            timestamp,
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception:
        return "Unknown time"

    now = datetime.now()

    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "Just now"

    if seconds < 3600:
        minutes = int(seconds // 60)

        return f"{minutes}m ago"

    if seconds < 86400:
        hours = int(seconds // 3600)

        return f"{hours}h ago"

    if seconds < 604800:
        days = int(seconds // 86400)

        return f"{days}d ago"

    return dt.strftime("%b %d, %Y")


# =========================================================
# SAFE VALUE CLAMPING
# =========================================================

def clamp(value, minimum, maximum):
    """
    Clamp numeric values safely.
    """

    return max(minimum, min(value, maximum))


# =========================================================
# DIALOGUE PARSER
# =========================================================

def parse_dialogue_script(script):
    """
    Parse encoded dialogue script blocks.

    Example:

    [p1|name=Napoleon|lang=fr-CA|voice=Microsoft Claude|pitch=0.9|rate=1]
    Bonjour.

    Returns structured dialogue objects.
    """

    if not script:
        return []

    script = script.strip()

    # =====================================================
    # REGEX BLOCK PARSER
    # =====================================================

    pattern = r"\[(.*?)\]\s*(.*?)(?=\n\[|$)"

    matches = re.findall(
        pattern,
        script,
        flags=re.DOTALL | re.MULTILINE
    )

    parsed_segments = []

    for metadata, text in matches:

        try:

            metadata = metadata.strip()

            text = text.strip()

            if not text:
                continue

            metadata_parts = metadata.split("|")

            speaker_id = metadata_parts[0].strip()

            data = {
                "speaker_id": speaker_id,
                "name": "Unknown Speaker",
                "voice": DEFAULT_VOICE,
                "lang": DEFAULT_LANGUAGE,
                "pitch": 1.0,
                "rate": 1.0,
                "text": clean_dialogue_text(text),
            }

            # =============================================
            # PARSE KEY/VALUE METADATA
            # =============================================

            for item in metadata_parts[1:]:

                if "=" not in item:
                    continue

                key, value = item.split("=", 1)

                key = key.strip().lower()

                value = value.strip()

                if key == "name":

                    data["name"] = value[:80]

                elif key == "voice":

                    data["voice"] = value[:120]

                elif key == "lang":

                    if validate_language(value):
                        data["lang"] = value

                elif key == "pitch":

                    try:

                        pitch = float(value)

                        data["pitch"] = clamp(
                            pitch,
                            0.5,
                            2.0
                        )

                    except Exception:
                        pass

                elif key == "rate":

                    try:

                        rate = float(value)

                        data["rate"] = clamp(
                            rate,
                            0.5,
                            2.0
                        )

                    except Exception:
                        pass

            parsed_segments.append(data)

        except Exception:
            continue

    return parsed_segments


# =========================================================
# DIALOGUE ENCODER
# =========================================================

def encode_dialogue_script(dialogue_blocks):
    """
    Convert structured dialogue into encoded script.

    dialogue_blocks example:

    [
        {
            "speaker_id": "p1",
            "name": "Napoleon",
            "lang": "fr-CA",
            "voice": "Microsoft Claude",
            "pitch": 1,
            "rate": 1,
            "text": "Bonjour."
        }
    ]
    """

    encoded = []

    for block in dialogue_blocks:

        speaker_id = block.get("speaker_id", "p1")

        name = block.get("name", "Unknown Speaker")

        lang = block.get("lang", DEFAULT_LANGUAGE)

        voice = block.get("voice", DEFAULT_VOICE)

        pitch = clamp(
            float(block.get("pitch", 1)),
            0.5,
            2.0
        )

        rate = clamp(
            float(block.get("rate", 1)),
            0.5,
            2.0
        )

        text = clean_dialogue_text(
            block.get("text", "")
        )

        metadata = (
            f"[{speaker_id}"
            f"|name={name}"
            f"|lang={lang}"
            f"|voice={voice}"
            f"|pitch={pitch}"
            f"|rate={rate}]"
        )

        encoded.append(f"{metadata}\n{text}")

    return "\n\n".join(encoded)


# =========================================================
# DIALOGUE CLEANER
# =========================================================

def clean_dialogue_text(text):
    """
    Remove dangerous or malformed content safely.
    """

    if not text:
        return ""

    # Normalize spacing
    text = re.sub(r"\r\n", "\n", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove metadata-like nested tags
    text = re.sub(r"\[(.*?)\]", "", text)

    # Strip dangerous whitespace
    text = text.strip()

    return text


# =========================================================
# SENTENCE SPLITTER
# =========================================================

def split_sentences(text):
    """
    Split dialogue into sentence captions.
    """

    if not text:
        return []

    sentences = re.split(
        r'(?<=[.!?])\s+',
        text
    )

    return [
        s.strip()
        for s in sentences
        if s.strip()
    ]


# =========================================================
# READING TIME ESTIMATION
# =========================================================

def estimate_reading_time(text):
    """
    Estimate reading time in minutes.
    """

    if not text:
        return 1

    words = len(text.split())

    minutes = max(1, round(words / 200))

    return minutes


# =========================================================
# SPEAKER EXTRACTION
# =========================================================

def extract_speakers(script):
    """
    Return unique speakers from dialogue.
    """

    parsed = parse_dialogue_script(script)

    speakers = []

    seen = set()

    for segment in parsed:

        speaker_key = (
            segment["speaker_id"],
            segment["name"]
        )

        if speaker_key in seen:
            continue

        seen.add(speaker_key)

        speakers.append({
            "speaker_id": segment["speaker_id"],
            "name": segment["name"],
            "voice": segment["voice"],
            "lang": segment["lang"],
        })

    return speakers


# =========================================================
# SCRIPT VALIDATION
# =========================================================

def validate_dialogue_script(script):
    """
    Validate encoded dialogue integrity.
    """

    parsed = parse_dialogue_script(script)

    if not parsed:
        return False, "No valid dialogue blocks found."

    for segment in parsed:

        if not segment["text"]:
            return False, "Dialogue contains empty lines."

        if len(segment["text"]) > 5000:
            return False, "Dialogue segment too large."

    return True, "Valid"


# =========================================================
# SEARCH SANITIZER
# =========================================================

def sanitize_search_query(query):
    """
    Clean search input safely.
    """

    if not query:
        return ""

    query = query.strip()

    query = re.sub(r"[^\w\s\-']", "", query)

    return query[:100]


# =========================================================
# SAFE INTEGER PARSER
# =========================================================

def safe_int(value, default=0):
    """
    Safe integer conversion.
    """

    try:
        return int(value)

    except Exception:
        return default


# =========================================================
# FILE SIZE FORMATTER
# =========================================================

def format_file_size(size_bytes):
    """
    Human readable file size.
    """

    if size_bytes < 1024:
        return f"{size_bytes} B"

    if size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"

    return f"{round(size_bytes / (1024 * 1024), 1)} MB"