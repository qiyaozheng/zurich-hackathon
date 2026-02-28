from __future__ import annotations

from abc import ABC, abstractmethod


class RobotAdapter(ABC):
    """Abstract base for all robot adapters (simulator, Dobot CR, etc.)."""

    @abstractmethod
    async def pick(self) -> dict:
        ...

    @abstractmethod
    async def place(self, bin_id: str) -> dict:
        ...

    @abstractmethod
    async def move(self, position: str) -> dict:
        ...

    @abstractmethod
    async def stop(self) -> dict:
        ...

    @abstractmethod
    async def heartbeat(self) -> dict:
        ...

    @abstractmethod
    async def preflight(self) -> dict:
        ...
