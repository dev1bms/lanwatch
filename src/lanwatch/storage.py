from __future__ import annotations

import sqlite3
import threading
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import Device, DeviceEdit, DeviceType, EventKind, EventView, Observation, PresenceMark, ScanRecord
from .reconcile import Reconciliation, reconcile

_SCHEMA_V1 = """
CREATE TABLE devices (
    mac          TEXT PRIMARY KEY,
    ip           TEXT NOT NULL,
    hostname     TEXT,
    vendor       TEXT,
    alias        TEXT,
    dev_type     TEXT NOT NULL DEFAULT 'unknown',
    type_locked  INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    known        INTEGER NOT NULL DEFAULT 0,
    random_mac   INTEGER NOT NULL DEFAULT 0,
    is_self      INTEGER NOT NULL DEFAULT 0,
    is_gateway   INTEGER NOT NULL DEFAULT 0,
    online       INTEGER NOT NULL DEFAULT 0,
    rtt_ms       REAL,
    first_seen   REAL NOT NULL,
    last_seen    REAL NOT NULL
);
CREATE TABLE scans (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    started  REAL NOT NULL,
    duration REAL NOT NULL,
    found    INTEGER NOT NULL,
    method   TEXT NOT NULL,
    error    TEXT
);
CREATE INDEX idx_scans_started ON scans (started);
CREATE TABLE sightings (
    mac TEXT NOT NULL,
    ts  REAL NOT NULL
);
CREATE INDEX idx_sightings_ts ON sightings (ts);
CREATE INDEX idx_sightings_mac ON sightings (mac);
CREATE TABLE events (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     REAL NOT NULL,
    mac    TEXT NOT NULL,
    kind   TEXT NOT NULL,
    ip     TEXT,
    detail TEXT
);
CREATE INDEX idx_events_ts ON events (ts);
"""

MIGRATIONS: tuple[str, ...] = (_SCHEMA_V1,)
EVENT_RETENTION_DAYS = 30
DAY = 86400.0


def _to_device(row: sqlite3.Row) -> Device:
    return Device(
        mac=row["mac"],
        ip=row["ip"],
        hostname=row["hostname"],
        vendor=row["vendor"],
        alias=row["alias"],
        dev_type=DeviceType(row["dev_type"]),
        type_locked=bool(row["type_locked"]),
        notes=row["notes"],
        known=bool(row["known"]),
        random_mac=bool(row["random_mac"]),
        is_self=bool(row["is_self"]),
        is_gateway=bool(row["is_gateway"]),
        online=bool(row["online"]),
        rtt_ms=row["rtt_ms"],
        first_seen=row["first_seen"],
        last_seen=row["last_seen"],
    )


def _device_params(ob: Observation) -> tuple[Any, ...]:
    return (
        ob.ip,
        ob.hostname,
        ob.vendor,
        ob.dev_type.value,
        int(ob.random_mac),
        int(ob.is_self),
        int(ob.is_gateway),
        ob.rtt_ms,
    )


