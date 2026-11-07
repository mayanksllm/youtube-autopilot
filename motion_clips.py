"""
motion_clips.py - Real moving footage for every scene (replaces static images).

Each scene is built from 1-3 short sub-clips (a cut every ~2.5-3.5s) so the
Short feels fast and alive instead of one still image with a slow zoom.

Source cascade per sub-clip:
  Tier 1: Pexels Video API   (PEXELS_API_KEY)   - free, portrait stock footage
  Tier 2: Pixabay Video API  (PIXABAY_API_KEY)  - free, optional
  Tier 3: AI/stock image + strong motion (zoom + pan + handheld drift)
          so the emergency fallback still moves.

Public entry point: build_scene_video(...)
"""

import os
import re
import random
import subprocess
import urllib.parse
from pathlib import Path
from typing import Callable, List, Optional, Set

import requests

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "")

W, H, FPS = 1080, 1920, 30
TARGET_SUBCLIP_SECONDS = 3.0   # average length of one cut
MIN_SUBCLIP_SECONDS = 1.6

_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


# -----------------------------------------------------------------------------
# Stock video search + download
# -----------------------------------------------------------------------------

def _pick_pexels_file(video: dict) -> Optional[dict]:
    """Choose a portrait-friendly mp4 rendition around 720-1440px tall."""
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("link")]
    if not files:
        return None
    good = [f for f in files if (f.get("height") or 0) >= 1280 and (f.get("width") or 0) <= 1600]
    pool = good or [f for f in files if (f.get("height") or 0) >= 720] or files
    # Smallest adequate file keeps downloads fast
    pool.sort(key=lambda f: (f.get("height") or 0) * (f.get("width") or 0))
    return pool[0]


def _search_pexels(query: str) -> List[dict]:
    if not PEXELS_API_KEY:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 15},
            headers={"Authorization": PEXELS_API_KEY},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        out = []
        for v in r.json().get("videos", []):
            f = _pick_pexels_file(v)
            if f and (v.get("duration") or 0) >= 2:
                out.append({"id": f"pexels_{v['id']}", "url": f["link"], "duration": float(v.get("duration") or 0)})
        return out
    except Exception as e:
        print(f"   [Pexels Video Notice] {e}")
        return []


def _search_pixabay(query: str) -> List[dict]:
    if not PIXABAY_API_KEY:
        return []
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": PIXABAY_API_KEY, "q": query, "per_page": 15, "safesearch": "true"},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        out = []
        for h in r.json().get("hits", []):
            vids = h.get("videos", {})
            pick = vids.get("medium") or vids.get("large") or vids.get("small")
            if pick and pick.get("url") and (h.get("duration") or 0) >= 2:
                # Prefer portrait-ish sources; landscape gets center-cropped by the scale/crop filter
                out.append({"id": f"pixabay_{h['id']}", "url": pick["url"], "duration": float(h.get("duration") or 0),
                            "portrait": (pick.get("height") or 0) >= (pick.get("width") or 0)})
        out.sort(key=lambda x: not x.get("portrait", False))
        return out
    except Exception as e:
        print(f"   [Pixabay Video Notice] {e}")
        return []


