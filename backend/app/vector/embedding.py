"""
Module D support — embedding provider abstraction (Phase 5, DEC-012).

Honest scope statement
----------------------
The pilot runs on an 8 GB laptop with no model server (Phase 5 explicitly says
not to install Ollama), and the `sentence-transformers` dependency listed in
requirements.txt would download several hundred MB of weights on first use.
Rather than block Phase 5 on that, the default provider is a **deterministic
lexical embedder**, not a semantic neural model:

    HashingEmbeddingProvider  — feature hashing over word unigrams/bigrams,
                                character 3-5 grams, L2-normalised, 384 dims.

It captures lexical overlap (which is what this small, terminology-dense
knowledge base actually needs — "pink bollworm", "bacterial blight", "neem
kernel extract") and it is reproducible byte-for-byte, so similarity-search
tests can assert exact neighbours instead of hoping a model downloads.

What it is NOT: it has no notion of synonymy ("bollworm" ≠ "larva"), no cross-
lingual ability, and no semantic generalisation. Any claim that retrieval is
"semantic" would be false with this provider. `EmbeddingProvider` exists so a
real model (`SentenceTransformerProvider`, below, requiring the optional extra)
can be swapped in without touching the store, the schema, or the importer — but
swapping providers changes the vector space, so the importer must re-run, and
`embedding_model` on every row makes a mixed-provider index detectable instead
of silently wrong.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Iterable

EMBEDDING_DIM = 384
DEFAULT_MODEL_ID = "hashing-lexical-v1"

# Same Devanagari lesson as the classifier (DEC-011): Python's \w excludes
# combining marks, so a naive tokenizer would split "धान" into "ध" + "न".
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_WORD_RE = re.compile(r"[A-Za-z\u0900-\u097F0-9]+", re.UNICODE)


def normalize(text: str) -> str:
    """NFKC + lowercase; whitespace collapsed. Language-agnostic."""
    folded = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", folded).strip()


def _stable_hash(token: str, salt: str) -> tuple[int, int]:
    """
    Deterministic bucket + sign from a stable digest.

    Python's built-in hash() is salted per process (PYTHONHASHSEED), which would
    make stored vectors unusable across runs. A truncated SHA-256 does not.
    """
    digest = hashlib.sha256(f"{salt}\x1f{token}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
    sign = 1.0 if digest[4] & 1 else -1.0
    return bucket, sign


class EmbeddingProvider(ABC):
    """Provider-agnostic embedder, mirroring the DEC-004 LLMProvider pattern."""

    model_id: str
    dim: int

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class HashingEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic lexical embedder (see module docstring for what it is not).

    Word features are hashed with a signed bucket so collisions cancel on
    average instead of accumulating; character n-grams make the vector robust to
    morphology and to the transliterated-Hindi spellings in the dataset
    ("kida", "keet", "keeda"). The result is L2-normalised, so cosine similarity
    and dot product agree and stored values stay in a bounded range.
    """

    model_id = DEFAULT_MODEL_ID
    dim = EMBEDDING_DIM

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        norm_text = normalize(text)
        if not norm_text:
            return vec

        words = _WORD_RE.findall(norm_text)
        for word in words:
            bucket, sign = _stable_hash(f"w:{word}", "word")
            vec[bucket] += sign * 1.0

        for first, second in zip(words, words[1:]):
            bucket, sign = _stable_hash(f"b:{first} {second}", "bigram")
            vec[bucket] += sign * 0.5

        # Character n-grams over the space-stripped text keep word-boundary
        # information while tolerating internal spelling variation.
        compact = norm_text.replace(" ", "_")
        for n in (3, 4, 5):
            for i in range(len(compact) - n + 1):
                gram = compact[i:i + n]
                bucket, sign = _stable_hash(f"c{n}:{gram}", f"char{n}")
                vec[bucket] += sign * 0.25

        magnitude = math.sqrt(sum(v * v for v in vec))
        if magnitude == 0.0:
            return vec
        return [v / magnitude for v in vec]


class SentenceTransformerProvider(EmbeddingProvider):
    """
    Optional real semantic embedder. Requires the `sentence-transformers` extra
    (declared in requirements.txt but not installed for the pilot) and downloads
    model weights on first use — which is why it is not the default.

    Import is deferred so the application starts normally without the package.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "SentenceTransformerProvider requires the optional 'sentence-transformers' "
                "dependency, which is not installed. Use the default hashing provider."
            ) from exc
        self._model = SentenceTransformer(model_name)
        self.model_id = f"st:{model_name.split('/')[-1]}"
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode(normalize(text), normalize_embeddings=True)
        return [float(v) for v in vector]


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """
    Factory. Selection is by environment variable only, defaulting to the
    offline provider, so no code path silently depends on a network download.
    """
    import os

    choice = os.getenv("EMBEDDING_PROVIDER", "hashing").strip().lower()
    if choice in ("", "hashing", "lexical", "default"):
        return HashingEmbeddingProvider()
    if choice in ("sentence-transformer", "sentence_transformers", "st"):
        return SentenceTransformerProvider()
    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER '{choice}'. Supported: 'hashing' (default), 'sentence-transformer'."
    )


def reset_embedding_provider_cache() -> None:
    get_embedding_provider.cache_clear()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Reference cosine similarity. Raises on a dimension mismatch instead of
    returning a meaningless number.
    """
    if len(a) != len(b):
        raise ValueError(f"vector dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
