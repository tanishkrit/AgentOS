"""
LLM Client — Shared Interface to Local Ollama

Provides a reusable, configurable client for making inference requests
to the locally-hosted Ollama LLM. Used by the Planner for task
decomposition and by specialized agents for data extraction,
content generation, and dynamic reasoning.

All LLM calls in the project should go through this module.
"""

import json
import logging
import re
import requests
from typing import Optional

from src.config import Config

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Centralized client for local Ollama LLM inference.

    Features:
    - System + user prompt support
    - JSON output mode with automatic extraction
    - Configurable temperature and token limits
    - Graceful fallback when Ollama is unavailable
    - Singleton-style availability check (checked once, cached)
    """

    _instance: Optional["LLMClient"] = None
    _available: Optional[bool] = None

    def __init__(self) -> None:
        self._base_url = Config.OLLAMA_BASE_URL.rstrip("/")
        self._model = Config.OLLAMA_MODEL
        self._api_key = Config.OLLAMA_API_KEY

    @classmethod
    def get_instance(cls) -> "LLMClient":
        """Return a shared singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reconfigure(self) -> None:
        """
        Reload settings from Config (e.g. after the user changes the
        model or base URL via the Settings panel). Also resets the
        cached availability flag.
        """
        self._base_url = Config.OLLAMA_BASE_URL.rstrip("/")
        self._model = Config.OLLAMA_MODEL
        self._api_key = Config.OLLAMA_API_KEY
        LLMClient._available = None
        logger.info(
            f"LLMClient reconfigured: model={self._model}, "
            f"url={self._base_url}"
        )

    @property
    def available(self) -> bool:
        """Check if Ollama is reachable (cached after first check)."""
        if LLMClient._available is None:
            LLMClient._available = self._check_availability()
        return LLMClient._available

    def reset_availability(self) -> None:
        """Force re-check of Ollama availability on next call."""
        LLMClient._available = None

    @classmethod
    def list_local_models(cls) -> list[dict]:
        """
        Query the local Ollama server for all downloaded models.

        Returns a list of dicts with 'name' and 'size' keys, e.g.:
          [{"name": "qwen2.5:7b", "size": "4.7 GB"}, ...]
        Returns an empty list if Ollama is unreachable.
        """
        instance = cls.get_instance()
        try:
            headers = {}
            if instance._api_key:
                headers["Authorization"] = f"Bearer {instance._api_key}"
            resp = requests.get(
                f"{instance._base_url}/api/tags",
                headers=headers,
                timeout=5,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            models = []
            for m in data.get("models", []):
                size_bytes = m.get("size", 0)
                if size_bytes > 1_000_000_000:
                    size_str = f"{size_bytes / 1_000_000_000:.1f} GB"
                else:
                    size_str = f"{size_bytes / 1_000_000:.0f} MB"
                models.append({
                    "name": m.get("name", "unknown"),
                    "size": size_str,
                })
            return models
        except Exception as e:
            logger.warning(f"Failed to list local models: {e}")
            return []

    def _check_availability(self) -> bool:
        """Ping the Ollama server to see if it's reachable."""
        try:
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            resp = requests.get(
                f"{self._base_url}/api/tags",
                headers=headers,
                timeout=5,
            )
            if resp.status_code == 200:
                logger.info(f"Ollama is available at {self._base_url}")
                return True
            else:
                logger.warning(
                    f"Ollama returned status {resp.status_code}. LLM features disabled."
                )
                return False
        except requests.ConnectionError:
            logger.warning(
                f"Cannot connect to Ollama at {self._base_url}. LLM features disabled."
            )
            return False
        except Exception as e:
            logger.warning(f"Ollama availability check failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> Optional[str]:
        """
        Send a prompt to Ollama and return the raw text response.

        Args:
            prompt: The user prompt / question.
            system: Optional system prompt for role/context setting.
            temperature: Creativity control (0.0 = deterministic, 1.0 = creative).
            max_tokens: Maximum number of tokens to generate.
            timeout: HTTP request timeout in seconds.

        Returns:
            The generated text string, or None if Ollama is unavailable/errors.
        """
        if not self.available:
            return None

        try:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            payload = {
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }
            if system:
                payload["system"] = system

            resp = requests.post(
                f"{self._base_url}/api/generate",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()

            raw_text = resp.json().get("response", "").strip()
            logger.debug(f"LLM response length: {len(raw_text)} chars")
            return raw_text

        except requests.Timeout:
            logger.warning("Ollama request timed out.")
            return None
        except requests.RequestException as e:
            logger.error(f"Ollama API call failed: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None

    def generate_json(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> Optional[dict]:
        """
        Send a prompt and parse the response as JSON.

        Handles common LLM quirks: markdown code fences, extra text
        before/after the JSON object, etc.

        Returns:
            Parsed dict/list, or None if parsing fails or Ollama is unavailable.
        """
        # Append an instruction to ensure JSON output
        json_prompt = prompt + "\n\nRespond ONLY with valid JSON. No extra text."

        raw = self.generate(
            prompt=json_prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        if raw is None:
            return None

        return self._extract_json(raw)

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract and parse JSON from LLM output, handling code fences."""
        # Strip markdown code fences if present
        if "```" in text:
            match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        # Try to find a JSON object
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                cleaned_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', '', json_match.group(0))
                return json.loads(cleaned_text)
            except json.JSONDecodeError:
                pass

        # Try to find a JSON array
        array_match = re.search(r"\[.*\]", text, re.DOTALL)
        if array_match:
            try:
                cleaned_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', '', array_match.group(0))
                result = json.loads(cleaned_text)
                return {"items": result} if isinstance(result, list) else result
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to extract JSON from LLM response: {text[:200]}")
        return None

    def summarize(self, text: str, max_length: int = 200) -> Optional[str]:
        """Generate a concise summary of the given text."""
        return self.generate(
            prompt=f"Summarize the following text in {max_length} characters or less:\n\n{text[:3000]}",
            system="You are a concise summarizer. Output only the summary, nothing else.",
            temperature=0.1,
            max_tokens=256,
            timeout=30,
        )

    def extract_structured_data(
        self,
        raw_text: str,
        fields: list[str],
        context: str = "",
    ) -> Optional[dict]:
        """
        Extract structured fields from raw text using the LLM.

        Args:
            raw_text: The raw scraped/input text to extract from.
            fields: List of field names to extract (e.g. ["name", "address", "rating"]).
            context: Additional context about what data is expected.

        Returns:
            A dict with the requested fields, or None if extraction fails.
        """
        fields_str = ", ".join(f'"{f}"' for f in fields)

        system = (
            "You are a precise data extraction engine. "
            "Extract the requested fields from the provided text. "
            "If a field cannot be found, set its value to null. "
            "Return ONLY valid JSON."
        )

        prompt = f"""Extract the following fields from this text: [{fields_str}]

{f"Context: {context}" if context else ""}

Text:
\"\"\"
{raw_text[:3000]}
\"\"\"

Return a JSON object with these exact field names as keys."""

        return self.generate_json(
            prompt=prompt,
            system=system,
            temperature=0.1,
            max_tokens=1024,
            timeout=30,
        )

    def extract_structured_list(
        self,
        raw_text: str,
        fields: list[str],
        context: str = "",
    ) -> list[dict]:
        """
        Extract a list of structured items from raw text using the LLM.

        Args:
            raw_text: The raw scraped/input text to extract from.
            fields: List of field names to extract (e.g. ["name", "phone", "email"]).
            context: Additional context about what data is expected.

        Returns:
            A list of dicts with the requested fields, or an empty list.
        """
        if not self.available:
            return []

        fields_str = ", ".join(f'"{f}"' for f in fields)

        system = (
            "You are a precise data extraction engine. "
            "Extract all occurrences/entities of interest from the provided text. "
            "For each entity, extract the requested fields. "
            "If a field cannot be found, set its value to null. "
            "Return ONLY a valid JSON list of objects."
        )

        prompt = f"""Extract all items from the text. For each item, extract these fields: [{fields_str}]

{f"Context: {context}" if context else ""}

Text:
\"\"\"
{raw_text[:6000]}
\"\"\"

Return a valid JSON array of objects, like:
[
  {{
    "name": "Item Name",
    "phone": "Item Phone",
    "email": "Item Email"
  }}
]"""

        try:
            res = self.generate_json(
                prompt=prompt,
                system=system,
                temperature=0.1,
                max_tokens=2048,
                timeout=60,
            )

            if res is None:
                return []

            if isinstance(res, list):
                return res
            elif isinstance(res, dict):
                # Unpack common wrapper keys
                for key in ["items", "data", "results", "entities"]:
                    if key in res and isinstance(res[key], list):
                        return res[key]
                return [res]
            return []
        except Exception as e:
            logger.error(f"Structured list extraction failed: {e}")
            return []
