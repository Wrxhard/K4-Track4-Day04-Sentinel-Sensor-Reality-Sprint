"""Download official YOLOv8 weights and prepare a browser-compatible sample."""
import argparse
import os
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".runtime"))


def download(url, destination):
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Downloading {destination.name}…", flush=True)
    urllib.request.urlretrieve(url, temporary)
    temporary.replace(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", help="Optional path to FFmpeg with libx264")
    args = parser.parse_args()
    download("https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt", ROOT / "models" / "yolov8n.pt")
    download("https://ultralytics.com/images/bus.jpg", ROOT / "tests" / "bus.jpg")
    sample = ROOT / "dist" / "media" / "sample.mp4"
    if sample.exists():
        print("Weights and sample ready.")
        return
    import cv2
    import numpy as np
    photo = cv2.imread(str(ROOT / "tests" / "bus.jpg"))
    if photo is None:
        raise RuntimeError("Sample image could not be read")
    scale = min(960 / photo.shape[1], 540 / photo.shape[0])
    photo = cv2.resize(photo, (int(photo.shape[1] * scale), int(photo.shape[0] * scale)))
    positive = np.zeros((540, 960, 3), dtype=np.uint8)
    y, x = (540 - photo.shape[0]) // 2, (960 - photo.shape[1]) // 2
    positive[y:y + photo.shape[0], x:x + photo.shape[1]] = photo
    empty = np.full((540, 960, 3), (18, 13, 8), dtype=np.uint8)
    sample.parent.mkdir(parents=True, exist_ok=True)
    if not args.ffmpeg:
        import imageio_ffmpeg
        args.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
               "-pix_fmt", "bgr24", "-s", "960x540", "-r", "20", "-i", "pipe:0", "-an",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", str(sample)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        # Six seconds of real objects, then six seconds of empty frames.
        for i in range(240):
            process.stdin.write((positive if i < 120 else empty).tobytes())
    finally:
        process.stdin.close()
    if process.wait() != 0:
        sample.unlink(missing_ok=True)
        raise RuntimeError("FFmpeg sample generation failed")
    print("Weights and 12-second H.264 sample ready.")


if __name__ == "__main__":
    main()
