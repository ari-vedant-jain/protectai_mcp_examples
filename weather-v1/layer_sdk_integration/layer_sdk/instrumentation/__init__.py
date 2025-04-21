"""Instrumentation module for the SDK."""
from typing import Dict, Callable

from ._base import BaseInstrumentor
from ._openai import OpenAIInstrumentation
from ._anthropic import AnthropicInstrumentation  

instrumentor_instances: Dict[str, Callable] = {
    "openai": OpenAIInstrumentation,
    "anthropic": AnthropicInstrumentation, 
}

__all__ = ["BaseInstrumentor", "instrumentor_instances", "OpenAIInstrumentation", "AnthropicInstrumentation"]
