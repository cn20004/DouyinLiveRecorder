# -*- encoding: utf-8 -*-
"""
Zhenglaoshi mod: Douyin live comments/viewer persistence.

This module intentionally stays independent from the video recorder. It consumes
normalized Douyin events from a local DyHub-compatible SSE endpoint and stores
them in SQLite. Collector failures never interrupt video recording.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from .utils import logger


EVENT_TYPES = "chat,gift,member,like,follow,room"


def extract_douyin_web_rid(url: str, room_json: dict | None = None) -> str | None:
    """Best-effort web_rid extraction for live.douyin.com rooms."""
    match = re.search(r"live\.douyin\.com/(\d+)", url or "")
    if match:
        return match.group(1)

    room_json = room_json or {}
    owner = room_json.get("owner") or {}
    for value in (
        owner.get("web_rid"),
        owner.get("webRid"),
        room_json.get("web_rid"),
        room_json.get("webRid"),
    ):
        if value:
            return str(value)
    return None


class DouyinEventStore:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS douyin_events (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    platform TEXT,
                    type TEXT NOT NULL,
                    event_ts INTEGER,
                    received_at INTEGER,
                    user_id TEXT,
                    nickname TEXT,
                    sec_uid TEXT,
                    content TEXT,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_douyin_events_room_ts
                    ON douyin_events(room_id, event_ts);
                CREATE INDEX IF NOT EXISTS idx_douyin_events_type_ts
                    ON douyin_events(type, event_ts);
                CREATE INDEX IF NOT EXISTS idx_douyin_events_nickname
                    ON douyin_events(nickname);

                CREATE TABLE IF NOT EXISTS douyin_room_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL,
                    event_ts INTEGER NOT NULL,
                    online_total INTEGER,
                    popularity INTEGER,
                    total_user INTEGER,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_douyin_room_stats_room_ts
                    ON douyin_room_stats(room_id, event_ts);

                CREATE TABLE IF NOT EXISTS douyin_monitor_sessions (
                    room_id TEXT PRIMARY KEY,
                    anchor_name TEXT,
                    source_url TEXT,
                    collector_url TEXT,
                    status TEXT,
                    started_at INTEGER,
                    last_event_at INTEGER,
                    last_error TEXT
                );
                """
            )

    def upsert_session(
        self,
        room_id: str,
        anchor_name: str,
        source_url: str,
        collector_url: str,
        status: str,
        last_error: str = "",
    ) -> None:
        now = int(time.time() * 1000)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO douyin_monitor_sessions
                    (room_id, anchor_name, source_url, collector_url, status,
                     started_at, last_event_at, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(room_id) DO UPDATE SET
                    anchor_name=excluded.anchor_name,
                    source_url=excluded.source_url,
                    collector_url=excluded.collector_url,
                    status=excluded.status,
                    last_error=excluded.last_error
                """,
                (
                    room_id, anchor_name, source_url, collector_url, status,
                    now, now, last_error[:2000],
                ),
            )

    def touch_session(self, room_id: str, status: str = "connected", error: str = "") -> None:
        now = int(time.time() * 1000)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE douyin_monitor_sessions
                SET status=?, last_event_at=?, last_error=?
                WHERE room_id=?
                """,
                (status, now, error[:2000], room_id),
            )

    def save_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "unknown")
        room_id = str(event.get("roomId") or "")
        if not room_id:
            return

        event_ts = int(event.get("ts") or event.get("receivedAt") or time.time() * 1000)
        received_at = int(event.get("receivedAt") or event_ts)
        user = event.get("user") or {}
        data = event.get("data") or {}
        event_id = str(
            event.get("id")
            or f"{room_id}:{event_type}:{event_ts}:{user.get('id','')}:{hash(json.dumps(event, ensure_ascii=False, sort_keys=True))}"
        )
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        content = data.get("content")
        if content is not None:
            content = str(content)

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO douyin_events
                    (id, room_id, platform, type, event_ts, received_at,
                     user_id, nickname, sec_uid, content, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    room_id,
                    str(event.get("platform") or "douyin"),
                    event_type,
                    event_ts,
                    received_at,
                    str(user.get("id") or ""),
                    str(user.get("nickname") or ""),
                    str(user.get("secUid") or ""),
                    content,
                    payload,
                    int(time.time() * 1000),
                ),
            )

            if event_type == "room":
                conn.execute(
                    """
                    INSERT INTO douyin_room_stats
                        (room_id, event_ts, online_total, popularity, total_user, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        room_id,
                        event_ts,
                        _safe_int(data.get("total")),
                        _safe_int(data.get("popularity")),
                        _safe_int(data.get("totalUser")),
                        payload,
                    ),
                )


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


class DouyinMonitorManager:
    """Manage one daemon SSE consumer per Douyin live room."""

    def __init__(self, collector_url: str, db_path: str):
        self.collector_url = collector_url.rstrip("/")
        self.store = DouyinEventStore(db_path)
        self._threads: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def start_room(self, room_id: str, anchor_name: str, source_url: str) -> bool:
        room_id = str(room_id)
        with self._lock:
            thread = self._threads.get(room_id)
            if thread and thread.is_alive():
                return False
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._run_room,
                name=f"douyin-monitor-{room_id}",
                args=(room_id, anchor_name, source_url, stop_event),
                daemon=True,
            )
            self._stops[room_id] = stop_event
            self._threads[room_id] = thread
            thread.start()
            return True

    def stop_room(self, room_id: str) -> None:
        with self._lock:
            stop_event = self._stops.get(str(room_id))
            if stop_event:
                stop_event.set()

    def _connect_room(self, client: httpx.Client, room_id: str) -> None:
        response = client.post(
            f"{self.collector_url}/api/rooms/connect",
            json={"roomId": room_id},
            timeout=20,
        )
        # "already connected" can be exposed as 409 by compatible collectors.
        if response.status_code not in (200, 201, 202, 204, 409):
            raise RuntimeError(
                f"collector connect failed: HTTP {response.status_code} {response.text[:300]}"
            )

    def _run_room(
        self,
        room_id: str,
        anchor_name: str,
        source_url: str,
        stop_event: threading.Event,
    ) -> None:
        retry = 0
        self.store.upsert_session(
            room_id, anchor_name, source_url, self.collector_url, "starting"
        )

        while not stop_event.is_set():
            try:
                with httpx.Client(timeout=None) as client:
                    self._connect_room(client, room_id)
                    self.store.touch_session(room_id, "connected")
                    retry = 0

                    params = {"roomId": room_id, "types": EVENT_TYPES}
                    with client.stream(
                        "GET",
                        f"{self.collector_url}/api/events",
                        params=params,
                        headers={"Accept": "text/event-stream"},
                    ) as response:
                        response.raise_for_status()
                        data_lines: list[str] = []

                        for line in response.iter_lines():
                            if stop_event.is_set():
                                break

                            if line == "":
                                if data_lines:
                                    raw = "\n".join(data_lines)
                                    data_lines.clear()
                                    try:
                                        event = json.loads(raw)
                                        if event.get("type") == "__hello":
                                            continue
                                        self.store.save_event(event)
                                        self.store.touch_session(room_id, "connected")
                                    except json.JSONDecodeError:
                                        logger.warning(
                                            f"抖音弹幕事件JSON解析失败 room={room_id}: {raw[:300]}"
                                        )
                                continue

                            if line.startswith("data:"):
                                data_lines.append(line[5:].lstrip())

                if stop_event.is_set():
                    break

            except Exception as err:
                retry += 1
                delay = min(60, max(5, retry * 5))
                self.store.touch_session(room_id, "reconnecting", str(err))
                logger.warning(
                    f"抖音评论/人数采集断开 [{anchor_name or room_id}]：{err}，{delay}秒后重连"
                )
                stop_event.wait(delay)

        self.store.touch_session(room_id, "stopped")
