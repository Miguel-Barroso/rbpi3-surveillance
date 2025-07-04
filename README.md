# rbpi3-surveillance
A way to utilize Raspberry Pi 3 as a CCTV

# RBPi3 MJPEG Snapshot Streamer

Turn any UVC USB webcam into a headless MJPEG surveillance camera  
(works around USB-OTG bus limitations on Pi 3 by snapshotting instead of continuous RTSP)

## Features

- Auto-detect first `/dev/video*` device
- Low-latency, minimal AVC buffering
- Configurable FPS & JPEG quality
- Systemd unit for auto start & restart
- Ingest via VLC, QVR Pro, browsers, etc.

## Installation

```bash
sudo apt update
sudo apt install python3-opencv python3-flask
pip3 install -r requirements.txt
```

Copy snapshot_stream.py and snapshot-stream.service into place:

```bash
sudo cp snapshot_stream.py /usr/local/bin/
sudo cp snapshot-stream.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now snapshot-stream
```

## Usage

- Stream URL: http://<pi-ip>:8080/stream <-- Your RBPi's IP or Tailscale

- Custom port / fps / quality:
```bash
python3 snapshot_stream.py --port 9090 --fps 15 --quality 50
```

Feel free to copy this repo and improve upon it!

Buy me a coffee ☕
```bash
BTC: bc1qjsvtd3dd44llyu4rwz2ucl4kp9wd9kvpsj6tk5
```