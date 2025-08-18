# 2025-07-04 RBPi3 Surveillance Setup

## Background  
I had an old Raspberry Pi 3 B and a Logitech C920 USB webcam lying around, and wanted a cheap headless surveillance solution. Unfortunately, the Pi 3’s single USB-OTG bus (which it shares between the four USB ports and Ethernet/Wi-Fi) chokes when you try to push a high-bitrate H.264 or MJPEG RTSP stream in real time — even at modest resolutions like 320 × 240@10 fps the kernel logs would show `dwc2_hc_halt() channel can’t be halted` and the camera would disconnect entirely (see ```sudo dmseg -w```).

Watching the same device locally under Raspbian (via VLC’s “Capture Device”) worked fine in full-HD, so I realized that continuous streaming was the problem. Instead, I needed to:

1. **Snapshot** frames at a controlled rate (≤ 25 fps)  
2. **Serve** them as a simple MJPEG HTTP stream with minimal buffering  

## Troubleshooting Attempts

- **v4l2rtspserver** (MJPEG / H.264) → green artifacts, dropped frames, USB bus resets  
- **ffmpeg / cvlc** pipelines → frequent resets, unsupported/YUYV codec errors, panics  
- **Alternative OS (Ubuntu 24.04)** → same USB bus faults under load  
- **Unplug peripherals** (headless) → no improvement  

## Final Solution: Flask + OpenCV MJPEG Snapshots
Approach: Instead of a continuous video stream, capture single JPEG frames at up to 25 fps and serve them as an MJPEG HTTP stream.

Built a tiny **Flask + OpenCV** snapshot server:

- **Auto-detect** first working `/dev/video*`  
- **Cap OpenCV buffer** to 1 frame → minimal latency  
- **JPEG encode** at configurable quality (default 30)  
- **Limit FPS** (default 25) via `time.sleep()`  
- **Stream over HTTP** as `multipart/x-mixed-replace` → ingestible by VLC, QVR Pro, web browsers, etc.  
- **Systemd service** for auto-start, restart on failure, headless operation  
- **Remote access** via Tailscale + SSH

Script: /usr/local/bin/snapshot_stream.py supports these CLI arguments:
```
--host: bind address (default 0.0.0.0)

--port: HTTP port (default 8080)

--fps: target frames per second (capped to avoid bus overload)

--quality: JPEG quality (e.g. 30–50)

snapshot_stream.py --host 0.0.0.0 --port 8080 --fps 25 --quality 30
```

### Repo Layout
```
rbpi3-surveillance/
├── snapshot_stream.py        # main Flask/OpenCV MJPEG streamer
├── requirements.txt          # Flask, opencv-python
├── snapshot-stream.service   # systemd unit (auto-restart, 1 sec delay)
├── README.md                 # install & usage instructions
└── LICENSE                   # GNU GPL v3
```

### Key Script Features

```python
#!/usr/bin/env python3
"""
snapshot_stream.py

- Finds & opens first UVC camera (/dev/video*).
- Serves `http://<pi>:8080/stream` as low-latency MJPEG.
- Args: --host, --port, --fps, --quality, --buffersize.
"""
import glob, time, signal, sys, argparse, logging, cv2
from flask import Flask, Response

# …[see full script in repo]…

Args:

    --fps 25 (max)

    --quality 30 (JPEG)

    --buffersize 1 (OpenCV CAP_PROP_BUFFERSIZE)

Logging for startup & frame-read failures

Graceful shutdown on SIGINT/SIGTERM
```

### Systemd Unit (snapshot-stream.service)

Auto-restarts on failure with a 1 s delay

Hardcodes default port 8080, but you can change it via ExecStart arguments or an EnvironmentFile

```bash
[Unit]
Description=MJPEG Snapshot Streamer
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/snapshot_stream.py \
    --host 0.0.0.0 --port 8080 --fps 25 --quality 30
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
```

Change to port 9090:
```bash
ExecStart=/usr/local/bin/snapshot_stream.py \
    --host 0.0.0.0 --port 9090 --fps 25 --quality 30
```


### Usage
```bash
sudo apt update
sudo apt install python3-opencv python3-flask
pip3 install -r requirements.txt
```

```bash
sudo cp snapshot_stream.py /usr/local/bin/
sudo cp snapshot-stream.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now snapshot-stream
```
Stream URL: http://192.168.1.50:8080/stream <-- Your RBPi's IP or Tailscale

Ingestors tested: VLC (desktop & mobile), QVR Pro (QNAP), web browsers

### Results

- Stable 640 × 480 JPEG stream at 25 fps

- No USB bus panics under sustained load

- Low CPU usage (~10–15 %), no audio

- Headless + remote management via Tailscale/SSH

### Lessons learned:

When the USB-OTG bus can’t handle a real-time encode & transport pipeline, switch to a snapshot-based MJPEG server.

Simple HTTP multipart streams can be surprisingly robust on constrained hardware.

A minimal Flask + OpenCV service is easier to tune & debug than full-blown RTSP or FFmpeg pipelines.

# Update 2025-07-05: Simplified Workflow
## Background

Why reinvent the wheel when the solution already exists?
I discovered that pure MJPEG frame capture and restreaming is a well-established approach. This is exactly how OctoPi manages to run smoothly on an RPi3 with a USB camera. It’s not “streaming” in the modern sense, but this is how webcams worked back in the day. Fun fact: one of the very first Internet use cases was watching a coffee pot drip!

## MJPG-Streamer

First, install the mjpeg-streamer-experimental fork, which works well with Raspberry Pi:

```git clone https://github.com/jacksonliam/mjpg-streamer.git```

You’ll also need the following libraries and cmake:

```apt install -y git build-essential libjpeg-dev libv4l-dev cmake```

Then build and install:

```
cd mjpg-streamer/mjpg-streamer-experimental
make
make install
```

Find your device ID (usually ```/dev/video0```). Then run mjpg_streamer to capture MJPEG frames. You can control the frame rate with ```-f``` and resolution with ```-r```.

Example:
```
mjpg_streamer \
  -i "input_uvc.so -d /dev/video0 -r 1280x720 -f 20 -q 80" \
  -o "output_http.so -w /usr/local/share/mjpg-streamer/www -p 8080"
```
Make sure port ***8080*** is available.

## Systemd Service

Create ```/etc/systemd/system/mjpg-streamer.service```:

```
[Unit]
Description=MJPG-Streamer webcam service
After=network.target

[Service]
# Make sure we respawn on crash
Restart=always
RestartSec=1

# Run as your mjpg-streamer user (replace 'pi' if different)
User=********
Group=********

# Point to the installed binaries & plugins
ExecStart=/usr/local/bin/mjpg_streamer \
  -i "input_uvc.so -d /dev/video0 -r 1280x720 -f 20" \
  -o "output_http.so -p 8080 -w /usr/local/share/mjpg-streamer/www -c admin:****************"

# Log to journal
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Then reload systemd and enable the service:

```
systemctl daemon-reload
systemctl enable mjpg-streamer
```

Check status and logs:

```systemctl status mjpg-streamer.service```

If you make changes, restart the service:
```systemctl restart mjpg-streamer```

## Summary

You now have a perpetually running service that captures JPEG frames from any webcam—even on low-powered devices like the Raspberry Pi 3—and serves them over the network. This simulates “modern” webcam streaming using simple, lightweight tools.

In other words: you can do this today with hardware you already have—no need to buy a CCTV system!