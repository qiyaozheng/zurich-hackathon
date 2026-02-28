"""Robot Function Registry — thin wrapper for Gemini Robotics-ER function calls.

This module dispatches function calls from the orchestrator to the actual robot API.
The placeholder implementations use the SimulatorAdapter as fallback.

YOUR COLLEAGUE: Replace robot_move_to() and robot_grip() with real Dobot CR S0 100 code.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Will be set by main.py during startup
_adapter = None
_broadcast_fn = None


def set_robot_backend(adapter, broadcast_fn=None):
    """Called during app startup to inject the robot adapter."""
    global _adapter, _broadcast_fn
    _adapter = adapter
    _broadcast_fn = broadcast_fn


# ---------------------------------------------------------------------------
# Robot API — Replace these with real Dobot CR S0 100 implementations
# ---------------------------------------------------------------------------

async def robot_move_to(x: float, y: float, z: float) -> dict[str, Any]:
    """Move the robot end-effector to a 3D position (mm).

    TODO (Kollege): Replace with real Dobot CR TCP/IP command.
    Current implementation uses the simulator adapter.
    """
    logger.info("ROBOT move_to(%.1f, %.1f, %.1f)", x, y, z)

    if _adapter:
        try:
            await _adapter.move(x, y, z)
            return {"success": True, "position": [x, y, z]}
        except Exception as e:
            logger.error("Robot move failed: %s", e)
            return {"success": False, "error": str(e), "position": [x, y, z]}

    return {"success": True, "position": [x, y, z], "simulated": True}


async def robot_grip(action: str) -> dict[str, Any]:
    """Open or close the gripper.

    TODO (Kollege): Replace with real Dobot CR gripper command.
    Current implementation uses the simulator adapter.
    """
    logger.info("ROBOT grip(%s)", action)

    if _adapter:
        try:
            if action == "close":
                await _adapter.pick()
            else:
                await _adapter.place("CURRENT")
            return {"success": True, "state": action}
        except Exception as e:
            logger.error("Robot grip failed: %s", e)
            return {"success": False, "error": str(e), "state": action}

    return {"success": True, "state": action, "simulated": True}


# ---------------------------------------------------------------------------
# Function Call Dispatcher
# ---------------------------------------------------------------------------

FUNCTION_REGISTRY: dict[str, Any] = {
    "move_to": lambda args: robot_move_to(args["x"], args["y"], args["z"]),
    "grip": lambda args: robot_grip(args["action"]),
}


async def execute_robot_function(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a function call from Gemini to the appropriate handler."""
    handler = FUNCTION_REGISTRY.get(name)
    if not handler:
        logger.warning("Unknown robot function: %s", name)
        return {"error": f"Unknown function: {name}"}

    try:
        result = await handler(args)
        logger.info("Function %s result: %s", name, result)
        return result
    except Exception as e:
        logger.error("Function %s failed: %s", name, e)
        return {"error": str(e), "function": name}
