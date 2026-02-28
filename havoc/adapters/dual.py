from __future__ import annotations

import asyncio
import logging

from adapters.base import RobotAdapter
from adapters.dobot_cr import DobotCRAdapter
from adapters.simulator import SimulatorAdapter

logger = logging.getLogger(__name__)


class DualAdapter(RobotAdapter):
    """Drives a real Dobot CR AND the HMI simulator in parallel.

    If the Dobot is unavailable, gracefully falls back to simulator-only.
    """

    def __init__(self, dobot: DobotCRAdapter, simulator: SimulatorAdapter):
        self._dobot = dobot
        self._simulator = simulator
        self._dobot_live = True

    async def _dobot_call(self, method: str, *args, **kwargs):
        if not self._dobot_live:
            return {"status": "SKIPPED", "adapter": "dobot_cr"}
        try:
            return await getattr(self._dobot, method)(*args, **kwargs)
        except Exception as e:
            logger.warning("Dobot call %s failed: %s — falling back to simulator", method, e)
            self._dobot_live = False
            return {"status": "ERROR", "adapter": "dobot_cr", "error": str(e)}

    async def pick(self) -> dict:
        dobot_res, sim_res = await asyncio.gather(
            self._dobot_call("pick"),
            self._simulator.pick(),
        )
        return {**sim_res, "dobot": dobot_res}

    async def place(self, bin_id: str) -> dict:
        dobot_res, sim_res = await asyncio.gather(
            self._dobot_call("place", bin_id),
            self._simulator.place(bin_id),
        )
        return {**sim_res, "dobot": dobot_res}

    async def move(self, position: str) -> dict:
        dobot_res, sim_res = await asyncio.gather(
            self._dobot_call("move", position),
            self._simulator.move(position),
        )
        return {**sim_res, "dobot": dobot_res}

    async def stop(self) -> dict:
        dobot_res, sim_res = await asyncio.gather(
            self._dobot_call("stop"),
            self._simulator.stop(),
        )
        return {**sim_res, "dobot": dobot_res}

    async def heartbeat(self) -> dict:
        dobot_res = await self._dobot_call("heartbeat")
        return {
            "status": "OK",
            "adapter": "dual",
            "dobot_live": self._dobot_live,
            "dobot": dobot_res,
        }

    async def preflight(self) -> dict:
        sim_res = await self._simulator.preflight()
        dobot_res = await self._dobot_call("preflight")
        return {
            "status": "OK",
            "adapter": "dual",
            "dobot_live": self._dobot_live,
            "simulator": sim_res,
            "dobot": dobot_res,
        }


def create_adapter(
    dobot_host: str,
    dobot_port: int,
    simulator: SimulatorAdapter,
    speed_pct: int = 30,
) -> RobotAdapter:
    """Try to connect to Dobot CR; fall back to simulator-only."""
    try:
        dobot = DobotCRAdapter(host=dobot_host, port=dobot_port, speed_pct=speed_pct)
        logger.info("DualAdapter created — Dobot CR at %s:%d + Simulator", dobot_host, dobot_port)
        return DualAdapter(dobot=dobot, simulator=simulator)
    except Exception as e:
        logger.warning("Dobot CR not reachable (%s) — using Simulator only", e)
        return simulator
