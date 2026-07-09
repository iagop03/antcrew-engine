"""antcrew_engine.config — minimal config helpers for the standalone engine.

Only contains ``build_llm()``.  Use ``antcrew.config`` for the full loader
(team context, channels, LangGraph runners) when working with Layer 1.
"""
from __future__ import annotations

from antcrew_engine.models.base import BaseLLM


def build_llm(model_str: str, *, prompt_caching: bool = False) -> BaseLLM:
    """Parse a model string and return a configured LLM instance.

    Supported forms::

        "claude"                  # default Anthropic (claude-sonnet-4-6)
        "claude-haiku-4-5-20251001"
        "gpt-4o"                  # OpenAI (requires openai extra)
        "openai:gpt-4o-mini"
        "ollama:llama3"
        "groq:llama3-70b-8192"
        "azure:my-deployment"
        "gemini"                  # GeminiModel default
        "simulated"               # deterministic stub for tests
    """
    s = model_str.strip().lower()

    if s == "simulated":
        from antcrew_engine.models.simulated import SimulatedLLM
        return SimulatedLLM()

    if s.startswith("ollama:"):
        from antcrew_engine.models.ollama_model import OllamaModel
        return OllamaModel(s.split(":", 1)[1])

    if s.startswith("groq:"):
        from antcrew_engine.models.groq_model import GroqModel
        return GroqModel(s.split(":", 1)[1])

    if s.startswith("azure:"):
        from antcrew_engine.models.azure_openai_model import AzureOpenAIModel
        return AzureOpenAIModel(deployment=s.split(":", 1)[1])

    if s.startswith("openai:"):
        from antcrew_engine.models.openai_model import OpenAIModel
        return OpenAIModel(s.split(":", 1)[1])

    if s.startswith("gpt") or s.startswith("o1") or s.startswith("o3"):
        from antcrew_engine.models.openai_model import OpenAIModel
        return OpenAIModel(s)

    if s.startswith("gemini"):
        from antcrew_engine.models.gemini_model import GeminiModel
        return GeminiModel(s)

    if s == "gemini":
        from antcrew_engine.models.gemini_model import GeminiModel
        return GeminiModel()

    # Default: Anthropic / Claude (model strings starting with "claude" or the bare "anthropic")
    if not (s.startswith("claude") or s == "anthropic"):
        raise ValueError(
            f"Unknown model: {model_str!r}. "
            "Supported prefixes: claude, gpt, o1, o3, openai:, ollama:, groq:, azure:, gemini, simulated."
        )
    from antcrew_engine.models.anthropic_model import AnthropicModel
    model_id = None if s in ("claude", "anthropic") else s
    return AnthropicModel(
        **({"model": model_id} if model_id else {}),
        prompt_caching=prompt_caching,
    )