def _download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 50_000:
        return True
    try:
        with requests.get(url, headers=_UA, stream=True, timeout=40) as r:
            if r.status_code != 200:
                return False
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        return dest.stat().st_size > 50_000
    except Exception as e:
        print(f"   [Clip Download Notice] {e}")
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def fetch_stock_clip(queries: List[str], cache_dir: Path, used_ids: Set[str], need_seconds: float) -> Optional[dict]:
    """Return {'path': Path, 'duration': float, 'id': str} for the first usable, unused clip."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        for search in (_search_pexels, _search_pixabay):
            results = [c for c in search(q) if c["id"] not in used_ids]
            if not results:
                continue
            # Prefer clips long enough for the cut, but shuffle the top picks for variety
            long_enough = [c for c in results if c["duration"] >= need_seconds]
            pool = (long_enough or results)[:6]
            random.shuffle(pool)
            for c in pool:
                dest = cache_dir / f"{c['id']}.mp4"
                if _download(c["url"], dest):
                    used_ids.add(c["id"])
                    return {"path": dest, "duration": c["duration"], "id": c["id"]}
    return None


# -----------------------------------------------------------------------------
# FFmpeg helpers
# -----------------------------------------------------------------------------

def _run(cmd: List[str]) -> None:
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def _encode_args() -> List[str]:
    return ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def _video_subclip(ffmpeg: str, src: Path, src_dur: float, sub_dur: float, badge: Optional[Path], out: Path) -> None:
    """Cut a random window from a stock clip, fill 1080x1920, add a punch-in, overlay caption."""
    max_start = max(0.0, src_dur - sub_dur - 0.15)
    start = random.uniform(0.0, max_start) if max_start > 0 else 0.0
    loop_args = ["-stream_loop", "-1"] if src_dur < sub_dur + 0.15 else []
    # Gentle 1.00 -> 1.06 push-in on top of the real motion keeps every cut energetic
    frames = max(1, int(sub_dur * FPS))
    vf = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},"
        f"scale={int(W*1.08)}:{int(H*1.08)},"
        f"zoompan=z='1+0.06*on/{frames}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[bg]"
    )
    if badge is not None:
        filt = f"{vf};[bg][1:v]overlay=0:0:shortest=1[outv]"
        cmd = [ffmpeg, "-y", *loop_args, "-ss", f"{start:.3f}", "-t", f"{sub_dur:.3f}", "-i", str(src),
               "-loop", "1", "-i", str(badge), "-filter_complex", filt, "-map", "[outv]",
               "-t", f"{sub_dur:.3f}", *_encode_args(), str(out)]
    else:
        filt = f"{vf};[bg]null[outv]"
        cmd = [ffmpeg, "-y", *loop_args, "-ss", f"{start:.3f}", "-t", f"{sub_dur:.3f}", "-i", str(src),
               "-filter_complex", filt, "-map", "[outv]", "-t", f"{sub_dur:.3f}", *_encode_args(), str(out)]
    _run(cmd)


def _image_motion_subclip(ffmpeg: str, img: Path, sub_dur: float, badge: Optional[Path], out: Path, variant: int) -> None:
    """Fallback: still image with real camera motion (zoom + pan + drift), not a bare slow zoom."""
    frames = max(2, int(sub_dur * FPS))
    moves = [
        # zoom in toward center
        ("min(1.0+0.22*on/{f},1.22)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        # pan left -> right while zoomed
        ("1.18", "(iw-iw/zoom)*on/{f}", "ih/2-(ih/zoom/2)+8*sin(on/9)"),
        # zoom out reveal
        ("max(1.22-0.22*on/{f},1.0)", "iw/2-(iw/zoom/2)+10*sin(on/11)", "ih/2-(ih/zoom/2)"),
        # slow rise (pedestal)
        ("1.16", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/{f})"),
    ]
    z, x, y = moves[variant % len(moves)]
    z, x, y = z.format(f=frames), x.format(f=frames), y.format(f=frames)
    pre = f"scale={int(W*1.5)}:{int(H*1.5)}:force_original_aspect_ratio=increase,crop={int(W*1.5)}:{int(H*1.5)}"
    vf = f"[0:v]{pre},zoompan=z='{z}':d={frames}:x='{x}':y='{y}':s={W}x{H}:fps={FPS},setsar=1[bg]"
    if badge is not None:
        filt = f"{vf};[bg][1:v]overlay=0:0:shortest=1[outv]"
        cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(img), "-loop", "1", "-i", str(badge),
               "-filter_complex", filt, "-map", "[outv]", "-t", f"{sub_dur:.3f}", *_encode_args(), str(out)]
    else:
        filt = f"{vf};[bg]null[outv]"
        cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(img), "-filter_complex", filt, "-map", "[outv]",
               "-t", f"{sub_dur:.3f}", *_encode_args(), str(out)]
    _run(cmd)


def _concat(ffmpeg: str, parts: List[Path], out: Path, work_dir: Path) -> None:
    if len(parts) == 1:
        out.write_bytes(parts[0].read_bytes())
        return
    lst = work_dir / f"{out.stem}_concat.txt"
    with open(lst, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{p.resolve().as_posix()}'\n")
    _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])


# -----------------------------------------------------------------------------
# Caption + query helpers
# -----------------------------------------------------------------------------

def split_caption_chunks(narration: str, n_chunks: int, max_words: int = 4) -> List[str]:
    """Split a scene's narration into n caption chunks that follow the voice."""
    words = narration.split()
    if not words:
        return [""] * n_chunks
    n_chunks = max(1, min(n_chunks, len(words)))
    size = max(1, -(-len(words) // n_chunks))  # ceil
    chunks = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
    # Keep each caption short enough to read in ~1s
    chunks = [" ".join(c.split()[:max_words + 2]) for c in chunks]
    while len(chunks) < n_chunks:
        chunks.append(chunks[-1])
    return chunks[:n_chunks]


def key_word(chunk: str) -> str:
    words = re.findall(r"\w+", chunk, flags=re.UNICODE)
    return max(words, key=len) if words else ""


def query_variants(visual_query: str) -> List[str]:
    """'ancient stone temple pillars' -> full query, then shorter fallbacks."""
    vq = re.sub(r"[^\w\s-]", " ", visual_query or "").strip()
    if not vq:
        return []
    words = vq.split()
    variants = [" ".join(words[:4])]
    if len(words) > 2:
        variants.append(" ".join(words[:2]))
        variants.append(" ".join(words[-2:]))
    seen, out = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------

def build_scene_video(
    ffmpeg: str,
    scene_idx: int,
    dur: float,
    visual_query: str,
    image_prompt: str,
    badge_paths: List[Optional[Path]],
    out_path: Path,
    work_dir: Path,
    used_ids: Set[str],
    image_fn: Optional[Callable[[str, int], str]] = None,
) -> dict:
    """
    Build one scene (duration `dur`) out of len(badge_paths) moving sub-clips.
    badge_paths: one caption overlay per sub-clip (use None for no caption).
    Returns {'stock': n_stock_clips, 'image': n_image_fallbacks}.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = work_dir / "stock_cache"
    n_sub = len(badge_paths)
    sub_dur = dur / n_sub
    queries = query_variants(visual_query)

    parts: List[Path] = []
    stats = {"stock": 0, "image": 0}
    fallback_img: Optional[Path] = None

    for i in range(n_sub):
        sub_out = work_dir / f"scene{scene_idx:02d}_sub{i}.mp4"
        badge = badge_paths[i]
        done = False

        if queries:
            # Rotate query so cuts inside one scene are not all the same footage
            ordered = queries[i % len(queries):] + queries[:i % len(queries)]
            clip = fetch_stock_clip(ordered, cache_dir, used_ids, need_seconds=sub_dur)
            if clip:
                try:
                    _video_subclip(ffmpeg, clip["path"], clip["duration"], sub_dur, badge, sub_out)
                    stats["stock"] += 1
                    done = True
                except subprocess.CalledProcessError as e:
                    print(f"   [Stock Clip Render Notice] scene {scene_idx} sub {i}: {(e.stderr or '')[-160:]}")

        if not done:
            if fallback_img is None and image_fn is not None:
                try:
                    fallback_img = Path(image_fn(image_prompt, scene_idx))
                except Exception as e:
                    print(f"   [Image Fallback Notice] {e}")
            if fallback_img is None:
                raise RuntimeError(f"No footage or image available for scene {scene_idx}")
            _image_motion_subclip(ffmpeg, fallback_img, sub_dur, badge, sub_out, variant=scene_idx + i)
            stats["image"] += 1

        parts.append(sub_out)

    _concat(ffmpeg, parts, out_path, work_dir)
    return stats

