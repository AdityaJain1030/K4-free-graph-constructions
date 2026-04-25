"""
Anthropic (Claude) API interface for LLMs.

Implements LLMInterface using the official `anthropic` Python SDK. Accepts the
same LLMModelConfig used for OpenAI so it is a drop-in alternative — the
ensemble auto-selects this class when a model name starts with "claude-".

Env vars: ANTHROPIC_API_KEY (or set api_key in config via ${ANTHROPIC_API_KEY}).
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from openevolve.llm.base import LLMInterface

logger = logging.getLogger(__name__)


class AnthropicLLM(LLMInterface):
    """LLM interface using Anthropic's Messages API."""

    def __init__(self, model_cfg: Optional[dict] = None):
        try:
            import anthropic  # lazy import so non-Anthropic users don't need the dep
        except ImportError as e:
            raise ImportError(
                "The `anthropic` package is required to use Claude models. "
                "Install with `pip install anthropic`."
            ) from e

        self.model = model_cfg.name
        self.system_message = model_cfg.system_message
        self.temperature = model_cfg.temperature
        self.top_p = model_cfg.top_p
        self.max_tokens = model_cfg.max_tokens or 4096
        self.timeout = model_cfg.timeout
        self.retries = model_cfg.retries if model_cfg.retries is not None else 0
        self.retry_delay = model_cfg.retry_delay or 1
        self.random_seed = getattr(model_cfg, "random_seed", None)  # unused by Anthropic API

        # Prefer ANTHROPIC_API_KEY env var — LLMConfig's shared api_key is usually the OpenAI key.
        api_key = os.environ.get("ANTHROPIC_API_KEY") or model_cfg.api_key
        if not api_key:
            raise ValueError(
                "No Anthropic API key provided. Set ANTHROPIC_API_KEY or llm.api_key."
            )

        # Ignore api_base if it was inherited from the OpenAI default shared config.
        api_base = model_cfg.api_base
        if api_base and "openai.com" in api_base:
            api_base = None

        kwargs: Dict[str, Any] = {"api_key": api_key, "max_retries": self.retries}
        if api_base:
            kwargs["base_url"] = api_base
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout

        self.client = anthropic.Anthropic(**kwargs)

        if not hasattr(logger, "_initialized_models"):
            logger._initialized_models = set()
        if self.model not in logger._initialized_models:
            logger.info(f"Initialized Anthropic LLM with model: {self.model}")
            logger._initialized_models.add(self.model)

    async def generate(self, prompt: str, **kwargs) -> str:
        return await self.generate_with_context(
            system_message=self.system_message,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )

    async def generate_with_context(
        self, system_message: str, messages: List[Dict[str, str]], **kwargs
    ) -> str:
        # Anthropic expects system as a top-level param, not a message role.
        # Also requires strict alternation of user/assistant roles.
        anthropic_messages: List[Dict[str, str]] = []
        for m in messages:
            role = m.get("role", "user")
            if role == "system":
                # Fold any stray system-role messages into the system string
                system_message = (system_message or "") + "\n\n" + m.get("content", "")
                continue
            anthropic_messages.append({"role": role, "content": m.get("content", "")})

        params: Dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        if system_message:
            params["system"] = system_message
        temperature = kwargs.get("temperature", self.temperature)
        if temperature is not None:
            params["temperature"] = temperature
        top_p = kwargs.get("top_p", self.top_p)
        if top_p is not None:
            params["top_p"] = top_p

        retries = kwargs.get("retries", self.retries)
        retry_delay = kwargs.get("retry_delay", self.retry_delay)
        timeout = kwargs.get("timeout", self.timeout)

        for attempt in range(retries + 1):
            try:
                return await asyncio.wait_for(self._call_api(params), timeout=timeout)
            except asyncio.TimeoutError:
                if attempt < retries:
                    logger.warning(
                        f"Anthropic timeout on attempt {attempt + 1}/{retries + 1}. Retrying..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"All {retries + 1} Anthropic attempts timed out")
                    raise
            except Exception as e:
                if attempt < retries:
                    logger.warning(
                        f"Anthropic error on attempt {attempt + 1}/{retries + 1}: {e}. Retrying..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"All {retries + 1} Anthropic attempts failed: {e}")
                    raise

    async def _call_api(self, params: Dict[str, Any]) -> str:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: self.client.messages.create(**params)
        )
        # Concatenate all text blocks in the response
        parts = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts)
