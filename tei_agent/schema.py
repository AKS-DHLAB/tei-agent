"""TEI P5 4.12.0 knowledge: element/attribute allow-list (derived from tei_all.rng) and RELAX NG validation."""
from __future__ import annotations

import json
import re
import threading
from functools import lru_cache

from lxml import etree

from .config import DATA_DIR, TEI_VERSION
from .xmlutils import local, parse_fragment

RNG_PATH = DATA_DIR / "schema" / "tei_all.rng"
INDEX_PATH = DATA_DIR / "schema" / "tei_index.json"
RNG_URL = f"https://www.tei-c.org/Vault/P5/{TEI_VERSION}/xml/tei/custom/schema/relaxng/tei_all.rng"

_rng = None
_rng_lock = threading.Lock()


@lru_cache(maxsize=1)
def index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def element_exists(name: str) -> bool:
    return name in index()


def allowed_attributes(name: str) -> list[str]:
    e = index().get(name)
    return sorted(e["attributes"]) if e else []


GLOBAL_ATTRS = {"xml:id", "n", "xml:lang", "rend", "style", "rendition", "xml:base", "xml:space", "ana", "corresp",
                "synch", "sameAs", "copyOf", "next", "prev", "exclude", "select", "cert", "resp", "source", "facs",
                "change"}


def attribute_cheatsheet(elements: list[str]) -> str:
    """Compact per-element list of NON-global attributes, for prompts."""
    lines = []
    for e in sorted(set(elements)):
        if e not in index():
            continue
        specific = [a for a in allowed_attributes(e) if a not in GLOBAL_ATTRS and not a.endswith(("-iso", "-custom"))]
        vals = []
        for a in ("type", "unit", "aloud", "direct", "calendar", "reason", "place"):
            v = index()[e]["attributes"].get(a, {}).get("values")
            if v:
                vals.append(f"{a}∈{{{','.join(v[:12])}}}")
        lines.append(f"- {e}: @{' @'.join(specific) if specific else '(globals only)'}" + (f"  [{'; '.join(vals)}]" if vals else ""))
    return "\n".join(lines)


ISO_DATE_ATTRS = {"when", "from", "to", "notBefore", "notAfter"}
_ISO = re.compile(r"^-?\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01])(T([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$|^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$|^--(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?$|^---(0[1-9]|[12]\d|3[01])$")  # month 01-12, day 01-31, 24h time


def _bad_value(name: str, att: str, val: str) -> bool:
    from .numerals import NUMERIC, NUMERIC_ATTRS
    if att in ISO_DATE_ATTRS:
        v = val.strip()
        return not _ISO.match(v) or v.lstrip("-").startswith("0000")  # XSD has no year zero
    if att in NUMERIC_ATTRS or (att == "value" and name == "num"):
        return not NUMERIC.match(val.strip())
    return False


def _fix_date(v: str) -> str | None:
    """Year-less placeholders → XSD gMonthDay/gMonth (0000-03-23 → --03-23)."""
    m = re.match(r"^0000-(\d{2})(-(\d{2}))?$", v.strip())
    if m:
        return f"--{m.group(1)}-{m.group(3)}" if m.group(3) else f"--{m.group(1)}"
    return None


def quick_check(fragment: str) -> list[str]:
    """Fast deterministic checks: unknown elements, attributes not allowed on an element."""
    try:
        root = parse_fragment(fragment)
    except etree.XMLSyntaxError as e:
        return [f"not well-formed: {e}"]
    issues = []
    idx = index()
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        name = local(el.tag)
        if name == "wrap":
            continue
        if name not in idx:
            issues.append(f"<{name}> is not a TEI element")
            continue
        allowed = idx[name]["attributes"]
        for a in el.attrib:
            q = etree.QName(a)
            an = f"xml:{q.localname}" if q.namespace == "http://www.w3.org/XML/1998/namespace" else q.localname
            if an not in allowed:
                issues.append(f"@{an} is not allowed on <{name}>")
            elif _bad_value(name, an, el.attrib[a]):
                issues.append(f"@{an}=\"{el.attrib[a]}\" on <{name}> has an invalid value (dates: ISO 8601; numbers: Arabic numerals)")
    return sorted(set(issues))


def strip_disallowed(fragment: str) -> tuple[str, list[str]]:
    """Deterministic last-resort repair: drop disallowed attributes and unwrap unknown elements."""
    root = parse_fragment(fragment)
    idx = index()
    log = []
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        name = local(el.tag)
        if name == "wrap":
            continue
        if name not in idx:
            parent = el.getparent()
            log.append(f"unwrapped <{name}>")
            _unwrap(el, parent)
            continue
        for a in list(el.attrib):
            q = etree.QName(a)
            an = f"xml:{q.localname}" if q.namespace == "http://www.w3.org/XML/1998/namespace" else q.localname
            if an in idx[name]["attributes"] and _bad_value(name, an, el.attrib[a]):
                from .numerals import to_arabic
                conv = to_arabic(el.attrib[a]) if an not in ISO_DATE_ATTRS else _fix_date(el.attrib[a])
                if conv is not None:
                    log.append(f"@{an}: \"{el.attrib[a]}\" → \"{conv}\" on <{name}>")
                    el.set(a, conv)
                    continue
            if an not in idx[name]["attributes"] or _bad_value(name, an, el.attrib[a]):
                log.append(f"removed @{an}=\"{el.attrib[a]}\" from <{name}>")
                del el.attrib[a]
    return inner_xml(root), log


def inner_xml(root) -> str:
    """Serialize the content of a wrapper element (text + children incl. tails), namespace-free."""
    from xml.sax.saxutils import escape

    from .xmlutils import strip_ns, to_string
    return escape(root.text or "") + "".join(strip_ns(to_string(c)) for c in root)


def _unwrap(el, parent):
    idx = parent.index(el)
    text = el.text or ""
    if idx == 0:
        parent.text = (parent.text or "") + text
    else:
        prev = parent[idx - 1]
        prev.tail = (prev.tail or "") + text
    for i, ch in enumerate(list(el)):
        parent.insert(idx + i, ch)
    tail = el.tail or ""
    last = parent[idx + len(el) - 1] if len(el) else None
    parent.remove(el)
    if tail:
        if last is not None and last is not el:
            last.tail = (last.tail or "") + tail
        elif idx == 0:
            parent.text = (parent.text or "") + tail
        else:
            parent[idx - 1].tail = (parent[idx - 1].tail or "") + tail


def rng():
    global _rng
    with _rng_lock:
        if _rng is None:
            _rng = etree.RelaxNG(etree.parse(str(RNG_PATH)))
    return _rng


def validate_document(xml: str) -> dict:
    try:
        doc = etree.fromstring(xml.encode("utf-8"), etree.XMLParser(huge_tree=True))
    except etree.XMLSyntaxError as e:
        return {"wellformed": False, "valid": False, "errors": [{"line": getattr(e, "lineno", 0), "message": str(e)}]}
    v = rng()
    ok = v.validate(doc)
    errs = [{"line": e.line, "message": e.message} for e in v.error_log] if not ok else []
    return {"wellformed": True, "valid": ok, "errors": errs[:200], "schema": f"tei_all {TEI_VERSION}"}
