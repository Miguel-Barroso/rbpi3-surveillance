#!/usr/bin/env python3
"""
snapshot_stream.py

A tiny Flask app that captures MJPEG frames from the first
available UVC camera (/dev/video*) and serves them as an
HTTP multipart stream at /stream.

Usage:
    python3 snapshot_stream.py --host 0.0.0.0 --port 8080 --fps 25 --quality 30
"""

import glob
import time
import signal
import sys
import cv2
from flask import Flask, Response
import argparse
import logging

# ─── Configuration & Argument Parsing ─────────────────────────────────────

parser = argparse.ArgumentParser(
    description="MJPEG snapshot streamer for a USB UVC camera"
)
parser.add_argument(
    "--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)"
)
parser.add_argument(
    "--port", type=int, default=8080, help="Port to listen on (default: 8080)"
)
parser.add_argument(
    "--fps", type=float, default=25.0, help="Maximum frame rate (default: 25)"
)
parser.add_argument(
    "--quality",
    type=int,
    default=30,
    help="JPEG quality (1–100, higher is better image, default: 30)",
)
parser.add_argument(
    "--buffersize",
    type=int,
    default=1,
    help="OpenCV buffer size per the V4L backend (default: 1)",
)
args = parser.parse_args()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = Flask(__name__)

# ─── Camera Initialization ────────────────────────────────────────────────

def find_uvc_device(buffer_size):
    """Find and open the first working /dev/video* device."""
    for dev in sorted(glob.glob("/dev/video*")):
        cap = cv2.VideoCapture(dev)
        if not cap.isOpened():
            cap.release()
            continue
        # Minimal buffering to reduce latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
        logging.info(f"Opened camera at {dev}")
        return cap
        # release() happens automatically on reassign/reopen
    raise RuntimeError("No UVC camera found on /dev/video*")

cap = find_uvc_device(buffer_size=args.buffersize)

# Graceful shutdown
def cleanup(signum, frame):
    logging.info("Shutting down, releasing camera…")
    cap.release()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# ─── Frame Generator ──────────────────────────────────────────────────────

def gen_frames():
    interval = 1.0 / args.fps
    while True:
        success, frame = cap.read()
        if not success:
            logging.warning("Frame read failed, retrying…")
            time.sleep(0.1)
            continue

        # Encode to JPEG
        ret, buffer = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), args.quality]
        )
        if not ret:
            logging.warning("JPEG encode failed, skipping frame…")
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )

        time.sleep(interval)

# ─── Flask Route ─────────────────────────────────────────────────────────

@app.route("/stream")
def stream():
    """Stream MJPEG frames as multipart/x-mixed-replace."""
    return Response(
        gen_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

# ─── Entrypoint ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.info(f"Starting server on http://{args.host}:{args.port}/stream")
    app.run(host=args.host, port=args.port, threaded=True)
