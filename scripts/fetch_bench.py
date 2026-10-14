"""Download the generality benchmark (bench/manifest.json) at its pinned commits into bench/data/.

The gold files are not committed to this repository; each one is fetched from its source repository and its
own licence statement is printed so it can be checked.

  python scripts/fetch_bench.py            # all items
  python scripts/fetch_bench.py ko-knote-16 de-drama-kleist
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "bench" / "manifest.json"
DATA = ROOT / "bench" / "data"


def licence_line(xml: str) -> str:
    m = re.search(r"<availability\b.*?</availability>", xml, re.S)
    if not m:
        return "(no <availability> in file; see the repository README)"
    lic = re.search(r'<licence[^>]*target="([^"]+)"', m.group(0))
    txt = re.sub(r"<[^>]+>", " ", m.group(0))
    return (lic.group(1) + " · " if lic else "") + re.sub(r"\s+", " ", txt).strip()[:120]


def main(ids: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles (cp949): print ✓/→ as "?" instead of crashing
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]
    DATA.mkdir(parents=True, exist_ok=True)
    failed = 0
    for it in items:
        if ids and it["id"] not in ids:
            continue
        url = f"https://raw.githubusercontent.com/{it['repo']}/{it['commit']}/{urllib.parse.quote(it['path'])}"
        out = DATA / f"{it['id']}.xml"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "TEI-Agent bench"}), timeout=60) as r:
                data = r.read()
            out.write_bytes(data)
            print(f"{it['id']:28s} {len(data):>9,d} B  manifest: {it['licence']}  file: {licence_line(data.decode('utf-8', 'replace'))}")
        except Exception as e:  # network or missing file
            failed += 1
            print(f"{it['id']:28s} FAILED {e} ({url})", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
