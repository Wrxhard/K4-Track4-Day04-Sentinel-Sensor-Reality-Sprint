"""Detection policy and bounded, observable streaming primitives."""
from __future__ import annotations

import asyncio
import json
import struct
import time
from collections import deque
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confidence: float = Field(default=0.35, ge=0.05, le=0.95)
    idle_fps: int = Field(default=2, ge=1, le=10)
    active_fps: int = Field(default=15, ge=2, le=30)
    hold_seconds: float = Field(default=1.0, ge=0, le=10)

    @model_validator(mode="after")
    def valid_policy(self):
        if self.idle_fps >= self.active_fps:
            raise ValueError("Idle FPS must be lower than person-present FPS")
        return self


class DetectionPolicy:
    def __init__(self):
        self.last_detection: float | None = None

    def decide(self, detected: bool, settings: Settings, now: float | None = None):
        now = time.monotonic() if now is None else now
        if detected:
            self.last_detection = now
        holding = self.last_detection is not None and now - self.last_detection < settings.hold_seconds
        active = detected or holding
        if active:
            return "active", settings.active_fps, "Person detected" if detected else "Waiting for person to return"
        return "idle", settings.idle_fps, "No person detected"


@dataclass
class Frame:
    frame_id: int
    capture_ms: float
    jpeg: bytes


def pack_frame(metadata: dict, jpeg: bytes) -> bytes:
    header = json.dumps(metadata, separators=(",", ":"), allow_nan=False).encode()
    return struct.pack("!I", len(header)) + header + jpeg


def unpack_frame(packet: bytes) -> Frame:
    if len(packet) < 5 or len(packet) > 2_000_000:
        raise ValueError("Frame packet size is invalid")
    size = struct.unpack("!I", packet[:4])[0]
    if size > 4096 or size < 2 or size + 4 >= len(packet):
        raise ValueError("Frame header size is invalid")
    meta = json.loads(packet[4:4 + size])
    frame_id, capture_ms = meta.get("id"), meta.get("capture_ms")
    if isinstance(frame_id, bool) or not isinstance(frame_id, int) or frame_id < 0:
        raise ValueError("Frame ID is invalid")
    if not isinstance(capture_ms, (int, float)) or not 0 <= capture_ms < 1e15:
        raise ValueError("Capture timestamp is invalid")
    return Frame(frame_id, capture_ms, packet[4 + size:])


class LatestFrameQueue:
    """Keep only the newest waiting frame; count every replaced frame."""
    def __init__(self):
        self.queue: asyncio.Queue[Frame] = asyncio.Queue(maxsize=1)
        self.available = asyncio.Event()
        self.received = 0
        self.dropped = 0
        self.input_bytes = 0

    def put(self, frame: Frame, packet_bytes: int):
        self.received += 1
        self.input_bytes += packet_bytes
        if self.queue.full():
            self.queue.get_nowait()
            self.dropped += 1
        self.queue.put_nowait(frame)
        self.available.set()

    async def get(self):
        frame = await self.queue.get()
        if self.queue.empty():
            self.available.clear()
        return frame


class Pacer:
    """Limit processing frequency; permit immediate response on idle→active."""
    def __init__(self):
        self.last_started = 0.0

    async def wait(self, fps: int):
        start = time.monotonic()
        await asyncio.sleep(max(0, self.last_started + 1 / fps - start))
        self.last_started = time.monotonic()
        return (time.monotonic() - start) * 1000


class Window:
    def __init__(self, seconds=5.0):
        self.seconds = seconds
        self.started = time.monotonic()
        self.items = deque()

    def add(self, size: int):
        now = time.monotonic()
        self.items.append((now, size))
        while self.items and self.items[0][0] < now - self.seconds:
            self.items.popleft()

    def rates(self):
        now = time.monotonic()
        while self.items and self.items[0][0] < now - self.seconds:
            self.items.popleft()
        duration = max(0.1, min(self.seconds, now - self.started))
        return len(self.items) / duration, sum(size for _, size in self.items) * 8 / duration / 1000
