"""Bounded local video processing. No shell interpolation or remote video fetching."""

import os
import shutil
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

EDGES = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]


def configure_ffmpeg():
    """Make the bundled converter available to Gradio's video preprocessing too."""
    if shutil.which("ffmpeg"):
        return
    from .storage import root
    tools_dir = root() / "tools"
    tools_dir.mkdir(exist_ok=True)
    link = tools_dir / "ffmpeg"
    if not link.exists():
        link.symlink_to(imageio_ffmpeg.get_ffmpeg_exe())
    os.environ["PATH"] = str(tools_dir) + os.pathsep + os.environ.get("PATH", "")


def encode_mp4(raw_path, output):
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(raw_path),
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)],
                   check=True, capture_output=True, timeout=90)
    Path(raw_path).unlink(missing_ok=True)
    return str(output)


def clip_video(source, output, start, end, duration):
    start, end = max(0, start - 0.65), min(duration, end + 0.65)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", str(start), "-i", str(source),
                    "-t", str(max(0.2, end - start)), "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(output)], check=True, capture_output=True, timeout=45)
    return str(output), round(start, 3), round(end, 3)


def open_video(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 300 * 1024 * 1024:
        raise ValueError("Choose a video smaller than 300 MB.")
    cap = cv2.VideoCapture(str(path))
    fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if not cap.isOpened() or not np.isfinite(fps) or not 1 <= fps <= 240 or count <= 0:
        cap.release()
        raise ValueError("Could not read this video. Upload an MP4 or MOV recording.")
    duration = count / fps
    if duration > 180.1:
        cap.release()
        raise ValueError("Use a recording of three minutes or less. Trim longer footage to the exercise set.")
    w, h = int(cap.get(3)), int(cap.get(4))
    if max(w, h) > 4096 or min(w, h) < 100:
        cap.release()
        raise ValueError("Use a video between 100 and 4096 pixels per side.")
    return cap, fps, duration


def draw_pose(frame, points, scores, angle, t, synthetic=False, caption=None, review=False, parts=None):
    frame = frame.copy()
    if points is not None:
        for a, b in EDGES:
            if scores[a] >= 0.45 and scores[b] >= 0.45:
                colour = (58, 166, 224) if review else (193, 179, 20)
                if parts is not None:
                    part = 'left' if a in (11,13,15) and b in (11,13,15) else 'right' if a in (12,14,16) and b in (12,14,16) else 'trunk' if a in (5,6,11,12) and b in (5,6,11,12) else None
                    colour = {'green':(176,245,137),'yellow':(107,214,255),'red':(120,109,255),'grey':(175,165,157)}[parts.get(part,'grey')]
                cv2.line(frame, tuple(map(int, points[a])), tuple(map(int, points[b])), colour, 3, cv2.LINE_AA)
        for i, point in enumerate(points):
            if scores[i] >= 0.45:
                cv2.circle(frame, tuple(map(int, point)), 4, (237, 249, 255), -1, cv2.LINE_AA)
    caption = caption or ("Tracking uncertain" if angle is None else f"2D interior angle: {angle:.0f} deg")
    if review:
        caption = "Review | " + caption
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 48), (67, 53, 25), -1)
    cv2.putText(frame, f"{t:05.1f}s   {caption}", (16, 31), cv2.FONT_HERSHEY_SIMPLEX, .58, (255, 255, 255), 1, cv2.LINE_AA)
    if synthetic:
        cv2.putText(frame, "ILLUSTRATIVE EXAMPLE - SYNTHETIC LANDMARKS", (18, frame.shape[0] - 22), cv2.FONT_HERSHEY_SIMPLEX, .5, (75, 65, 49), 1, cv2.LINE_AA)
    return frame
