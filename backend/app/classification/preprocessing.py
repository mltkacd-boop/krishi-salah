"""
Module B — text preprocessing and language handling.

Deliberately lightweight and dependency-free (no external NLP model, no
tokenizer download): the classifier must run inside the API process with no
network access and no GPU, and must stay independent of PostgreSQL and Ollama.

Two things happen here:
1. `normalize_text` — a single canonical form used for *both* training and
   inference. Normalising identically in both places is what prevents
   train/serve skew, a common silent failure in text pipelines.
2. `detect_language` — a transparent heuristic (script ratio + romanised-Hindi
   markers), not a trained language-ID model. It is used only to report the
   detected language to the API caller and to let the frontend pick a reply
   language later; classification itself is language-agnostic, because the
   TF-IDF features are learned from mixed-language training text.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Final

# Devanagari block: U+0900–U+097F (covers Hindi).
_DEVANAGARI_RE: Final[re.Pattern[str]] = re.compile(r"[\u0900-\u097F]")
# Keep unicode word characters and the Devanagari block; turn everything else
# (punctuation, emoji, control chars) into a space so it cannot act as a
# spurious feature.
#
# The explicit Devanagari range is REQUIRED, not defensive: Python's `\w` does
# not match Devanagari combining marks (Unicode category Mn) — the vowel signs
# (matras) and the nukta. Without the explicit range, `re.sub(r"[^\w\s]+", " ")`
# turns "धान" into "ध न" and "कीड़ा" into "क ड", corrupting every Hindi word
# into look-alike consonant fragments. That bug is silent (the model still
# trains, just on mutilated text), so it is guarded by a regression test in
# backend/tests/test_classification.py.
_NON_WORD_RE: Final[re.Pattern[str]] = re.compile(r"[^\w\s\u0900-\u097F]+", re.UNICODE)
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")

# Romanised-Hindi function/content words. Chosen to be words that are *not*
# ordinary English words, so a hit is real evidence of Hinglish rather than
# noise. Deliberately excludes tokens that are also English ("spray", "crop").
_ROMANISED_HINDI_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "kya", "kaise", "kaisa", "kaisi", "kitna", "kitni", "kitne", "kab",
        "kahan", "kyun", "kyon", "hai", "hain", "hoga", "hogi", "nahi", "nahin",
        "me", "mein", "ke", "ki", "ka", "ko", "se", "par", "aur", "ya",
        "dawa", "keeda", "keede", "kida", "kit", "rog", "rogai", "fasal",
        "fasal", "khet", "kheti", "bhao", "bhav", "matra", "chhidkav",
        "chhidkate", "todne", "todai", "todaai", "batao", "bataiye", "karein",
        "karun", "savdhani", "surakshit", "suraksha", "jhulsa", "sundi",
        "maahu", "deemak", "ganna", "aalu", "pyaz", "gehu", "dhan", "makka",
        "kapas", "tamatar", "bad", "ghata", "lag", "gaya", "gayi", "hue",
    }
)

LANGUAGE_ENGLISH: Final[str] = "en"
LANGUAGE_HINDI: Final[str] = "hi"
LANGUAGE_HINGLISH: Final[str] = "hi-latn"
LANGUAGE_UNKNOWN: Final[str] = "unknown"

# Fraction of Devanagari characters above which the query is treated as Hindi.
_DEVANAGARI_RATIO_FOR_HINDI: Final[float] = 0.30


def normalize_text(text: str) -> str:
    """
    Canonical form used identically at training time and inference time.

    - NFKC normalisation (collapses visually identical Devanagari variants and
      full-width forms, so two spellings of the same word share features).
    - Lowercase (affects Latin script only; Devanagari has no case).
    - Punctuation, digits-adjacent symbols and emoji replaced by spaces.
    - Whitespace collapsed and trimmed.

    Digits are preserved: "60 ml" vs "2.5 kg" is a meaningful distinction even
    though the classifier never interprets the quantity.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = _NON_WORD_RE.sub(" ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


def token_count(normalized_text: str) -> int:
    """Number of whitespace tokens in already-normalized text."""
    return len(normalized_text.split()) if normalized_text else 0


def detect_language(text: str) -> str:
    """
    Report the query language as `hi` (Devanagari), `hi-latn` (romanised Hindi),
    `en`, or `unknown` for text with no letters at all.

    This is a heuristic used for *reporting*, never for routing: the model is
    trained on all three forms together. An honest heuristic (rather than a
    trained classifier) is the right choice here because no labelled
    language-identification corpus exists in this project, and claiming a
    trained language detector would overstate what was built.
    """
    if not text or not text.strip():
        return LANGUAGE_UNKNOWN

    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        # Digits/punctuation only (e.g. "60 ml" is fine, but "123" is not).
        return LANGUAGE_UNKNOWN

    devanagari = len(_DEVANAGARI_RE.findall(text))
    if devanagari / len(letters) >= _DEVANAGARI_RATIO_FOR_HINDI:
        return LANGUAGE_HINDI

    tokens = set(normalize_text(text).split())
    marker_hits = len(tokens & _ROMANISED_HINDI_MARKERS)
    if marker_hits >= 2 or (marker_hits >= 1 and len(tokens) <= 5):
        return LANGUAGE_HINGLISH

    return LANGUAGE_ENGLISH


__all__ = [
    "normalize_text",
    "token_count",
    "detect_language",
    "LANGUAGE_ENGLISH",
    "LANGUAGE_HINDI",
    "LANGUAGE_HINGLISH",
    "LANGUAGE_UNKNOWN",
]
