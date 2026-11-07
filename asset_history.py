"""
asset_history.py - Makes every video visually unique, across videos AND within one video.

Remembers (in asset_history.json, committed by the workflow like variety_store.json):
  - IDs of stock-video clips already used  -> never reused in a later video
  - Perceptual hashes (dHash) of every scene image already used
    -> a new image that looks like an old one is rejected and regenerated

Usage:
    from asset_history import asset_history
    asset_history.used_clip_ids()            # set of ids to exclude when searching stock footage
    asset_history.is_duplicate_image(path)   # True if it looks like an earlier image
    asset_history.remember_image(path)
    asset_history.remember_clips(ids)
    asset_history.commit()                   # write to disk (call once after a successful render)
"""

import json
from pathlib import Path
from typing import Iterable, List, Optional, Set

from PIL import Image

HISTORY_PATH = Path(__file__).parent.resolve() / "asset_history.json"
MAX_CLIPS = 2000
MAX_HASHES = 1000
DUPLICATE_MAX_HAMMING = 10   # of 64 bits; different pictures normally differ by 20-32


def dhash(path: Path) -> Optional[int]:
    """64-bit difference hash: robust to resizing, recompression and small color shifts."""
    try:
        with Image.open(path) as im:
            g = im.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            px = list(g.getdata())
        bits = 0
        for row in range(8):
            for col in range(8):
                bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
        return bits
    except Exception:
        return None


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


class AssetHistory:
    def __init__(self, path: Path = HISTORY_PATH):
        self.path = path
        self.clip_ids: List[str] = []
        self.hashes: List[str] = []       # hex strings, oldest first
        self._session_hashes: List[int] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.clip_ids = [str(x) for x in data.get("clip_ids", [])]
                self.hashes = [str(x) for x in data.get("image_hashes", [])]
        except Exception as e:
            print(f"   [Asset History Notice] Could not read {self.path.name}: {e}")

    def used_clip_ids(self) -> Set[str]:
        return set(self.clip_ids)

    def is_duplicate_image(self, path) -> bool:
        h = dhash(Path(path))
        if h is None:
            return False
        known = [int(x, 16) for x in self.hashes] + self._session_hashes
        return any(_hamming(h, k) <= DUPLICATE_MAX_HAMMING for k in known)

    def remember_image(self, path) -> None:
        h = dhash(Path(path))
        if h is not None:
            self._session_hashes.append(h)

    def remember_clips(self, ids: Iterable[str]) -> None:
        have = set(self.clip_ids)
        for i in ids:
            if i not in have:
                self.clip_ids.append(i)
                have.add(i)

    def commit(self) -> None:
        for h in self._session_hashes:
            hx = f"{h:016x}"
            if hx not in self.hashes:
                self.hashes.append(hx)
        self._session_hashes = []
        self.clip_ids = self.clip_ids[-MAX_CLIPS:]
        self.hashes = self.hashes[-MAX_HASHES:]
        try:
            self.path.write_text(
                json.dumps({"clip_ids": self.clip_ids, "image_hashes": self.hashes}, indent=1),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"   [Asset History Notice] Could not save {self.path.name}: {e}")


asset_history = AssetHistory()

