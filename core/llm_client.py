"""OpenAI-compatible LLM client."""

from typing import Optional, List, Dict, Any
from openai import OpenAI
import os
import yaml
from pathlib import Path

def load_settings() -> Dict[str, Any]:
    """Load optional settings from core/configs/settings.yaml."""
    config_paths = [
        Path(__file__).parent / "configs" / "settings.yaml",
        Path(__file__).parent.parent / "core" / "configs" / "settings.yaml",
        Path("core/configs/settings.yaml"),
    ]

    for config_path in config_paths:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

    print("[Warning] settings.yaml was not found; using defaults")
    return {}


class LLMClient:
    """Small wrapper around an OpenAI-compatible chat-completions API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize the client from arguments, environment, or settings."""
        settings = load_settings()
        llm_config = settings.get("llm", {})

        self.base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or llm_config.get("base_url")
            or "https://api.openai.com/v1"
        )

        self.api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or llm_config.get("api_key")
            or "EMPTY"
        )

        self.model = (
            model
            or os.getenv("OPENAI_MODEL")
            or llm_config.get("model")
            or "gpt-5.5"
        )

        self.default_temperature = llm_config.get("default_temperature", 0.2)
        self.default_max_tokens = llm_config.get("default_max_tokens", 1024)
        self.temperatures = llm_config.get("temperatures", {})

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        print(f"[LLMClient] Initialized model: {self.model}")

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        task_type: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Run a non-streaming chat completion."""
        if temperature is None:
            if task_type and task_type in self.temperatures:
                temperature = self.temperatures[task_type]
            else:
                temperature = self.default_temperature

        if max_tokens is None:
            max_tokens = self.default_max_tokens

        if "gpt-5" in self.model.lower():
            temperature = 1

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        print(f"[LLMClient] Calling model: {self.model}, temperature={temperature}, max_tokens={max_tokens}")

        try:
            if "gpt-5" in self.model.lower() or "o1" in self.model.lower():
                token_param = {"max_completion_tokens": max_tokens}
            else:
                token_param = {"max_tokens": max_tokens}

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                **token_param,
                **kwargs,
            )

            output = response.choices[0].message.content

            print(f"[LLMClient] Response length: {len(output)} characters")

            return output

        except Exception as e:
            print(f"[LLMClient] Call failed: {e}")
            raise

    def chat_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        task_type: Optional[str] = None,
        **kwargs,
    ):
        """Run a streaming chat completion."""
        if temperature is None:
            if task_type and task_type in self.temperatures:
                temperature = self.temperatures[task_type]
            else:
                temperature = self.default_temperature

        if max_tokens is None:
            max_tokens = self.default_max_tokens

        if "gpt-5" in self.model.lower():
            temperature = 1

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            if "gpt-5" in self.model.lower() or "o1" in self.model.lower():
                token_param = {"max_completion_tokens": max_tokens}
            else:
                token_param = {"max_tokens": max_tokens}

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                **token_param,
                stream=True,
                **kwargs,
            )

            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            print(f"[LLMClient] Streaming call failed: {e}")
            raise

    def test_connection(self) -> bool:
        """Return whether the configured API can complete a small request."""
        try:
            response = self.chat("hello", max_tokens=10)
            return bool(response)
        except Exception as e:
            print(f"[LLMClient] Connection test failed: {e}")
            return False


if __name__ == "__main__":
    client = LLMClient()

    print("=" * 60)
    print("Testing LLM client")
    print("=" * 60)
    print(f"Base URL: {client.base_url}")
    print(f"Model: {client.model}")
    print(f"Default Temperature: {client.default_temperature}")
    print(f"Default Max Tokens: {client.default_max_tokens}")
    print(f"Task Temperatures: {client.temperatures}")
    print("=" * 60)

    print("\nTesting chat...")
    try:
        response = client.chat("Introduce DuckDB in one sentence.")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Test failed: {e}")
