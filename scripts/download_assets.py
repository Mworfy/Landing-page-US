#!/usr/bin/env python3
"""
Download CMS assets listed in scripts/assets-to-download.json.
Run after build_cms.py: python3 scripts/download_assets.py
"""

from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "scripts" / "assets-to-download.json"


def download(url: str, dest: Path, retries: int = 3) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True

    ctx = ssl.create_default_context()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AIESEC-US-Migration/1.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                dest.write_bytes(resp.read())
            return True
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  attempt {attempt + 1} failed: {e}")
            time.sleep(1)
    return False


def main() -> None:
    if not MANIFEST.exists():
        print("Run scripts/build_cms.py first to generate the manifest.")
        sys.exit(1)

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assets = data["assets"]
    missing = [a for a in assets if not a.get("exists_locally")]

    print(f"Downloading {len(missing)} assets ({len(assets)} total referenced)...")

    ok = 0
    fail = 0
    for i, asset in enumerate(missing, 1):
        dest = ROOT / asset["local_path"]
        url = asset["url"]
        print(f"[{i}/{len(missing)}] {asset['filename']}")
        if download(url, dest):
            ok += 1
        else:
            fail += 1
            print(f"  FAILED: {url}")

    # Refresh manifest exists_locally flags
    for asset in assets:
        dest = ROOT / asset["local_path"]
        asset["exists_locally"] = dest.exists() and dest.stat().st_size > 0

    data["missing_locally"] = sum(1 for a in assets if not a["exists_locally"])
    MANIFEST.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(f"\nDone: {ok} downloaded, {fail} failed, {data['missing_locally']} still missing")


if __name__ == "__main__":
    main()
