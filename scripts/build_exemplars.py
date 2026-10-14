"""Build compact few-shot exemplars (raw text -> TEI) from openly licensed TEI corpora.

Only CC0 / CC BY sources are used (licences verified 2026-10-12):
  KNoTE (CC BY 4.0, Zenodo 10.5281/zenodo.21218299)
  ELTeC-eng / ELTeC-fra (texts PD, markup CC BY 4.0)
  GerDraCor (CC0)
  EEBO-TCP Phase I A00002 (CC0)
  I.Sicily (CC BY 4.0, EpiDoc)
  ParlaMint-GB sample (CC BY 4.0)
Added in 0.1.3 (licences verified 2026-10-14 in each file's <availability> or the repository README):
  DISCO, Diachronic Spanish Sonnet Corpus (CC BY 4.0, README)            poetry, es
  Arthur Schnitzler: Briefwechsel (CC BY 4.0, <licence> in each letter)  correspondence, de
  Kōi Genji monogatari text DB (CC0 1.0, <availability>)                early print, ja
  RusDraCor (CC0 1.0, <licence>)                                         drama, ru
  ELTeC-deu / ELTeC-spa (markup CC BY 4.0, <licence>)                    prose fiction, de / es

Usage:
  python scripts/build_exemplars.py --knote ../KNoTE/dataset --corpora ../corpora
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
NS = {"t": TEI}

SOURCES = [
    # (id, relative path, root key, lang, genre, licence, citation)
    ("knote-dongbaek", "knote:26_Kim Yu-jeong_The Camellias (Dongbaek-kkot).xml", "ko", "prose_fiction",
     "CC BY 4.0", "Kim, G. et al. (2026). KNoTE. JOHD 12(1). doi:10.5334/johd.590"),
    ("knote-unsu", "knote:14_Hyun Jin-geon_A Lucky Day (Unsu Joeun Nal).xml", "ko", "prose_fiction",
     "CC BY 4.0", "Kim, G. et al. (2026). KNoTE. JOHD 12(1). doi:10.5334/johd.590"),
    ("knote-hyeol", "knote:01_Yi In-jik_Tears of Blood (Hyeol-ui Nu).xml", "ko", "prose_fiction",
     "CC BY 4.0", "Kim, G. et al. (2026). KNoTE. JOHD 12(1). doi:10.5334/johd.590"),
    ("eltec-eng-trollope", "corpora:ELTeC-eng/level1/ENG18400_Trollope.xml", "en", "prose_fiction",
     "Text PD; markup CC BY 4.0", "ELTeC-eng, COST Action CA16204 Distant Reading for European Literary History"),
    ("eltec-fra-adam", "corpora:ELTeC-fra/level1/FRA00101_Adam.xml", "fr", "prose_fiction",
     "Text PD; markup CC BY 4.0", "ELTeC-fra, COST Action CA16204 Distant Reading for European Literary History"),
    ("gerdracor-emilia", "corpora:gerdracor/tei/lessing-emilia-galotti.xml", "de", "drama",
     "CC0", "GerDraCor (German Drama Corpus), dracor.org"),
    ("tcp-a00002", "corpora:A00002/A00002.xml", "en", "early_print",
     "CC0", "EEBO-TCP Phase I, A00002"),
    ("isicily-1", "corpora:ISicily/inscriptions/ISic000001.xml", "la", "inscription",
     "CC BY 4.0", "I.Sicily (EpiDoc), Prag et al."),
    ("parlamint-gb", "corpora:ParlaMint/Samples/ParlaMint-GB/2017/ParlaMint-GB_2017-09-07-commons.xml", "en",
     "speech_transcript", "CC BY 4.0", "ParlaMint 5.0, CLARIN ERIC"),
    # 0.1.3: genre and language gaps (poetry, letters, Japanese, Russian, German and Spanish prose)
    ("disco-sonnet", "corpora:disco/tei/15th-17th/per-sonnet/disco018g_0031.xml", "es", "poetry",
     "CC BY 4.0", "Ruiz Fabo, P. et al. DISCO: Diachronic Spanish Sonnet Corpus. github.com/pruizf/disco"),
    ("schnitzler-letter", "corpora:schnitzler-briefe-data/data/editions/L00040.xml", "de", "correspondence",
     "CC BY 4.0", "Arthur Schnitzler: Briefwechsel mit Autorinnen und Autoren (ACDH-CH), L00040"),
    ("koui-genji", "corpora:kouigenjimonogatari/xml/master/05.xml", "ja", "early_print",
     "CC0 1.0", "校異源氏物語テキストDB (Kōi Genji monogatari text DB), vol. 5"),
    ("rusdracor-revizor", "corpora:rusdracor/tei/gogol-revizor.xml", "ru", "drama",
     "CC0 1.0", "RusDraCor (Russian Drama Corpus), dracor.org: Gogol, Revizor"),
    ("eltec-deu", "corpora:ELTeC-deu/level1/DEU001.xml", "de", "prose_fiction",
     "Text PD; markup CC BY 4.0", "ELTeC-deu, COST Action CA16204 Distant Reading for European Literary History"),
    ("eltec-spa", "corpora:ELTeC-spa/level1/SPA1001_GilYCarrasco_ElSenyorDeBembibre.xml", "es", "prose_fiction",
     "Text PD; markup CC BY 4.0", "ELTeC-spa, COST Action CA16204 Distant Reading for European Literary History"),
]

LIST_TAGS = {"listPerson", "listPlace", "listOrg", "listBibl", "listEvent", "listRelation", "listPrefixDef",
             "taxonomy", "tagsDecl", "keywords", "revisionDesc", "langUsage", "classDecl", "editorialDecl"}


def local(tag) -> str:
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def strip_private(root):
    for el in root.iter("{%s}email" % TEI):
        parent = el.getparent()
        if parent is not None:
            # keep tail
            if el.tail:
                prev = el.getprevious()
                if prev is not None:
                    prev.tail = (prev.tail or "") + el.tail
                else:
                    parent.text = (parent.text or "") + el.tail
            parent.remove(el)


def trim_lists(el, cap=5):
    for node in el.iter():
        if local(node.tag) in LIST_TAGS:
            kids = [k for k in node if isinstance(k.tag, str)]
            for k in kids[cap:]:
                node.remove(k)


def trim(el, budget: int) -> int:
    """Keep children of `el` in document order until budget is exhausted. Returns remaining budget."""
    kids = list(el)
    keep_all = True
    for k in kids:
        if not keep_all:
            el.remove(k)
            continue
        size = len(etree.tostring(k, encoding="unicode"))
        if size <= budget:
            budget -= size
        elif len(k) and budget > 300:
            budget = trim(k, budget)
            keep_all = False
        else:
            el.remove(k)
            keep_all = False
    return budget


def plain_text(el) -> str:
    """Approximate the 'raw text' a user would paste: one paragraph per innermost block (a verse line, a speaker
    label, a paragraph), <lb/> as a line break, editorial notes left out."""
    containers = {"lg", "sp", "spGrp", "div", "opener", "closer", "floatingText", "castList", "castGroup", "body", "front", "back"}
    block_tags = {"p", "head", "l", "speaker", "stage", "ab", "u", "item", "dateline", "salute", "signed", "byline",
                  "docTitle", "titlePart", "castItem", "addrLine", "trailer", "epigraph"}

    LB = "\u2028"  # <lb/>; whitespace in the XML source (indentation) is collapsed to one space

    def text_of(node) -> str:
        out = [node.text or ""]
        for ch in node:
            n = local(ch.tag)
            if n == "lb":
                out.append(LB)
            elif n == "space":
                out.append(" ")
            elif n not in ("note", "fw") and isinstance(ch.tag, str):
                out.append(text_of(ch))
            out.append(ch.tail or "")
        return "".join(out)

    blocks = []
    for node in el.iter():
        if local(node.tag) in block_tags and not any(local(a.tag) in block_tags for a in node.iterancestors()):
            lines = [re.sub(r"\s+", " ", ln).strip() for ln in text_of(node).split(LB)]
            txt = "\n".join(ln for ln in lines if ln)
            if txt:
                blocks.append(txt)
    if not blocks:
        blocks = [re.sub(r"\s+", " ", "".join(el.itertext())).strip()]
    return "\n\n".join(blocks)


def drop_external_links(el):
    """Pointers into the source project's own image/API servers cannot be reproduced from raw text:
    drop @facs/@corresp holding URLs and unwrap <seg> left without attributes."""
    for node in el.iter():
        if not isinstance(node.tag, str):
            continue
        for a in ("facs", "corresp"):
            if node.get(a, "").startswith(("http://", "https://")):
                del node.attrib[a]
    for seg in list(el.iter("{%s}seg" % TEI)):
        if not seg.attrib:
            parent, idx = seg.getparent(), seg.getparent().index(seg)
            prev = seg.getprevious()
            if seg.text:
                if prev is not None:
                    prev.tail = (prev.tail or "") + seg.text
                else:
                    parent.text = (parent.text or "") + seg.text
            for k, ch in enumerate(list(seg)):
                parent.insert(idx + k, ch)
            last = parent[idx + len(seg) - 1] if len(seg) else seg.getprevious()
            if seg.tail:
                if last is not None and last is not seg:
                    last.tail = (last.tail or "") + seg.tail
                else:
                    parent.text = (parent.text or "") + seg.tail
            parent.remove(seg)


def element_inventory(root) -> dict:
    inv = {}
    for node in root.iter():
        if isinstance(node.tag, str) and node.tag.startswith("{%s}" % TEI):
            inv[local(node.tag)] = inv.get(local(node.tag), 0) + 1
    return dict(sorted(inv.items(), key=lambda x: -x[1]))


def build(src_path: Path, ex_id, lang, genre, licence, citation, body_budget=3500, header_budget=5000):
    parser = etree.XMLParser(remove_blank_text=True, recover=True, huge_tree=True)
    tree = etree.parse(str(src_path), parser)
    root = tree.getroot()
    strip_private(root)
    header = root.find("t:teiHeader", NS)
    text = root.find("t:text", NS)
    if text is None:
        text = root.find(".//t:text", NS)
    inventory = element_inventory(text) if text is not None else {}
    header_inv = element_inventory(header) if header is not None else {}

    h = copy.deepcopy(header)
    trim_lists(h)
    trim(h, header_budget)

    body = text.find(".//t:body", NS) if text is not None else None
    b = copy.deepcopy(body)
    drop_external_links(b)
    trim(b, body_budget)
    etree.indent(h, space="  ")
    # body is not re-indented: mixed content whitespace must be preserved
    as_str = lambda e: re.sub(r' xmlns(:\w+)?="[^"]+"', "", etree.tostring(e, encoding="unicode"))
    return {
        "id": ex_id,
        "lang": lang,
        "genre": genre,
        "licence": licence,
        "citation": citation,
        "source_file": src_path.name,
        "body_element_inventory": inventory,
        "header_element_inventory": header_inv,
        "raw_input": plain_text(b),
        "tei_body": as_str(b),
        "tei_header": as_str(h),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--knote", default="", help="KNoTE dataset folder (omit to keep the existing KNoTE exemplars)")
    ap.add_argument("--corpora", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "tei_agent" / "data" / "exemplars"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    roots = {"knote": Path(a.knote), "corpora": Path(a.corpora)}
    index = []
    for ex_id, rel, lang, genre, licence, citation in SOURCES:
        key, path = rel.split(":", 1)
        p = roots[key] / path
        if not p.exists() or not str(roots[key]).strip("."):
            # source not available locally: keep the exemplar built earlier, if any
            old = out / f"{ex_id}.json"
            if old.exists():
                ex = json.loads(old.read_text(encoding="utf-8"))
                index.append({k: ex[k] for k in ("id", "lang", "genre", "licence", "citation", "source_file")})
                print(f"{ex_id}: kept existing (source not found: {p})")
            else:
                print("missing", p)
            continue
        ex = build(p, ex_id, lang, genre, licence, citation)
        (out / f"{ex_id}.json").write_text(json.dumps(ex, ensure_ascii=False, indent=1), encoding="utf-8")
        index.append({k: ex[k] for k in ("id", "lang", "genre", "licence", "citation", "source_file")})
        print(f"{ex_id}: raw {len(ex['raw_input'])} chars, body {len(ex['tei_body'])} chars")
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
