from antcrew_engine.models.base import BaseLLM, Message
from antcrew_engine.models.cache import LLMCache, FileLLMCache
from antcrew_engine.models.anthropic_model import AnthropicModel
from antcrew_engine.models.fallback import FallbackLLM
from antcrew_engine.models.ollama_model import OllamaModel
from antcrew_engine.models.groq_model import GroqModel
from antcrew_engine.models.gemini_model import GeminiModel
from antcrew_engine.models.simulated import SimulatedLLM

# OpenAIModel is imported lazily (requires optional 'openai' package)
def __getattr__(name: str):
    if name == "OpenAIModel":
        from antcrew_engine.models.openai_model import OpenAIModel
        return OpenAIModel
    raise AttributeError(f"module 'antcrew_engine.models' has no attribute {name!r}")

__all__ = [
    "BaseLLM", "Message",
    "LLMCache",
    "FileLLMCache",
    "AnthropicModel",
    "FallbackLLM",
    "OllamaModel",
    "GroqModel",
    "GeminiModel",
    "SimulatedLLM",
    "OpenAIModel",  # lazy — requires pip install openai
]
