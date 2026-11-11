#!/usr/bin/env python3
"""Record demo video of Cortex Zero Adaptive plugin showing 3 recovery scenarios."""
import subprocess
import time
import os

# Start ffmpeg recording Xvfb display :99
output_path = "/home/professor/.hermes/plugins/cortex-zero-adaptive/demo_video.mp4"
print(f"Starting screen recording to {output_path}")

# Record at 30fps, 1280x720 from Xvfb :99
ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-f", "x11grab",
    "-framerate", "30",
    "-s", "1280x720",
    "-i", ":99",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "23",
    "-pix_fmt", "yuv420p",
    output_path
]

rec_process = subprocess.Popen(ffmpeg_cmd)
print(f"Recording started (PID: {rec_process.pid})")

# Give ffmpeg a moment to start
time.sleep(2)

# Run the demo scenarios via the plugin's demo tool
import asyncio
import sys
import json
sys.path.insert(0, "/home/professor/.hermes/plugins/cortex-zero-adaptive")

from tools import cz_adaptive_demo

async def run_demos():
    print("\n=== DEMO 1: Navigation Failure Recovery ===")
    result = cz_adaptive_demo({"demo": "navigation_failure"})
    print(f"Result: {result}")
    
    time.sleep(3)
    
    print("\n=== DEMO 2: Element Not Found Recovery ===")
    result = cz_adaptive_demo({"demo": "element_not_found"})
    print(f"Result: {result}")
    
    time.sleep(3)
    
    print("\n=== DEMO 3: Policy Blocked Recovery ===")
    result = cz_adaptive_demo({"demo": "policy_blocked"})
    print(f"Result: {result}")
    
    time.sleep(3)

asyncio.run(run_demos())

# Stop recording
print("\nStopping recording...")
rec_process.terminate()
rec_process.wait(timeout=10)
print(f"Demo video saved to {output_path}")

# Verify file
size = os.path.getsize(output_path)
print(f"File size: {size / 1024 / 1024:.1f} MB")