"""
LLM Provider — supports all four providers:
  gemini    → Google Gemini (gemini-2.0-flash, free tier)
  openai    → OpenAI GPT-4o
  azure     → Azure OpenAI Service (your own deployment)
  anthropic → Anthropic Claude

Switch provider by changing LLM_PROVIDER in backend/.env.
No code changes required.
"""
import asyncio
import logging
import re
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMMessage:
    def __init__(self, role: str, content: str):
        self.role    = role       # "user" | "assistant" | "system"
        self.content = content


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[LLMMessage],
                   system: Optional[str] = None) -> str: ...

    @abstractmethod
    async def stream_chat(self, messages: List[LLMMessage],
                          system: Optional[str] = None
                         ) -> AsyncGenerator[str, None]: ...

    def provider_name(self) -> str:
        return self.__class__.__name__


# ── 1. Google Gemini ──────────────────────────────────────────────────────────

class GeminiProvider(LLMProvider):
    """
    Free tier available at https://aistudio.google.com
    Model: gemini-2.0-flash (fast, capable, free quota)
    """

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._genai     = genai
        self.model_name = settings.GEMINI_MODEL
        logger.info(f"✅ Gemini ready — model: {self.model_name}")

    def _make_prompt(self, messages: List[LLMMessage],
                     system: Optional[str]) -> str:
        """Build a single combined prompt string for Gemini."""
        parts = []
        if system:
            parts.append(f"[SYSTEM INSTRUCTIONS]\n{system}")
        for m in messages:
            label = "Assistant" if m.role == "assistant" else "User"
            parts.append(f"[{label}]\n{m.content}")
        parts.append("[Assistant]")
        return "\n\n".join(parts)

    def _get_model(self):
        return self._genai.GenerativeModel(
            self.model_name,
            generation_config=self._genai.GenerationConfig(
                max_output_tokens=4096,
                temperature=0.7,
            ),
        )

    async def chat(self, messages: List[LLMMessage],
                   system: Optional[str] = None) -> str:
        prompt = self._make_prompt(messages, system)
        model  = self._get_model()

        def _call():
            return model.generate_content(prompt).text

        return await asyncio.to_thread(_call)

    async def stream_chat(self, messages: List[LLMMessage],
                          system: Optional[str] = None) -> AsyncGenerator[str, None]:
        prompt = self._make_prompt(messages, system)
        model  = self._get_model()

        def _stream():
            return model.generate_content(prompt, stream=True)

        stream = await asyncio.to_thread(_stream)
        for chunk in stream:
            try:
                if chunk.text:
                    yield chunk.text
            except Exception:
                pass


# ── 2. OpenAI ─────────────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    """
    Standard OpenAI API (GPT-4o, GPT-4, GPT-3.5-turbo etc.)
    Get key at: https://platform.openai.com/api-keys
    """

    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model  = settings.OPENAI_MODEL
        logger.info(f"✅ OpenAI ready — model: {self.model}")

    def _build_messages(self, messages: List[LLMMessage],
                        system: Optional[str]) -> List[Dict]:
        out = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            out.append({"role": m.role, "content": m.content})
        return out

    async def chat(self, messages: List[LLMMessage],
                   system: Optional[str] = None) -> str:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(messages, system),
            max_tokens=4096,
        )
        return resp.choices[0].message.content

    async def stream_chat(self, messages: List[LLMMessage],
                          system: Optional[str] = None) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(messages, system),
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── 3. Azure OpenAI ───────────────────────────────────────────────────────────

class AzureOpenAIProvider(LLMProvider):
    """
    Azure OpenAI Service — your own GPT deployment in Azure.

    Required env vars:
      AZURE_OPENAI_API_KEY      = your Azure OpenAI key
      AZURE_OPENAI_ENDPOINT     = https://<your-resource>.openai.azure.com/
      AZURE_OPENAI_DEPLOYMENT   = your deployment name (e.g. gpt-4o)
      AZURE_OPENAI_API_VERSION  = 2024-02-01 (or latest)

    Setup: https://portal.azure.com → Azure OpenAI → Keys and Endpoint
    """

    def __init__(self):
        from openai import AsyncAzureOpenAI
        self.client = AsyncAzureOpenAI(
            api_key        = settings.AZURE_OPENAI_API_KEY,
            azure_endpoint = settings.AZURE_OPENAI_ENDPOINT,
            api_version    = settings.AZURE_OPENAI_API_VERSION,
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        logger.info(
            f"✅ Azure OpenAI ready — "
            f"endpoint: {settings.AZURE_OPENAI_ENDPOINT} | "
            f"deployment: {self.deployment}"
        )

    def _build_messages(self, messages: List[LLMMessage],
                        system: Optional[str]) -> List[Dict]:
        out = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            out.append({"role": m.role, "content": m.content})
        return out

    async def chat(self, messages: List[LLMMessage],
                   system: Optional[str] = None) -> str:
        resp = await self.client.chat.completions.create(
            model    = self.deployment,   # Azure uses deployment name as model
            messages = self._build_messages(messages, system),
            max_tokens = 4096,
        )
        return resp.choices[0].message.content

    async def stream_chat(self, messages: List[LLMMessage],
                          system: Optional[str] = None) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model    = self.deployment,
            messages = self._build_messages(messages, system),
            max_tokens = 4096,
            stream   = True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── 4. Anthropic Claude ───────────────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude (claude-sonnet-4, claude-opus-4 etc.)
    Get key at: https://console.anthropic.com
    """

    def __init__(self):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model  = settings.ANTHROPIC_MODEL
        logger.info(f"✅ Anthropic ready — model: {self.model}")

    def _build_messages(self, messages: List[LLMMessage]) -> List[Dict]:
        return [
            {"role": "assistant" if m.role == "assistant" else "user",
             "content": m.content}
            for m in messages
        ]

    async def chat(self, messages: List[LLMMessage],
                   system: Optional[str] = None) -> str:
        kw: Dict = {
            "model":     self.model,
            "max_tokens": 4096,
            "messages":  self._build_messages(messages),
        }
        if system:
            kw["system"] = system
        resp = await self.client.messages.create(**kw)
        return resp.content[0].text

    async def stream_chat(self, messages: List[LLMMessage],
                          system: Optional[str] = None) -> AsyncGenerator[str, None]:
        kw: Dict = {
            "model":     self.model,
            "max_tokens": 4096,
            "messages":  self._build_messages(messages),
        }
        if system:
            kw["system"] = system
        async with self.client.messages.stream(**kw) as stream:
            async for text in stream.text_stream:
                yield text


