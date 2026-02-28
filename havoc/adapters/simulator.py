from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

from adapters.base import RobotAdapter
from models import FactoryFloorEvent

logger = logging.getLogger(__name__)

BroadcastFn = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class SimulatorAdapter(RobotAdapter):
    """Sends animation commands to the HMI via a broadcast callback."""

    def __init__(self, broadcast: BroadcastFn | None = None):
        self._broadcast = broadcast

    def set_broadcast(self, broadcast: BroadcastFn) -> None:
        self._broadcast = broadcast

    async def _send(self, event: FactoryFloorEvent) -> dict:
        payload = event.model_dump()
        if self._broadcast:
            await self._broadcast(payload)
        logger.info("SIM → %s", payload)
        return {"status": event.status, "adapter": "simulator"}

    async def pick(self) -> dict:
        return await self._send(FactoryFloorEvent(animation="PICK"))

    async def place(self, bin_id: str) -> dict:
        result = await self._send(
            FactoryFloorEvent(animation="PLACE", target=bin_id)
        )
        result["bin"] = bin_id
        return result

    async def move(self, position: str) -> dict:
        return await self._send(
            FactoryFloorEvent(animation="MOVE", target=position)
        )

    async def stop(self) -> dict:
        return await self._send(FactoryFloorEvent(animation="STOP"))

    async def heartbeat(self) -> dict:
        return {"status": "OK", "adapter": "simulator"}

    async def preflight(self) -> dict:
        return {"status": "OK", "adapter": "simulator", "checks": ["broadcast_ready"]}
