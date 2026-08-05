#!/usr/bin/env python3
"""Replace remaining CDN URLs in HTML with local asset paths using the manifest."""

import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "scripts" / "assets-to-download.json"
CDN_RE = re.compile(
    r"https://(?:cdn\.prod\.website-files\.com|uploads-ssl\.webflow\.com)/[^\s\"'<>]+"
)


def relpath(from_dir: Path, to_file: Path) -> str:
    try:
        rel = to_file.resolve().relative_to(from_dir.resolve())
        return rel.as_posix()
    except ValueError:
        ups = 0
        cur = from_dir.resolve()
        target = to_file.resolve()
        while True:
            try:
                rel = target.relative_to(cur)
                return "/".join([".."] * ups + [rel.as_posix()])
            except ValueError:
                if cur.parent == cur:
                    break
                cur = cur.parent
                ups += 1
        return target.as_posix()


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    url_map = {a["url"]: a["local_path"] for a in data["assets"]}
    for url, local in list(url_map.items()):
        url_map[unquote(url)] = local

    # Map local filenames back to CDN for fixing broken absolute paths from prior run
    local_to_path = {a["filename"]: a["local_path"] for a in data["assets"]}

    updated = 0
    for html_file in sorted(ROOT.rglob("*.html")):
        text = html_file.read_text(encoding="utf-8")
        original = text

        def repl_cdn(match: re.Match) -> str:
            url = match.group(0)
            local = url_map.get(url) or url_map.get(unquote(url))
            if not local:
                return url
            return relpath(html_file.parent, ROOT / local)

        text = CDN_RE.sub(repl_cdn, text)

        # Fix broken absolute paths inserted by earlier buggy run
        root_str = str(ROOT)

        def fix_abs_path(match: re.Match) -> str:
            local = match.group(1)
            return relpath(html_file.parent, ROOT / local)

        text = re.sub(
            rf'(?:\.\./)*{re.escape(root_str)}/(assets/cms/[^"\']+)',
            fix_abs_path,
            text,
        )

        if text != original:
            html_file.write_text(text, encoding="utf-8")
            updated += 1
            print(f"  updated {html_file.relative_to(ROOT)}")

    remaining = set()
    for html_file in ROOT.rglob("*.html"):
        remaining.update(CDN_RE.findall(html_file.read_text(encoding="utf-8", errors="ignore")))

    print(f"\nUpdated {updated} files, {len(remaining)} CDN URLs still remaining")


if __name__ == "__main__":
    main()
