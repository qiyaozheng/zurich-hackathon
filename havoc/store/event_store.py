from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import aiosqlite

from models import EventType, FactoryEvent, ShiftStats

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    event_id   TEXT PRIMARY KEY,
    timestamp  TEXT NOT NULL,
    event_type TEXT NOT NULL,
    agent      TEXT NOT NULL,
    data       TEXT NOT NULL,
    source_document TEXT,
    source_location TEXT
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_ts   ON events(timestamp);
"""


class EventStore:
    def __init__(self, db_path: str = "events.db"):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.executescript(_CREATE_TABLE + _CREATE_INDEX)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def emit(self, event: FactoryEvent) -> str:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO events (event_id, timestamp, event_type, agent, data, source_document, source_location) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.timestamp.isoformat(),
                event.event_type.value,
                event.agent,
                json.dumps(event.data),
                event.source_document,
                json.dumps(event.source_location),
            ),
        )
        await self._db.commit()
        return event.event_id

    def _row_to_event(self, row: tuple) -> FactoryEvent:
        return FactoryEvent(
            event_id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            event_type=EventType(row[2]),
            agent=row[3],
            data=json.loads(row[4]),
            source_document=row[5] or "",
            source_location=json.loads(row[6]) if row[6] else {},
        )

    async def query(
        self,
        event_type: EventType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[FactoryEvent]:
        assert self._db is not None
        clauses: list[str] = []
        params: list[str] = []
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type.value)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since.isoformat())
        if until:
            clauses.append("timestamp <= ?")
            params.append(until.isoformat())

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(str(limit))

        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()
        return [self._row_to_event(r) for r in rows]

    async def get_by_part(self, part_id: str) -> list[FactoryEvent]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM events WHERE data LIKE ? ORDER BY timestamp",
            (f'%"{part_id}"%',),
        )
        rows = await cursor.fetchall()
        return [self._row_to_event(r) for r in rows]

    async def get_stats(
        self, start: datetime | None = None, end: datetime | None = None
    ) -> ShiftStats:
        events = await self.query(event_type=EventType.INSPECTION, since=start, until=end, limit=10000)
        if not events:
            return ShiftStats()

        total = len(events)
        rejected = 0
        manual = 0
        overrides = 0
        confidence_sum = 0.0

        for ev in events:
            d = ev.data
            action = d.get("action", "")
            if action == "REJECT":
                rejected += 1
            elif action == "MANUAL_REVIEW":
                manual += 1
            confidence_sum += d.get("confidence", 0.0)

        override_events = await self.query(event_type=EventType.OPERATOR_OVERRIDE, since=start, until=end, limit=10000)
        overrides = len(override_events)

        passed = total - rejected
        return ShiftStats(
            total_inspected=total,
            passed=passed,
            rejected=rejected,
            manual_reviews=manual,
            operator_overrides=overrides,
            pass_rate=round(passed / total, 4) if total else 0.0,
            avg_confidence=round(confidence_sum / total, 4) if total else 0.0,
            start_time=start,
            end_time=end,
        )

    async def get_recent(self, limit: int = 20) -> list[FactoryEvent]:
        return await self.query(limit=limit)
