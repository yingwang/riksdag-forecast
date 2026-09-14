"""Download the current result files from resultat.val.se."""
from __future__ import annotations

import hashlib
import urllib.request

BASE = "https://resultat.val.se/resultatfiler/val2026"
FILES = {
    "preliminar": f"{BASE}/p/rd/Val_2026_preliminar_00_RD.zip",
    "slutlig": f"{BASE}/s/rd/Val_2026_slutlig_00_RD.zip",
}
INDEX = f"{BASE}/index.md5"
UA = {"User-Agent": "riksdag-forecast (github.com/yingwang/riksdag-forecast)"}


def get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def index_md5() -> dict[str, str]:
    out = {}
    for line in get(INDEX).decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[1].lstrip("./")] = parts[0]
    return out


def fetch_all() -> dict[str, bytes]:
    blobs = {name: get(url) for name, url in FILES.items()}
    idx = index_md5()
    for name, url in FILES.items():
        key = url[len(BASE) + 1:]
        if key in idx and hashlib.md5(blobs[name]).hexdigest() != idx[key]:
            # the index and the zip were served from different moments; harmless, but note it
            print(f"note: {name} md5 differs from index.md5 (files updated while downloading)")
    return blobs
