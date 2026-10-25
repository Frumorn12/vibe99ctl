"""GIF store and local library for the gallery.

The store searches Tenor's public search pages (Tenor closed its free API in
2026): each page embeds a ``store-cache`` JSON with the first 50 results and
their media URLs. No API key, no account. If Tenor changes that page the
search simply returns nothing; the local library keeps working.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)
TIMEOUT_S = 20
MEDIA_SUFFIXES = {".gif", ".webp", ".png", ".mp4", ".webm", ".mov", ".mkv", ".m4v"}


def _xdg(var: str, default: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / default)


LIBRARY_DIR = _xdg("XDG_DATA_HOME", ".local/share") / "vibe99" / "libreria"
CACHE_DIR = _xdg("XDG_CACHE_HOME", ".cache") / "vibe99"


class StoreError(Exception):
    """The online store could not be reached or parsed."""


@dataclass
class StoreItem:
    id: str
    title: str
    preview_url: str  # small animated GIF for the grid
    full_url: str  # full-size GIF that gets converted and uploaded
    width: int
    height: int
    duration: float

    @property
    def filename(self) -> str:
        slug = Path(urllib.parse.urlparse(self.full_url).path).stem or "gif"
        return f"{slug[:40]}-{self.id}.gif"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.read()
    except OSError as exc:
        host = urllib.parse.urlparse(url).netloc
        raise StoreError(f"Non riesco a raggiungere {host}: {exc}") from exc


def parse_search_page(page: str) -> list[StoreItem]:
    """Extract results from a Tenor search page's embedded ``store-cache`` JSON."""
    m = re.search(r'<script[^>]*id="store-cache"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    try:
        cache = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    items: list[StoreItem] = []
    for entry in cache.get("universal", {}).get("search", {}).values():
        for r in entry.get("results") or []:
            fmts = r.get("media_formats") or {}
            # Transparent variants (stickers) end up on black, like the screen.
            full = fmts.get("gif_transparent") or fmts.get("gif") or fmts.get("mediumgif")
            small = fmts.get("tinygif_transparent") or fmts.get("tinygif") or full
            if not full or not small:
                continue
            w, h = (full.get("dims") or [0, 0])[:2]
            items.append(
                StoreItem(
                    id=str(r.get("id", "")),
                    title=r.get("content_description") or r.get("title") or "",
                    preview_url=small["url"],
                    full_url=full["url"],
                    width=int(w),
                    height=int(h),
                    duration=float(full.get("duration") or 0),
                )
            )
    return items


def search(query: str, *, stickers: bool = False) -> list[StoreItem]:
    """Search the store. ``stickers`` returns transparent GIFs (great on black)."""
    slug = re.sub(r"[^\w]+", "-", query.strip().lower()).strip("-")
    if not slug:
        return []
    kind = "stickers" if stickers else "gifs"
    url = f"https://tenor.com/search/{urllib.parse.quote(slug)}-{kind}"
    return parse_search_page(_get(url).decode("utf-8", errors="replace"))


def fetch(url: str) -> bytes:
    """Download a preview or full GIF, cached on disk by URL."""
    key = re.sub(r"[^\w.-]+", "_", urllib.parse.urlparse(url).path.strip("/"))
    cached = CACHE_DIR / "store" / key
    if cached.exists():
        return cached.read_bytes()
    data = _get(url)
    cached.parent.mkdir(parents=True, exist_ok=True)
    tmp = cached.with_suffix(cached.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(cached)
    return data


def download_full(item: StoreItem) -> Path:
    """Full-size GIF of a store item in the cache (not yet in the library)."""
    fetch(item.full_url)
    key = re.sub(r"[^\w.-]+", "_", urllib.parse.urlparse(item.full_url).path.strip("/"))
    return CACHE_DIR / "store" / key


def save_to_library(source: Path, name: str | None = None) -> Path:
    """Copy a file into the library (no-op if it is already there)."""
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    source = Path(source)
    if source.parent.resolve() == LIBRARY_DIR.resolve():
        return source
    dest = LIBRARY_DIR / (name or source.name)
    if dest.exists() and dest.read_bytes() == source.read_bytes():
        return dest
    stem, n = dest.stem, 2
    while dest.exists():
        dest = LIBRARY_DIR / f"{stem}-{n}{dest.suffix}"
        n += 1
    shutil.copy2(source, dest)
    return dest


def library_items() -> list[Path]:
    """Media files in the library, newest first."""
    if not LIBRARY_DIR.is_dir():
        return []
    files = [p for p in LIBRARY_DIR.iterdir() if p.suffix.lower() in MEDIA_SUFFIXES]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
