# Sentinel — laptop camera with person-driven FPS

Click **Start camera** at http://127.0.0.1:8765 and allow camera access. The laptop camera is the only input. YOLOv8n detects only people (COCO class 0) at 35% confidence.

- **Nobody detected:** sample, process, and display camera frames at a target of **2 FPS**.
- **Person detected:** switch to a target of **15 FPS**.
- **Person leaves:** keep the higher target for **1 second**, then switch back to 2 FPS. This avoids flickering on brief missed detections.
- Low-rate inference continues so the system can notice someone returning. At 2 FPS, a new person is usually noticed on the next check, within about half a second plus processing time.

The page has one camera view, person boxes, Start/Stop buttons, three settings (idle FPS, person-present FPS, hold time), and measured FPS, latency, drops, and CPU/GPU utilization. Stop shuts down every camera track and clears the displayed camera image. Refresh/navigation also releases the camera. Audio is never requested.

## Start locally

Dependencies and official YOLOv8n weights are already prepared on this computer:

```powershell
cd E:\KyNguyenVuonMinh\Sentinel\demo
.\start.ps1
```

Open http://127.0.0.1:8765. Inference currently uses the CPU-only PyTorch installation. GPU 0 utilization is still measured through nvidia-smi; a value of 0% is expected when that GPU is idle. A separate CUDA-enabled Python environment can be selected with `-PythonPath <python.exe> -Device 0`.

For another computer, install Python 3.11 or 3.12, create a virtual environment, install CPU PyTorch and `requirements.txt`, then run `setup_demo.py` to download the official weights. `requirements-lock.txt` records the validated Windows package versions. The old controlled sample remains a test fixture; it is no longer offered in the interface.

## How FPS changes

```text
Laptop camera → browser sampling → local YOLOv8 person detection
     → select idle/active FPS → return annotated frame + selected FPS
     → browser adjusts its capture timer → repeat
```

The browser actually changes how often it captures and uploads frames. The backend also limits processing frequency and retains only the newest waiting frame during overload. There is no bandwidth budget or artificial network delay in this simplified version. Frame width (maximum 640 pixels) and JPEG quality (70) stay constant, so the primary adaptive variable is FPS.

These are **processed-stream target rates**, not a claim that the camera sensor itself changes its native frame rate. The camera may capture internally at 30 FPS while this application samples it at 2 or 15 FPS. Actual throughput can be lower when inference or the browser cannot keep up.

## Measured metrics

| Metric | Meaning |
| --- | --- |
| Actual FPS | Frames actually displayed / elapsed time in a trailing three-second window. It decays to zero if frames stop arriving. |
| Latency | Browser display time minus the same frame's browser capture time. Includes capture encoding, upload, queue wait, inference, output encoding, return transport, and rendering. Shows median and p95. |
| Dropped frames | Queue replacements plus capture skips caused by upload backpressure. Frames intentionally not sampled at low FPS are **not** counted as dropped frames. |
| CPU / GPU | System CPU from psutil and GPU 0 utilization from nvidia-smi. Hardware readings are approximately once per second. Unavailable GPU telemetry is N/A. |
| Bandwidth estimate | Cameras × sampled frame width × sampled frame height × target FPS × bits/pixel ÷ 1,000,000, in decimal Mbps. Also shows an estimate using actual displayed FPS. Defaults to one camera and 24-bit RGB; both factors are editable. Camera count scales the estimate and does not open additional cameras. This is uncompressed bandwidth, not measured JPEG or WebSocket traffic. |

With the default 640 × 480 frames and 24 bits/pixel, the estimate is **14.75 Mbps at 2 FPS** and **110.59 Mbps at 15 FPS** for one camera. Before startup, the bandwidth card shows idle and person-present previews. While running it uses the actual sampled dimensions and current adaptive target FPS.

A positive person result is a model prediction, not a ground-truth accuracy measurement. Cameras, lighting, occlusion, and confidence can cause missed detections; the hold period reduces frequent switching.

## Validation

```powershell
..\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py -q
node --test tests\metrics.test.mjs
```

Tests cover real person-only YOLOv8 inference, person/empty/person transitions, target FPS selection, hold behavior, pacing, invalid FPS settings, congestion/drop accounting, packet framing, origin restrictions, and actual FPS arithmetic.

This version is served locally. External Sites publication remains unapproved and is not required for laptop-camera use. No camera frames are stored in Sites or sent to a cloud inference service. The local server binds to loopback and accepts only configured browser origins. One session uses the model at a time.

Sources: [YOLOv8 documentation](https://docs.ultralytics.com/models/yolov8/), [official weights](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt), [official person test image](https://ultralytics.com/images/bus.jpg).
