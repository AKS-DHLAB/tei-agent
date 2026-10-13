"""Few-shot exemplar store (raw text -> TEI pairs from KNoTE, ELTeC, GerDraCor, TCP, I.Sicily, ParlaMint)."""
from __future__ import annotations

import json
from functools import lru_cache

from .config import DATA_DIR

EX_DIR = DATA_DIR / "exemplars"


@lru_cache(maxsize=1)
def all_exemplars() -> dict[str, dict]:
    out = {}
    for p in sorted(EX_DIR.glob("*.json")):
        if p.name == "index.json":
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["id"]] = d
    return out


def select(genre: str, langs: list[str], preferred: list[str], k: int = 2) -> list[dict]:
    """Pick up to k exemplars: same genre+language first, then same genre, then same language."""
    ex = all_exemplars()
    scored = []
    for eid, d in ex.items():
        s = 0
        if d["genre"] == genre:
            s += 4
        if d["lang"] in langs:
            s += 3
        if eid in preferred:
            s += 2 - preferred.index(eid) * 0.1
        scored.append((s, eid))
    scored.sort(reverse=True)
    return [ex[e] for s, e in scored[:k] if s > 0]


def format_exemplar(d: dict, max_chars: int = 2200) -> str:
    raw = d["raw_input"][:max_chars // 2]
    body = d["tei_body"][:max_chars]
    return (f"### Exemplar `{d['id']}` ({d['lang']}, {d['genre']}; {d['licence']}; {d['citation']})\n"
            f"Raw input (excerpt):\n{raw}\n\nExpert TEI encoding (excerpt, may be truncated):\n{body}\n"
            "NOTE: exemplars show conventions, not an attribute allow-list. Some legacy exemplar attributes "
            "(e.g. said/@mode, measure/@ref, rs/@sex) are INVALID in TEI 4.12 — never copy them.")


def header_example(genre: str, langs: list[str]) -> str:
    s = select(genre, langs, [], k=1)
    return s[0]["tei_header"][:3000] if s else ""
