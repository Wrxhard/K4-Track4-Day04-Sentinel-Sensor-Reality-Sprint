"""Local YOLOv8 gateway and dashboard server. Run with one uvicorn worker."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".runtime"))
Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")

import cv2
import numpy as np
import psutil
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from ultralytics import YOLO

from .core import DetectionPolicy, LatestFrameQueue, Pacer, Settings, Window, pack_frame, unpack_frame

MODEL_PATH = ROOT / "models" / "yolov8n.pt"
model = None
device = "cpu"
inference_lock = asyncio.Lock()
session_lock = asyncio.Lock()
hardware = {"cpu_percent": None, "process_cpu_percent": None, "gpu_percent": None,
            "gpu_memory_mb": None, "gpu_name": None, "memory_mb": None}


def sample_hardware(process):
    values = {"cpu_percent": psutil.cpu_percent(),
              "process_cpu_percent": process.cpu_percent() / (psutil.cpu_count() or 1),
              "memory_mb": process.memory_info().rss / 1024 ** 2,
              "gpu_percent": None, "gpu_memory_mb": None, "gpu_name": None}
    executable = shutil.which("nvidia-smi")
    if executable:
        try:
            result = subprocess.run([executable, "--query-gpu=name,utilization.gpu,memory.used",
                                     "--format=csv,noheader,nounits", "--id=0"],
                                    capture_output=True, text=True, timeout=2,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode == 0:
                name, load, memory = [part.strip() for part in result.stdout.strip().split(",")]
                values.update(gpu_name=name, gpu_percent=float(load), gpu_memory_mb=float(memory))
        except (ValueError, OSError, subprocess.TimeoutExpired):
            pass
    return values


async def hardware_loop():
    process = psutil.Process()
    psutil.cpu_percent()
    process.cpu_percent()
    while True:
        hardware.update(await asyncio.to_thread(sample_hardware, process))
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app):
    global model, device
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    cv2.setNumThreads(2)
    device = os.environ.get("SENTINEL_DEVICE", "0" if torch.cuda.is_available() else "cpu")
    if not MODEL_PATH.exists():
        raise RuntimeError("Missing YOLOv8 weights. Run python setup_demo.py first.")
    model = await asyncio.to_thread(YOLO, str(MODEL_PATH))
    await asyncio.to_thread(model.predict, np.zeros((384, 640, 3), dtype=np.uint8),
                            imgsz=640, device=device, verbose=False)
    task = asyncio.create_task(hardware_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="Sentinel YOLOv8 streaming gateway", lifespan=lifespan)


async def infer_safely(jpeg, settings):
    # A cancelled websocket must wait for its native inference thread before
    # releasing the model lock; otherwise a new session can race that thread.
    async with inference_lock:
        task = asyncio.create_task(asyncio.to_thread(infer, jpeg, settings))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await task
            raise


def allowed_origins():
    origins = {"http://127.0.0.1:8765", "http://localhost:8765"}
    origins.update(x.rstrip("/") for x in os.environ.get("SENTINEL_ALLOWED_ORIGINS", "").split(",") if x)
    return origins


@app.get("/api/health")
async def health():
    return {"ready": model is not None, "model": "YOLOv8n", "device": device,
            "classes": model.names if model else {}, "hardware": hardware,
            "busy": session_lock.locked()}


def infer(jpeg: bytes, settings: Settings):
    start = time.perf_counter()
    frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None or frame.shape[0] > 2160 or frame.shape[1] > 3840:
        raise ValueError("Invalid image or image larger than 3840 × 2160")
    result = model.predict(frame, imgsz=640, conf=settings.confidence,
                           classes=[0], device=device, verbose=False)[0]
    if device != "cpu":
        torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) * 1000
    boxes = [{"class_id": int(box.cls.item()), "label": model.names[int(box.cls.item())],
              "confidence": round(float(box.conf.item()), 3),
              "xyxy": [round(float(x), 1) for x in box.xyxy[0].tolist()]}
             for box in result.boxes]
    return frame, boxes, elapsed


def encode(frame, boxes, profile):
    start = time.perf_counter()
    width, quality = 640, 70
    frame = frame.copy()
    
    # ---------------------------------------------------------
    # Tích hợp Adaptive Resolution (Nén Background, giữ nét ROI)
    # ---------------------------------------------------------
    h, w = frame.shape[:2]
    bg_scale = 0.1 # Tỉ lệ nén background
    small_bg = cv2.resize(frame, (0, 0), fx=bg_scale, fy=bg_scale)
    compressed_bg = cv2.resize(small_bg, (w, h), interpolation=cv2.INTER_NEAREST)
    
    if boxes:
        # Có vật thể -> Tạo mask giữ nét ROI, nén xung quanh
        mask = np.zeros((h, w), dtype=np.uint8)
        for box in boxes:
            x1, y1, x2, y2 = map(int, box["xyxy"])
            pad = 20 # Buffer padding
            cv2.rectangle(mask, (max(0, x1-pad), max(0, y1-pad)), (min(w, x2+pad), min(h, y2+pad)), 255, -1)
            
        mask = cv2.GaussianBlur(mask, (21, 21), 0)
        mask_3d = np.dstack([mask.astype(float) / 255.0]*3)
        frame = (frame.astype(float) * mask_3d + compressed_bg.astype(float) * (1 - mask_3d)).astype(np.uint8)
    else:
        # Không có vật thể -> Nén toàn bộ
        frame = compressed_bg
    # ---------------------------------------------------------

    for box in boxes:
        x1, y1, x2, y2 = map(int, box["xyxy"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (105, 227, 91), 2)
        cv2.putText(frame, f'{box["label"]} {box["confidence"]:.0%}', (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, .55, (105, 227, 91), 2)
    scale = min(1, width / frame.shape[1])
    if scale < 1:
        frame = cv2.resize(frame, (int(frame.shape[1] * scale), int(frame.shape[0] * scale)))
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return jpeg.tobytes(), (time.perf_counter() - start) * 1000, frame.shape[1], frame.shape[0], quality


@app.websocket("/ws")
async def stream(ws: WebSocket):
    # Loopback only by default, and reject unrelated browser origins.
    origin = ws.headers.get("origin", "").rstrip("/")
    if origin and origin not in allowed_origins():
        await ws.close(code=1008, reason="Origin not allowed")
        return
    if session_lock.locked():
        await ws.close(code=1013, reason="Another stream is running")
        return
    await ws.accept()
    async with session_lock:
        settings = Settings()
        queue = LatestFrameQueue()
        policy, pacer = DetectionPolicy(), Pacer()
        target_fps = settings.idle_fps
        source_window, inference_window, output_window = Window(), Window(), Window()
        processed = delivered = output_bytes = 0
        send_lock = asyncio.Lock()

        async def control(message):
            async with send_lock:
                await ws.send_json(message)

        await control({"type": "ready", "model": "YOLOv8n", "device": device,
                       "hardware": hardware, "classes": model.names})

        async def receive():
            nonlocal settings
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect()
                try:
                    if message.get("bytes") is not None:
                        packet = message["bytes"]
                        frame = unpack_frame(packet)
                        queue.put(frame, len(packet))
                        source_window.add(len(packet))
                    elif message.get("text"):
                        data = json.loads(message["text"])
                        if data.get("type") != "configure":
                            raise ValueError("Unknown control message")
                        settings = Settings.model_validate(data.get("settings", {}))
                        await control({"type": "configured", "settings": settings.model_dump()})
                except (ValueError, ValidationError, TypeError) as error:
                    await control({"type": "error", "message": str(error)[:300]})

        async def process():
            nonlocal processed, delivered, output_bytes, target_fps
            while True:
                # Gate before removing a queued frame so inference always uses
                # the freshest frame captured during the pacing wait.
                await queue.available.wait()
                shape_ms = await pacer.wait(target_fps)
                frame = await queue.get()
                current_settings = settings.model_copy(deep=True)
                try:
                    image, boxes, inference_ms = await infer_safely(frame.jpeg, current_settings)
                    processed += 1
                    inference_window.add(0)
                    profile, target_fps, reason = policy.decide(bool(boxes), current_settings)
                    jpeg, encode_ms, width, height, quality = await asyncio.to_thread(encode, image, boxes, profile)
                    metadata = {"type": "frame", "id": frame.frame_id, "capture_ms": frame.capture_ms,
                                "detected": bool(boxes), "boxes": boxes, "profile": profile,
                                "reason": reason, "target_fps": target_fps, "inference_ms": inference_ms,
                                "encode_ms": encode_ms, "width": width, "height": height, "quality": quality,
                                "device": device, "hardware": dict(hardware)}
                    source_fps, input_kbps = source_window.rates()
                    inference_fps, _ = inference_window.rates()
                    _, output_kbps = output_window.rates()
                    metadata.update(source_fps=source_fps, input_kbps=input_kbps, inference_fps=inference_fps,
                                    output_kbps=output_kbps, shape_ms=shape_ms,
                                    counters={"received": queue.received, "processed": processed,
                                              "delivered": delivered + 1, "dropped": queue.dropped,
                                              "output_bytes": output_bytes}, settings=current_settings.model_dump())
                    packet = pack_frame(metadata, jpeg)
                    async with send_lock:
                        await ws.send_bytes(packet)
                    delivered += 1
                    output_bytes += len(packet)
                    output_window.add(len(packet))
                except ValueError as error:
                    queue.dropped += 1
                    await control({"type": "error", "message": str(error)})

        receiver, processor = asyncio.create_task(receive()), asyncio.create_task(process())
        try:
            done, _ = await asyncio.wait([receiver, processor], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, RuntimeError):
            pass
        except Exception:
            with contextlib.suppress(Exception):
                await control({"type": "error", "message": "Processing failed; check the gateway terminal."})
        finally:
            receiver.cancel()
            processor.cancel()
            await asyncio.gather(receiver, processor, return_exceptions=True)


app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="dashboard")