# ── Mock (no key configured) ──────────────────────────────────────────────────

class MockProvider(LLMProvider):
    async def chat(self, messages: List[LLMMessage],
                   system: Optional[str] = None) -> str:
        return (
            "**Demo mode** — no LLM API key is configured.\n\n"
            "Edit `backend\\.env` and set one of:\n\n"
            "| Provider | Env var | Where to get key |\n"
            "|----------|---------|------------------|\n"
            "| Google Gemini (free) | `GEMINI_API_KEY` | https://aistudio.google.com |\n"
            "| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com |\n"
            "| Azure OpenAI | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | Azure Portal |\n"
            "| Anthropic | `ANTHROPIC_API_KEY` | https://console.anthropic.com |\n\n"
            "Also set `LLM_PROVIDER=gemini` (or openai / azure / anthropic)."
        )

    async def stream_chat(self, messages: List[LLMMessage],
                          system: Optional[str] = None) -> AsyncGenerator[str, None]:
        for word in (await self.chat(messages, system)).split(" "):
            yield word + " "
            await asyncio.sleep(0.015)


# ── Factory ───────────────────────────────────────────────────────────────────

def get_llm_provider(provider: Optional[str] = None) -> LLMProvider:
    """
    Return the correct LLM provider based on LLM_PROVIDER setting.
    Falls back to MockProvider if the required API key is not set.
    """
    name = (provider or settings.LLM_PROVIDER or "gemini").lower().strip()
    logger.info(f"LLM provider requested: '{name}'")

    try:
        # ── Gemini ────────────────────────────────────────────────────────
        if name == "gemini":
            if not settings.GEMINI_API_KEY:
                logger.warning(
                    "GEMINI_API_KEY not set in backend/.env\n"
                    "  Get a free key at: https://aistudio.google.com\n"
                    "  Then add to backend/.env:\n"
                    "    LLM_PROVIDER=gemini\n"
                    "    GEMINI_API_KEY=AIzaSy..."
                )
                return MockProvider()
            return GeminiProvider()

        # ── OpenAI ────────────────────────────────────────────────────────
        elif name == "openai":
            if not settings.OPENAI_API_KEY:
                logger.warning(
                    "OPENAI_API_KEY not set in backend/.env\n"
                    "  Get key at: https://platform.openai.com/api-keys\n"
                    "  Then add to backend/.env:\n"
                    "    LLM_PROVIDER=openai\n"
                    "    OPENAI_API_KEY=sk-..."
                )
                return MockProvider()
            return OpenAIProvider()

        # ── Azure OpenAI ──────────────────────────────────────────────────
        elif name in ("azure", "azure_openai", "azureopenai"):
            missing = []
            if not settings.AZURE_OPENAI_API_KEY:
                missing.append("AZURE_OPENAI_API_KEY")
            if not settings.AZURE_OPENAI_ENDPOINT:
                missing.append("AZURE_OPENAI_ENDPOINT")
            if missing:
                logger.warning(
                    f"Azure OpenAI: missing {missing} in backend/.env\n"
                    "  Get from: Azure Portal → Azure OpenAI → Keys and Endpoint\n"
                    "  Then add to backend/.env:\n"
                    "    LLM_PROVIDER=azure\n"
                    "    AZURE_OPENAI_API_KEY=your-key\n"
                    "    AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/\n"
                    "    AZURE_OPENAI_DEPLOYMENT=gpt-4o"
                )
                return MockProvider()
            return AzureOpenAIProvider()

        # ── Anthropic ─────────────────────────────────────────────────────
        elif name == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                logger.warning(
                    "ANTHROPIC_API_KEY not set in backend/.env\n"
                    "  Get key at: https://console.anthropic.com\n"
                    "  Then add to backend/.env:\n"
                    "    LLM_PROVIDER=anthropic\n"
                    "    ANTHROPIC_API_KEY=sk-ant-..."
                )
                return MockProvider()
            return AnthropicProvider()

        # ── Unknown ───────────────────────────────────────────────────────
        else:
            logger.warning(
                f"Unknown LLM_PROVIDER='{name}'\n"
                f"  Valid values: gemini | openai | azure | anthropic"
            )
            return MockProvider()

    except Exception as e:
        logger.error(f"LLM provider '{name}' failed to initialise: {e}")
        return MockProvider()
