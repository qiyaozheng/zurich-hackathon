from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from models import ExecutablePolicy, PolicyStatus

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS policies (
    policy_id  TEXT PRIMARY KEY,
    version    INTEGER NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data       TEXT NOT NULL
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_policies_status ON policies(status);
"""


class PolicyStore:
    def __init__(self, db_path: str = "events.db"):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._active: ExecutablePolicy | None = None

    @property
    def active_policy(self) -> ExecutablePolicy | None:
        return self._active

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(_CREATE_TABLE + _CREATE_INDEX)
        await self._db.commit()
        approved = await self.get_by_status(PolicyStatus.APPROVED)
        if approved:
            self._active = approved[-1]

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def store(self, policy: ExecutablePolicy) -> str:
        assert self._db is not None
        await self._db.execute(
            "INSERT OR REPLACE INTO policies (policy_id, version, status, created_at, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                policy.policy_id,
                policy.version,
                policy.status.value,
                policy.created_at.isoformat(),
                policy.model_dump_json(),
            ),
        )
        await self._db.commit()
        return policy.policy_id

    async def get(self, policy_id: str) -> ExecutablePolicy | None:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT data FROM policies WHERE policy_id = ?", (policy_id,)
        )
        row = await cursor.fetchone()
        if row:
            return ExecutablePolicy.model_validate_json(row[0])
        return None

    async def get_by_status(self, status: PolicyStatus) -> list[ExecutablePolicy]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT data FROM policies WHERE status = ? ORDER BY created_at", (status.value,)
        )
        rows = await cursor.fetchall()
        return [ExecutablePolicy.model_validate_json(r[0]) for r in rows]

    async def approve(self, policy_id: str) -> ExecutablePolicy | None:
        policy = await self.get(policy_id)
        if not policy:
            return None
        policy.status = PolicyStatus.APPROVED
        await self.store(policy)
        self._active = policy
        return policy

    async def reject(self, policy_id: str) -> ExecutablePolicy | None:
        policy = await self.get(policy_id)
        if not policy:
            return None
        policy.status = PolicyStatus.REJECTED
        await self.store(policy)
        return policy

    async def suspend(self, policy_id: str) -> ExecutablePolicy | None:
        policy = await self.get(policy_id)
        if not policy:
            return None
        policy.status = PolicyStatus.SUSPENDED
        await self.store(policy)
        if self._active and self._active.policy_id == policy_id:
            self._active = None
        return policy

    async def list_all(self) -> list[ExecutablePolicy]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT data FROM policies ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [ExecutablePolicy.model_validate_json(r[0]) for r in rows]
