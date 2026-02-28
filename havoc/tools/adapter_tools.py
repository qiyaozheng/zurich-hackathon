"""Robot adapter tools — LangChain tool wrappers for the adapter layer."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from adapters.base import RobotAdapter

logger = logging.getLogger(__name__)

_adapter: RobotAdapter | None = None


def set_adapter(adapter: RobotAdapter) -> None:
    global _adapter
    _adapter = adapter


def get_adapter() -> RobotAdapter:
    assert _adapter is not None, "Adapter not initialized"
    return _adapter


@tool
async def adapter_pick() -> str:
    """Command the robot to pick up a part from the inspection zone.

    Returns:
        JSON result of the pick operation.
    """
    import json
    result = await get_adapter().pick()
    return json.dumps(result)


@tool
async def adapter_place(bin_id: str) -> str:
    """Command the robot to place a part into the specified bin.

    Args:
        bin_id: Target bin identifier (e.g., BIN_A, BIN_B, REJECT_BIN).

    Returns:
        JSON result of the place operation.
    """
    import json
    result = await get_adapter().place(bin_id)
    return json.dumps(result)


@tool
async def adapter_move(position: str) -> str:
    """Command the robot to move to a specific position.

    Args:
        position: Target position as coordinate string.

    Returns:
        JSON result of the move operation.
    """
    import json
    result = await get_adapter().move(position)
    return json.dumps(result)


@tool
async def adapter_stop() -> str:
    """Emergency stop the robot immediately.

    Returns:
        JSON result of the stop operation.
    """
    import json
    result = await get_adapter().stop()
    return json.dumps(result)


@tool
async def adapter_preflight() -> str:
    """Run preflight checks on the robot adapter.

    Returns:
        JSON result with check status.
    """
    import json
    result = await get_adapter().preflight()
    return json.dumps(result)
