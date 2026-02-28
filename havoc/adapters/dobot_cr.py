from __future__ import annotations

import asyncio
import json
import logging
import socket

from adapters.base import RobotAdapter

logger = logging.getLogger(__name__)

# Default bin positions (x, y, z, rx, ry, rz) — calibrate on site
DEFAULT_BIN_POSITIONS: dict[str, str] = {
    "BIN_A": "200,0,50,0,0,0",
    "BIN_B": "200,100,50,0,0,0",
    "BIN_C": "200,-100,50,0,0,0",
    "REJECT_BIN": "0,200,50,0,0,0",
    "REVIEW_BIN": "0,-200,50,0,0,0",
}

PICK_POSITION = "250,0,0,0,0,0"
SAFE_HEIGHT_Z = 100


class DobotCRAdapter(RobotAdapter):
    """Controls a Dobot CR-series cobot via TCP/IP dashboard protocol (port 29999)."""

    def __init__(
        self,
        host: str = "192.168.1.6",
        port: int = 29999,
        bin_positions: dict[str, str] | None = None,
        speed_pct: int = 30,
    ):
        self._host = host
        self._port = port
        self._bin_positions = bin_positions or DEFAULT_BIN_POSITIONS
        self._speed_pct = speed_pct
        self._sock: socket.socket | None = None

    async def _connect(self) -> None:
        loop = asyncio.get_event_loop()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(5.0)
        await loop.run_in_executor(None, self._sock.connect, (self._host, self._port))
        logger.info("Dobot CR connected at %s:%d", self._host, self._port)

    def _send_raw(self, cmd: str) -> str:
        assert self._sock is not None
        self._sock.sendall(f"{cmd}\n".encode("ascii"))
        return self._sock.recv(2048).decode("ascii").strip()

    async def _send(self, cmd: str) -> str:
        if self._sock is None:
            await self._connect()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._send_raw, cmd)
        logger.info("DOBOT ← %s → %s", cmd, result)
        return result

    async def pick(self) -> dict:
        await self._send(f"MovL({PICK_POSITION})")
        await self._send("DO(1,ON)")
        return {"status": "OK", "adapter": "dobot_cr", "action": "pick"}

    async def place(self, bin_id: str) -> dict:
        pos = self._bin_positions.get(bin_id, self._bin_positions.get("REVIEW_BIN", PICK_POSITION))
        await self._send(f"MovL({pos})")
        await self._send("DO(1,OFF)")
        return {"status": "OK", "adapter": "dobot_cr", "bin": bin_id}

    async def move(self, position: str) -> dict:
        await self._send(f"MovL({position})")
        return {"status": "OK", "adapter": "dobot_cr"}

    async def stop(self) -> dict:
        await self._send("EmergencyStop()")
        return {"status": "STOPPED", "adapter": "dobot_cr"}

    async def heartbeat(self) -> dict:
        try:
            resp = await self._send("RobotMode()")
            return {"status": "OK", "adapter": "dobot_cr", "mode": resp}
        except Exception as e:
            return {"status": "ERROR", "adapter": "dobot_cr", "error": str(e)}

    async def preflight(self) -> dict:
        checks: list[str] = []
        try:
            await self._send("EnableRobot()")
            checks.append("robot_enabled")
            await self._send(f"SpeedFactor({self._speed_pct})")
            checks.append(f"speed_set_{self._speed_pct}pct")
            return {"status": "OK", "adapter": "dobot_cr", "checks": checks}
        except Exception as e:
            return {"status": "ERROR", "adapter": "dobot_cr", "error": str(e), "checks": checks}

    async def disconnect(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None
