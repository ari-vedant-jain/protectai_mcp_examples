from abc import ABC, abstractmethod
from typing import Any


class BaseInstrumentor(ABC):
    """Base class for all instrumentors."""
    _layer: Any

    def __init__(self, layer: Any):
        """Initialize the instrumentor.

        Args:
            layer (Any): The Layer SDK instance.
        """
        self._layer = layer

    @abstractmethod
    def instrument(self):
        """Instrument the code."""
        pass

    @abstractmethod
    def supports(self) -> bool:
        """Check if the instrumentor supports the current environment."""
        pass
