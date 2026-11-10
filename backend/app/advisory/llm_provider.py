"""
Module F — AI Advisory Module: LLM Provider abstraction.

Per DEC-004 (Decision Log), the system must access the LLM through a
provider-agnostic interface so Ollama (default, local) can be swapped for a
cloud LLM API later WITHOUT changing Modules B-E or the prompt-construction
logic in Module F.

IMPORTANT (Phase 2 scope): this module only defines the interface and the
Ollama implementation's connectivity/health check. It does NOT construct
advisory prompts or call the LLM to answer agricultural questions yet -
that integration belongs to Phase 7 (AI Advisory Integration), after the
rule engine (Phase 6) exists to gate what the LLM is allowed to see.
"""
from abc import ABC, abstractmethod

import requests

from app.core.config import get_settings


class LLMProvider(ABC):
    """Provider-agnostic interface. Every concrete provider must implement these methods."""

    @abstractmethod
    def generate(self, prompt: str, language: str = "en") -> str:
        """Generate text from a prompt. Must only paraphrase/translate content
        already present in the prompt - never used to originate agricultural facts."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> tuple[bool, str]:
        """Returns (is_available, message) without raising."""
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    """Default/initial provider (DEC-004): calls a locally running Ollama server."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model

    def health_check(self) -> tuple[bool, str]:
        """
        Checks whether the Ollama server is reachable and whether the configured
        model has been pulled locally. Never raises; used by health-check endpoint
        and Phase 2 setup verification.
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in tags]
            if not model_names:
                return False, (
                    f"Ollama server reachable at {self.base_url}, but no models are pulled. "
                    f"Run: ollama pull {self.model}"
                )
            if self.model not in model_names:
                return False, (
                    f"Ollama server reachable at {self.base_url}, but configured model "
                    f"'{self.model}' is not pulled. Available models: {model_names}. "
                    f"Run: ollama pull {self.model}"
                )
            return True, f"Ollama server reachable at {self.base_url}; model '{self.model}' is available."
        except requests.exceptions.ConnectionError:
            return False, (
                f"Could not connect to Ollama server at {self.base_url}. "
                f"Is Ollama installed and running? See docs/chapters/ or "
                f"PHASE2_SETUP_REPORT.md for installation instructions."
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"Ollama health check failed: {exc}"

    def generate(self, prompt: str, language: str = "en") -> str:
        """
        Phase 2 scope: not yet wired into any advisory flow (no prompts are
        constructed from agricultural data yet - that is Phase 7). Implemented
        here only so the interface contract is real and testable, not a stub
        that silently does nothing.
        """
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


class CloudAPIProvider(LLMProvider):
    """
    Placeholder for a future cloud LLM API provider (per DEC-004).
    NOT implemented in Phase 2 - added here only to document the extension
    point so adding a real implementation later requires no redesign of
    Modules B-E or of how Module F selects a provider.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def health_check(self) -> tuple[bool, str]:
        return False, "CloudAPIProvider is not implemented yet (reserved for post-pilot use)."

    def generate(self, prompt: str, language: str = "en") -> str:
        raise NotImplementedError("CloudAPIProvider is not implemented yet (reserved for post-pilot use).")


def get_llm_provider() -> LLMProvider:
    """Factory: returns the configured provider based on LLM_PROVIDER env var."""
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return OllamaProvider()
    if settings.llm_provider == "cloud":
        return CloudAPIProvider(api_key=settings.cloud_llm_api_key)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
