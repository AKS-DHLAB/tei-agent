"""Derive a compact element index (allowed attributes, closed value lists, possible children)
from tei_all.rng (TEI P5 4.12.0). Output: tei_agent/data/schema/tei_index.json

The index is used (1) to inject an attribute allow-list into prompts and
(2) for fast deterministic checks before full RELAX NG validation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from lxml import etree

RNG = "http://relaxng.org/ns/structure/1.0"
A = "http://relaxng.org/ns/compatibility/annotations/1.0"
N = {"r": RNG, "a": A}
HERE = Path(__file__).resolve().parents[1] / "tei_agent" / "data" / "schema"


def main():
    tree = etree.parse(str(HERE / "tei_all.rng"))
    defines = {}
    for d in tree.getroot().iter("{%s}define" % RNG):
        defines.setdefault(d.get("name"), []).append(d)

    element_defs = {}  # define name -> element name
    for name, ds in defines.items():
        for d in ds:
            el = d.find("r:element", N)
            if el is not None and el.get("name"):
                element_defs[name] = el.get("name")

    def walk(node, attrs, children, seen, top=True):
        for ch in node:
            if not isinstance(ch.tag, str):
                continue
            tag = etree.QName(ch).localname
            if tag == "attribute":
                nm = ch.find("r:name", N)
                aname = ch.get("name") or (nm.text if nm is not None else None)
                if aname:
                    vals = [v.text for v in ch.iter("{%s}value" % RNG) if v.text]
                    if vals and any(dt.get("type") == "boolean" for dt in ch.iter("{%s}data" % RNG)):
                        vals = ["true", "false"] + vals  # teidata.xTruthValue = xsd:boolean | unknown | inapplicable
                    doc = ch.find("a:documentation", N)
                    attrs.setdefault(aname, {"values": vals[:40], "doc": (doc.text or "").strip()[:160] if doc is not None else ""})
            elif tag == "element":
                if not top:
                    if ch.get("name"):
                        children.add(ch.get("name"))
                    continue
                walk(ch, attrs, children, seen, top=False)
            elif tag == "ref":
                r = ch.get("name")
                if r in element_defs:
                    children.add(element_defs[r])
                    continue
                if r in seen:
                    continue
                seen.add(r)
                for d in defines.get(r, []):
                    walk(d, attrs, children, seen, top=False)
            else:
                walk(ch, attrs, children, seen, top=False)

    index = {}
    for dname, ename in element_defs.items():
        attrs, children = {}, set()
        for d in defines[dname]:
            el = d.find("r:element", N)
            doc = el.find("a:documentation", N)
            walk(el, attrs, children, set(), top=False)
            text_allowed = any(True for _ in el.iter("{%s}text" % RNG))
        index[ename] = {
            "doc": re.sub(r"\s+", " ", doc.text or "").strip()[:200] if doc is not None else "",
            "attributes": dict(sorted(attrs.items())),
            "children": sorted(children),
            "text": text_allowed,
        }
    out = HERE / "tei_index.json"
    out.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(len(index), "elements ->", out, out.stat().st_size // 1024, "KB")
    for e in ("said", "measure", "rs", "person", "q", "date"):
        print(e, list(index[e]["attributes"])[:60])


if __name__ == "__main__":
    main()
