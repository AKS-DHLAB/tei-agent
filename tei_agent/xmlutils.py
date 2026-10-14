"""XML helpers: fragment parsing, source-text extraction, text-preservation check."""
from __future__ import annotations

import difflib
import re
from xml.sax.saxutils import escape

from lxml import etree

from .config import TEI_NS

# Text inside these elements is editorial addition, not source text -> excluded from the preservation check.
EDITORIAL = {"reg", "corr", "ex", "supplied", "note", "gloss", "rt"}
# expan is editorial only when it is the alternative of an abbr inside <choice>
WS = re.compile(r"\s+")
REMOVABLE = re.compile(r"^[\d\s\-–—_.\[\]()|pP·•*]{1,14}$")  # page numbers, soft hyphens, separators


def local(tag) -> str:
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def parse_fragment(xml: str) -> etree._Element:
    """Parse a TEI fragment (may contain several top-level elements). Raises XMLSyntaxError."""
    wrapped = f'<wrap xmlns="{TEI_NS}" xmlns:xml="http://www.w3.org/XML/1998/namespace">{xml}</wrap>'
    return etree.fromstring(wrapped.encode("utf-8"), etree.XMLParser(remove_blank_text=False, huge_tree=True))


def source_text(el: etree._Element) -> str:
    """Text that should correspond to the original source (editorial additions skipped)."""
    out: list[str] = []

    def rec(node, skip=False):
        name = local(node.tag)
        parent = node.getparent()
        is_edit = name in EDITORIAL or (name == "expan" and parent is not None and local(parent.tag) == "choice")
        s = skip or is_edit
        if node.text and not s:
            out.append(node.text)
        for ch in node:
            if isinstance(ch.tag, str):
                rec(ch, s)
            if ch.tail and not s:  # a child's tail belongs to this node: skipped when this node is editorial
                out.append(ch.tail)

    rec(el)
    return "".join(out)


def norm(s: str) -> str:
    return WS.sub("", s)


def check_preservation(raw: str, xml_fragment: str, allow_removals: bool = False) -> dict:
    """Return {"ok": bool, "removed": [...], "problems": [...]}.
    Only deletions of page-number-like snippets are tolerated; any insertion/substitution fails."""
    try:
        frag = parse_fragment(xml_fragment)
    except etree.XMLSyntaxError as e:
        return {"ok": False, "problems": [f"XML not well-formed: {e}"], "removed": []}
    a, b = norm(raw), norm(source_text(frag))
    if a == b:
        return {"ok": True, "removed": [], "problems": []}
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    removed, problems = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        if op == "delete" and allow_removals and REMOVABLE.match(a[i1:i2]):
            removed.append(a[i1:i2])
            continue
        ctx = a[max(0, i1 - 12):i2 + 12]
        problems.append(f"{op}: source '{a[i1:i2]}' -> output '{b[j1:j2]}' (context: …{ctx}…)")
        if len(problems) >= 5:
            break
    return {"ok": not problems, "removed": removed, "problems": problems}


def plain_p(raw: str, tag: str = "p") -> str:
    return f"<{tag}>{escape(raw.strip())}</{tag}>"


def strip_ns(s: str) -> str:
    return re.sub(r'\s+xmlns(:\w+)?="[^"]+"', "", s)


def to_string(el, pretty: bool = False) -> str:
    return etree.tostring(el, encoding="unicode", pretty_print=pretty)


def element_counts(xml_fragments: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for x in xml_fragments:
        try:
            f = parse_fragment(x)
        except etree.XMLSyntaxError:
            continue
        for n in f.iter():
            if isinstance(n.tag, str) and local(n.tag) != "wrap":
                counts[local(n.tag)] = counts.get(local(n.tag), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def refs_in(xml_fragments: list[str]) -> set[str]:
    out = set()
    for x in xml_fragments:
        for m in re.finditer(r'\b(?:ref|who|corresp|sameAs)="([^"]+)"', x):
            for tok in m.group(1).split():
                if tok.startswith("#"):
                    out.add(tok[1:])
    return out
