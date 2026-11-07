"""
parallax_animator.py - 100% free "animated 3D scene" look from a single AI image.

Takes the scene image from the existing free image cascade (Pollinations / HF /
Pexels photos / vault), estimates a depth map, and renders a real virtual-camera
move (dolly, orbit, pull-back, rise) where near objects shift more than far ones.
That depth parallax is what makes a still look like a living 3D scene, instead of
a flat picture with a slow zoom.

Depth source (all free, runs on CPU, no API key):
  1. Depth-Anything-V2-Small (Apache-2.0, 24.8M params) via `transformers`
  2. If torch/transformers/model download is unavailable: a built-in pseudo-depth
     (center-near + brightness) so the scene still gets parallax motion.

Public entry point: build_animated_scene_video(...)
"""

import os
import subprocess
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from motion_clips import _concat

W, H, FPS = 1080, 1920, 30
PARALLAX_PIXELS = 34.0   # max shift of the nearest vs farthest layer
DEPTH_MODEL = os.environ.get("DEPTH_MODEL", "depth-anything/Depth-Anything-V2-Small-hf")

_depth_pipe = None
_depth_unavailable = False


# -----------------------------------------------------------------------------
# Depth estimation
# -----------------------------------------------------------------------------

def _load_depth_pipe():
    global _depth_pipe, _depth_unavailable
    if _depth_unavailable:
        return None
    if _depth_pipe is None:
        try:
            from transformers import pipeline  # needs torch (CPU build is fine)
            _depth_pipe = pipeline("depth-estimation", model=DEPTH_MODEL, device=-1)
            print(f"   [Depth] Loaded {DEPTH_MODEL} on CPU")
        except Exception as e:
            print(f"   [Depth Notice] Depth model unavailable ({str(e)[:120]}). Using built-in pseudo-depth.")
            _depth_unavailable = True
            return None
    return _depth_pipe


