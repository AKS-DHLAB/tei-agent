"""Authority lookups (Wikidata) so header/registry identifiers come from a real source, not the LLM."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

UA = "TEI-Agent/0.1 (digital humanities research tool; https://digitalhumanities.kr/)"


def wikidata_search(name: str, lang: str = "en", limit: int = 5) -> list[dict]:
    q = urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": lang.split("-")[0],
                                "uselang": lang.split("-")[0], "limit": limit, "format": "json", "type": "item"})
    req = urllib.request.Request(f"https://www.wikidata.org/w/api.php?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [{"qid": d["id"], "label": d.get("label"), "description": d.get("description", ""),
             "uri": f"http://www.wikidata.org/entity/{d['id']}"} for d in data.get("search", [])]


def lookup(name: str, lang: str = "en", kind: str = "") -> dict:
    try:
        res = wikidata_search(name, lang)
        if not res and lang != "en":
            res = wikidata_search(name, "en")
        return {"query": name, "kind": kind, "candidates": res,
                "note": "Candidates only — confirm the right QID before adding it to the header."}
    except Exception as e:  # offline / blocked
        return {"query": name, "kind": kind, "candidates": [], "error": f"Wikidata not reachable: {e}"}


AUTH_HOSTS = ("wikidata.org", "viaf.org", "isni.org", "d-nb.info", "orcid.org", "id.loc.gov", "geonames.org")
AUTH_TYPES = {"wikidata", "viaf", "isni", "gnd", "orcid", "lccn", "geonames"}


def strip_identifiers(obj, found: list | None = None, context: str = ""):
    """Remove authority identifiers proposed by the LLM (refs to authority hosts, idno of authority types).
    Returns the cleaned object; removed items are appended to `found` as (context name, value)."""
    found = [] if found is None else found
    if isinstance(obj, dict):
        name = obj.get("name") or obj.get("text") or context
        out = {}
        for k, v in obj.items():
            if k in ("ref", "sameAs", "uri") and isinstance(v, str) and any(h in v for h in AUTH_HOSTS):
                found.append((name, v))
                continue
            if k == "idnos" and isinstance(v, list):
                keep = [i for i in v if not (isinstance(i, dict) and str(i.get("type", "")).lower() in AUTH_TYPES)]
                found += [(name, i.get("value")) for i in v if i not in keep]
                if keep:
                    out[k] = keep
                continue
            if k in ("wikidata", "viaf", "isni"):
                found.append((name, v))
                continue
            out[k] = strip_identifiers(v, found, name)
        return out
    if isinstance(obj, list):
        return [strip_identifiers(x, found, context) for x in obj]
    return obj
