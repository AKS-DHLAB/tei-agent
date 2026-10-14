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


def select(genre: str, langs: list[str], preferred: list[str], k: int = 2, extra: list[dict] | None = None) -> list[dict]:
    """Pick at most two exemplars (0.1.3):
    1. the best exemplar of the SAME GENRE (same language first, then the profile's preferred order);
    2. a second one in the document's LANGUAGE: if slot 1 is already in that language, only another exemplar of the
       same genre and language qualifies; if slot 1 is in another language (or there is none), the best exemplar in
       the document's language of any genre.
    An exemplar that matches neither genre nor language is never used: a wrong example teaches wrong structure.
    `extra` = user-supplied gold entries (marked "user"), preferred over bundled ones."""
    langs = [str(l).split("-")[0] for l in langs]
    pool = list(extra or []) + list(all_exemplars().values())

    def pref(d):
        return 1 - 0.05 * preferred.index(d["id"]) if d["id"] in preferred else 0

    def best(cands, score):
        cands = list(cands)
        return max(cands, key=score) if cands else None

    user = lambda d: 2 if d.get("user") else 0  # noqa: E731
    first = best((d for d in pool if d["genre"] == genre),
                 lambda d: (3 if d["lang"] in langs else 0) + user(d) + pref(d))
    from .profiles import GENRES  # local import: profiles does not depend on exemplars
    if first is None and not GENRES.get(genre, {}).get("exemplar_fallback", True):
        return []  # e.g. dictionaries: a running text in the same language would teach the wrong structure
    if first is not None and first["lang"] in langs:
        second = best((d for d in pool if d is not first and d["genre"] == genre and d["lang"] in langs),
                      lambda d: user(d) + pref(d))
    else:
        second = best((d for d in pool if d is not first and d["lang"] in langs),
                      lambda d: (3 if d["genre"] == genre else 0) + user(d) + pref(d))
    return [d for d in (first, second) if d is not None][:k]


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