def _pseudo_depth(base_bgr: np.ndarray) -> np.ndarray:
    """Fallback depth: subject usually sits near the center and brighter areas read as nearer."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W * 0.5) / (W * 0.5)) ** 2 + ((yy - H * 0.52) / (H * 0.62)) ** 2)
    center = np.clip(1.0 - r, 0.0, 1.0)
    gray = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    gray = cv2.GaussianBlur(gray, (0, 0), 25)
    d = 0.75 * center + 0.25 * gray
    lo, hi = float(d.min()), float(d.max())
    return ((d - lo) / (hi - lo + 1e-6)).astype(np.float32)


def estimate_depth(base_bgr: np.ndarray) -> np.ndarray:
    """Return a float32 (H, W) depth map in 0..1 where 1 = nearest to camera."""
    pipe = _load_depth_pipe()
    d = None
    if pipe is not None:
        try:
            rgb = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2RGB)
            out = pipe(Image.fromarray(rgb))["depth"]  # PIL image, bright = near
            d = np.array(out, dtype=np.float32)
            d = cv2.resize(d, (W, H), interpolation=cv2.INTER_CUBIC)
            lo, hi = np.percentile(d, 2), np.percentile(d, 98)
            d = np.clip((d - lo) / (hi - lo + 1e-6), 0.0, 1.0)
        except Exception as e:
            print(f"   [Depth Notice] Depth inference failed ({str(e)[:120]}). Using pseudo-depth.")
            d = None
    if d is None:
        d = _pseudo_depth(base_bgr)
    # Soften depth so layers slide smoothly instead of tearing at edges
    return cv2.GaussianBlur(d, (0, 0), 5).astype(np.float32)


# -----------------------------------------------------------------------------
# Virtual camera
# -----------------------------------------------------------------------------

# zoom (start, end), camera sideways/vertical sweep (start, end), each in -1..1
MOVES = {
    "dolly_in":    {"z": (1.10, 1.30), "cam": ((-0.3, 0.0), (0.3, 0.0))},
    "orbit_right": {"z": (1.18, 1.24), "cam": ((-1.0, 0.1), (1.0, -0.1))},
    "orbit_left":  {"z": (1.18, 1.24), "cam": ((1.0, 0.1), (-1.0, -0.1))},
    "pull_back":   {"z": (1.32, 1.12), "cam": ((0.6, 0.0), (-0.6, 0.0))},
    "rise":        {"z": (1.20, 1.26), "cam": ((0.0, -1.0), (0.0, 1.0))},
}
MOVE_ORDER = ["dolly_in", "orbit_right", "pull_back", "orbit_left", "rise"]


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _cover_resize(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    scale = max(W / w, H / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    interp = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    r = cv2.resize(img_bgr, (nw, nh), interpolation=interp)
    x0, y0 = (nw - W) // 2, (nh - H) // 2
    return r[y0:y0 + H, x0:x0 + W]


def _near_focus(depth: np.ndarray) -> Tuple[float, float]:
    """Centroid of the nearest region = where a close-up cut should punch in."""
    mask = depth > 0.65
    if mask.sum() < 2000:
        return W / 2.0, H / 2.0
    ys, xs = np.nonzero(mask)
    return float(xs.mean()), float(ys.mean())


def _render_frames(base: np.ndarray, depth: np.ndarray, n: int, move: str,
                   focus: Tuple[float, float], zoom_boost: float) -> Iterator[np.ndarray]:
    spec = MOVES[move]
    (z0, z1), ((cx0, cy0), (cx1, cy1)) = spec["z"], spec["cam"]
    z0, z1 = z0 * zoom_boost, z1 * zoom_boost
    zmin = min(z0, z1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    for i in range(n):
        t = _smooth(i / max(1, n - 1))
        z = _lerp(z0, z1, t)
        camx, camy = _lerp(cx0, cx1, t), _lerp(cy0, cy1, t)
        # Which source point sits at screen center (kept inside the image for this zoom)
        fx = float(np.clip(focus[0], W / (2 * zmin), W - W / (2 * zmin)))
        fy = float(np.clip(focus[1], H / (2 * zmin), H - H / (2 * zmin)))
        sx = (xx - W / 2.0) / z + fx
        sy = (yy - H / 2.0) / z + fy
        dz = cv2.remap(depth, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        shift = (dz - 0.5) * PARALLAX_PIXELS
        frame = cv2.remap(base, sx - shift * camx, sy - shift * camy, cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REFLECT_101)
        yield frame


def _encode_frames(ffmpeg: str, frames: Iterator[np.ndarray], n: int, badge: Optional[Path], out: Path) -> None:
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if badge is not None:
        cmd += ["-loop", "1", "-i", str(badge),
                "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1[outv]", "-map", "[outv]"]
    cmd += ["-frames:v", str(n), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for f in frames:
            proc.stdin.write(np.ascontiguousarray(f).tobytes())
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    err = proc.stderr.read().decode("utf-8", "ignore")
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg encode failed: {err[-200:]}")


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------

def build_animated_scene_video(
    ffmpeg: str,
    scene_idx: int,
    dur: float,
    image_prompt: str,
    badge_paths: List[Optional[Path]],
    out_path: Path,
    work_dir: Path,
    image_fn: Callable[[str, int], str],
) -> dict:
    """
    One AI image -> len(badge_paths) animated cuts of 3D-parallax camera motion.
    Cut 1 is a wide camera move, cut 2 punches in on the nearest subject, cut 3 goes wide again, etc.
    Returns {'animated': n_cuts}.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    img_path = Path(image_fn(image_prompt, scene_idx))
    raw = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    if raw is None:
        raise RuntimeError(f"Could not read scene image {img_path}")
    base = _cover_resize(raw)
    depth = estimate_depth(base)
    near_focus = _near_focus(depth)
    center_focus = (W / 2.0, H / 2.0)

    n_sub = len(badge_paths)
    sub_dur = dur / n_sub
    n_frames = max(2, int(round(sub_dur * FPS)))
    parts: List[Path] = []

    for i in range(n_sub):
        move = MOVE_ORDER[(scene_idx * 2 + i) % len(MOVE_ORDER)]
        closeup = (i % 2 == 1)
        frames = _render_frames(
            base, depth, n_frames, move,
            focus=near_focus if closeup else center_focus,
            zoom_boost=1.16 if closeup else 1.0,
        )
        sub_out = work_dir / f"anim{scene_idx:02d}_sub{i}.mp4"
        _encode_frames(ffmpeg, frames, n_frames, badge_paths[i], sub_out)
        parts.append(sub_out)

    _concat(ffmpeg, parts, out_path, work_dir)
    return {"animated": n_sub}

