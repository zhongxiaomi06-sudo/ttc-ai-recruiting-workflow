"""Base executor interface for skill search."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..models import Candidate, SearchIntent


class BaseExecutor(ABC):
    """A channel/executor that can search candidates given a structured intent."""

    name: str = "base"

    @abstractmethod
    async def search(self, intent: SearchIntent, limit: int = 10) -> List[Candidate]:
        """Return candidates matching the intent."""
        ...

    async def health(self) -> dict:
        """Optional health check metadata."""
        return {"ok": True, "source": self.name}
