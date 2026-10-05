import asyncio
import json
import struct
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import app
from backend.core import DetectionPolicy, Frame, LatestFrameQueue, Pacer, Settings, pack_frame, unpack_frame


def test_person_policy_holds_then_reduces_fps():
    policy = DetectionPolicy()
    settings = Settings(hold_seconds=1.5)
    assert policy.decide(False, settings, now=0)[0] == "idle"
    assert policy.decide(True, settings, now=1)[:2] == ("active", 15)
    assert policy.decide(False, settings, now=2)[0] == "active"
    assert policy.decide(False, settings, now=3)[:2] == ("idle", 2)
    assert policy.decide(True, settings, now=4)[:2] == ("active", 15)


def test_invalid_fps_is_rejected():
    with pytest.raises(ValidationError):
        Settings(idle_fps=10, active_fps=5)
    with pytest.raises(ValidationError):
        Settings(active_fps=31)
    with pytest.raises(ValidationError):
        Settings(classes=[5])  # Person-only inference cannot be overridden.


def test_queue_keeps_latest_and_accounts_for_replacements():
    async def scenario():
        queue = LatestFrameQueue()
        for i in range(10):
            queue.put(Frame(i, 100, b"test"), 4)
        assert queue.received == 10
        assert queue.dropped == 9
        assert queue.input_bytes == 40
        assert (await queue.get()).frame_id == 9
    asyncio.run(scenario())


def test_pacer_enforces_fps_and_adapts_to_faster_rate():
    async def scenario():
        pacer = Pacer()
        start = time.monotonic()
        await pacer.wait(10)
        await pacer.wait(10)
        await pacer.wait(20)
        assert time.monotonic() - start >= .145
    asyncio.run(scenario())


def test_wire_format_and_bad_packets():
    packet = pack_frame({"id": 7, "capture_ms": 42.5}, b"jpeg")
    assert unpack_frame(packet) == Frame(7, 42.5, b"jpeg")
    with pytest.raises(ValueError):
        unpack_frame(b"short")
    with pytest.raises(ValueError):
        unpack_frame(pack_frame({"id": 1, "capture_ms": float("inf")}, b"jpeg"))


def decode_output(packet):
    size = struct.unpack("!I", packet[:4])[0]
    return json.loads(packet[4:4 + size]), cv2.imdecode(np.frombuffer(packet[4 + size:], np.uint8), cv2.IMREAD_COLOR)


def test_real_yolov8_websocket_detects_then_reduces_and_recovers():
    photo = cv2.imread(str(Path(__file__).parent / "bus.jpg"))
    assert photo is not None
    _, positive = cv2.imencode(".jpg", photo)
    _, negative = cv2.imencode(".jpg", np.zeros((540, 960, 3), dtype=np.uint8))
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ready"]
        assert client.get("/").status_code == 200
        with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:8765"}) as ws:
            assert ws.receive_json()["model"] == "YOLOv8n"
            ws.send_json({"type": "configure", "settings": {"hold_seconds": 0}})
            assert ws.receive_json()["type"] == "configured"
            for frame_id, jpeg, expected in [(1, positive, True), (2, negative, False), (3, positive, True)]:
                started = time.monotonic()
                ws.send_bytes(pack_frame({"id": frame_id, "capture_ms": frame_id * 100}, jpeg.tobytes()))
                metadata, image = decode_output(ws.receive_bytes())
                assert metadata["detected"] is expected
                assert metadata["profile"] == ("active" if expected else "idle")
                assert metadata["target_fps"] == (15 if expected else 2)
                assert all(box["class_id"] == 0 for box in metadata["boxes"])
                assert image.shape[1] <= 640
                assert metadata["quality"] == 70
                assert image is not None
                assert metadata["counters"]["delivered"] == frame_id
                assert metadata["inference_ms"] > 0
                assert time.monotonic() - started >= metadata["shape_ms"] / 1000 * .95
            ws.send_json({"type": "configure", "settings": {"idle_fps": 10, "active_fps": 5}})
            assert ws.receive_json()["type"] == "error"
            # Send a burst faster than inference and shaping: stale queued frames
            # must be replaced, with drops counted and the latest frame retained.
            for i in range(4, 14):
                ws.send_bytes(pack_frame({"id": i, "capture_ms": i * 100}, positive.tobytes()))
            last = None
            for _ in range(10):
                last, _ = decode_output(ws.receive_bytes())
                if last["id"] == 13:
                    break
            assert last["id"] == 13
            assert last["counters"]["dropped"] > 0
            assert last["counters"]["received"] == 13
            assert last["counters"]["processed"] + last["counters"]["dropped"] == 13


def test_unknown_browser_origin_cannot_start_inference():
    from starlette.websockets import WebSocketDisconnect
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exception:
            with client.websocket_connect("/ws", headers={"origin": "https://unrelated.example"}):
                pass
        assert exception.value.code == 1008