class Storage:
    def __init__(self, path: Path | str) -> None:
        path = str(path)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=10)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._migrate()

    def _migrate(self) -> None:
        current: int = self._conn.execute("PRAGMA user_version").fetchone()[0]
        for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
            self._conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {version};\nCOMMIT;")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def _fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def save_scan(
        self,
        observations: Sequence[Observation],
        *,
        started: float,
        finished: float,
        method: str,
        offline_after: float,
    ) -> Reconciliation:
        with self._transaction() as conn:
            known = {row["mac"]: _to_device(row) for row in conn.execute("SELECT * FROM devices")}
            result = reconcile(known, observations, now=finished, offline_after=offline_after)
            conn.executemany(
                """INSERT INTO devices (ip, hostname, vendor, dev_type, random_mac, is_self, is_gateway, rtt_ms,
                                        mac, online, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                [(*_device_params(ob), ob.mac, finished, finished) for ob in result.created],
            )
            conn.executemany(
                """UPDATE devices SET ip = ?, hostname = ?, vendor = ?, dev_type = ?, random_mac = ?, is_self = ?,
                                      is_gateway = ?, rtt_ms = ?, online = 1, last_seen = ?
                   WHERE mac = ?""",
                [(*_device_params(ob), finished, ob.mac) for ob in result.refreshed],
            )
            conn.executemany("UPDATE devices SET online = 0 WHERE mac = ?", [(mac,) for mac in result.went_offline])
            conn.executemany("INSERT INTO sightings (mac, ts) VALUES (?, ?)", [(ob.mac, started) for ob in result.seen])
            conn.executemany(
                "INSERT INTO events (ts, mac, kind, ip, detail) VALUES (?, ?, ?, ?, ?)",
                [(e.ts, e.mac, e.kind.value, e.ip, e.detail) for e in result.events],
            )
            conn.execute(
                "INSERT INTO scans (started, duration, found, method) VALUES (?, ?, ?, ?)",
                (started, finished - started, len(result.seen), method),
            )
        return result

    def save_failed_scan(self, *, started: float, finished: float, method: str, error: str) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO scans (started, duration, found, method, error) VALUES (?, ?, 0, ?, ?)",
                (started, finished - started, method, error),
            )

    def update_device(self, mac: str, edit: DeviceEdit) -> Device | None:
        assignments: list[str] = []
        params: list[Any] = []
        if "alias" in edit:
            assignments.append("alias = ?")
            params.append((edit["alias"] or "").strip() or None)
        if "notes" in edit:
            assignments.append("notes = ?")
            params.append((edit["notes"] or "").strip() or None)
        if "known" in edit:
            assignments.append("known = ?")
            params.append(int(edit["known"]))
        if "dev_type" in edit:
            if edit["dev_type"] == "auto":
                assignments.append("type_locked = 0")
            else:
                assignments += ["dev_type = ?", "type_locked = 1"]
                params.append(DeviceType(edit["dev_type"]).value)

        with self._transaction() as conn:
            if assignments:
                updated = conn.execute(f"UPDATE devices SET {', '.join(assignments)} WHERE mac = ?", (*params, mac))
                if not updated.rowcount:
                    return None
            row = conn.execute("SELECT * FROM devices WHERE mac = ?", (mac,)).fetchone()
        return _to_device(row) if row else None

    def delete_device(self, mac: str) -> bool:
        with self._transaction() as conn:
            deleted = conn.execute("DELETE FROM devices WHERE mac = ?", (mac,)).rowcount
            conn.execute("DELETE FROM sightings WHERE mac = ?", (mac,))
            conn.execute("DELETE FROM events WHERE mac = ?", (mac,))
        return bool(deleted)

    def prune(self, *, now: float, history_days: int) -> None:
        history_cutoff = now - history_days * DAY
        with self._transaction() as conn:
            conn.execute("DELETE FROM sightings WHERE ts < ?", (history_cutoff,))
            conn.execute("DELETE FROM scans WHERE started < ?", (history_cutoff,))
            conn.execute("DELETE FROM events WHERE ts < ?", (now - max(EVENT_RETENTION_DAYS, history_days) * DAY,))

    def is_empty(self) -> bool:
        return not self._fetchall("SELECT 1 FROM devices LIMIT 1")

    def devices(self) -> list[Device]:
        return [_to_device(row) for row in self._fetchall("SELECT * FROM devices")]

    def device(self, mac: str) -> Device | None:
        rows = self._fetchall("SELECT * FROM devices WHERE mac = ?", (mac,))
        return _to_device(rows[0]) if rows else None

    def presence(self, *, now: float, window: float = DAY, buckets: int = 48) -> dict[str, list[PresenceMark]]:
        start = now - window
        size = window / buckets
        last = buckets - 1
        scanned = {
            min(int(row[0]), last)
            for row in self._fetchall(
                "SELECT DISTINCT CAST((started - ?) / ? AS INTEGER) FROM scans WHERE started >= ? AND error IS NULL",
                (start, size, start),
            )
        }
        seen: dict[str, set[int]] = defaultdict(set)
        for mac, bucket in self._fetchall(
            "SELECT mac, CAST((ts - ?) / ? AS INTEGER) FROM sightings WHERE ts >= ? GROUP BY 1, 2",
            (start, size, start),
        ):
            seen[mac].add(min(int(bucket), last))

        def to_marks(marks: set[int]) -> list[PresenceMark]:
            return [1 if b in marks else 0 if b in scanned else None for b in range(buckets)]

        empty = to_marks(set())
        return defaultdict(lambda: list(empty), {mac: to_marks(marks) for mac, marks in seen.items()})

    def events(self, limit: int = 50) -> list[EventView]:
        rows = self._fetchall(
            """SELECT e.id, e.ts, e.mac, e.kind, e.ip, e.detail, d.alias, d.hostname, d.vendor, d.dev_type
               FROM events e LEFT JOIN devices d ON d.mac = e.mac
               ORDER BY e.ts DESC, e.id DESC
               LIMIT ?""",
            (limit,),
        )
        return [
            EventView(
                id=row["id"],
                ts=row["ts"],
                mac=row["mac"],
                kind=EventKind(row["kind"]),
                ip=row["ip"],
                detail=row["detail"],
                alias=row["alias"],
                hostname=row["hostname"],
                vendor=row["vendor"],
                dev_type=DeviceType(row["dev_type"]) if row["dev_type"] else None,
            )
            for row in rows
        ]

    def last_scan(self) -> ScanRecord | None:
        rows = self._fetchall("SELECT * FROM scans ORDER BY id DESC LIMIT 1")
        return ScanRecord(**dict(rows[0])) if rows else None
