"""Deterministic <teiHeader> (and <standOff>) builder from a metadata dict.

The LLM only proposes *values*; XML is always produced here, so the header is well-formed
and uses only TEI 4.12-valid structures.
"""
from __future__ import annotations

import datetime as dt
import re

from lxml import etree

from .config import APP_NAME, APP_VERSION, TEI_NS, TEI_VERSION

XML_NS = "http://www.w3.org/XML/1998/namespace"
MODEL_NAMES = {"deepseek-flash": "DeepSeek-V4.1-Flash (API model deepseek-flash)",
               "deepseek-v4-pro": "DeepSeek-V4-Pro (API model deepseek-v4-pro)"}


def T(tag: str, text: str | None = None, attrib: dict | None = None, *children) -> etree._Element:
    el = etree.Element(f"{{{TEI_NS}}}{tag}", nsmap={None: TEI_NS})
    for k, v in (attrib or {}).items():
        if v in (None, "", []):
            continue
        if k.startswith("xml:"):
            el.set(f"{{{XML_NS}}}{k[4:]}", str(v))
        else:
            el.set(k, str(v))
    if text:
        el.text = str(text)
    for c in children:
        if c is not None:
            el.append(c)
    return el


def _idnos(parent, idnos):
    for i in idnos or []:
        if i.get("value"):
            parent.append(T("idno", i["value"], {"type": i.get("type")}))


def _names(parent, tag, names):
    for n in names or []:
        if isinstance(n, str):
            n = {"text": n}
        if n.get("text"):
            parent.append(T(tag, n["text"], {"xml:lang": n.get("lang"), "type": n.get("type")}))


def _p(parent, text, tag="p"):
    if text:
        for chunk in [t for t in re.split(r"\n\s*\n", str(text)) if t.strip()]:
            parent.append(T(tag, chunk.strip()))


def _bibl(src: dict) -> etree._Element:
    b = T("bibl", None, {"type": src.get("type"), "xml:lang": src.get("lang")})
    for t in src.get("titles") or ([{"text": src["title"], "level": src.get("level")}] if src.get("title") else []):
        b.append(T("title", t.get("text"), {"level": t.get("level"), "xml:lang": t.get("lang")}))
    for a in src.get("authors") or ([src["author"]] if src.get("author") else []):
        a = {"name": a} if isinstance(a, str) else a
        b.append(T("author", a.get("name"), {"ref": a.get("ref")}))
    for k in ("editor", "publisher", "pubPlace"):
        if src.get(k):
            b.append(T(k, src[k]))
    if src.get("date") or src.get("when"):
        b.append(T("date", src.get("date") or src.get("when"), {"when": src.get("when")}))
    for sc in src.get("biblScope", []):
        b.append(T("biblScope", sc.get("text"), {"unit": sc.get("unit"), "from": sc.get("from"), "to": sc.get("to")}))
    _idnos(b, src.get("idnos"))
    if src.get("note"):
        b.append(T("note", src["note"]))
    return b


def _person(p: dict, tag="person") -> etree._Element:
    attrs = {"xml:id": p.get("id"), "role": p.get("role"), "sex": p.get("sex"), "gender": p.get("gender"),
             "age": p.get("age"), "sameAs": p.get("sameAs")}
    el = T(tag, None, attrs)
    _names(el, "persName", p.get("names") or ([p["name"]] if p.get("name") else []))
    if p.get("birth"):
        el.append(T("birth", p["birth"].get("text"), {"when": p["birth"].get("when"), "where": p["birth"].get("where")}))
    if p.get("death"):
        el.append(T("death", p["death"].get("text"), {"when": p["death"].get("when"), "where": p["death"].get("where")}))
    if p.get("occupation"):
        el.append(T("occupation", p["occupation"]))
    _idnos(el, p.get("idnos"))
    if p.get("note"):
        el.append(T("note", p["note"]))
    return el


def _place(p: dict) -> etree._Element:
    el = T("place", None, {"xml:id": p.get("id"), "type": p.get("type")})
    _names(el, "placeName", p.get("names") or ([p["name"]] if p.get("name") else []))
    if p.get("geo"):
        el.append(T("location", None, {}, T("geo", p["geo"])))
    _idnos(el, p.get("idnos"))
    if p.get("note"):
        el.append(T("note", p["note"]))
    return el


def _org(o: dict) -> etree._Element:
    el = T("org", None, {"xml:id": o.get("id"), "type": o.get("type")})
    _names(el, "orgName", o.get("names") or ([o["name"]] if o.get("name") else []))
    _idnos(el, o.get("idnos"))
    if o.get("note"):
        el.append(T("note", o["note"]))
    return el


def build_header(md: dict, *, tag_counts: dict[str, int] | None = None, genre: str = "generic",
                 registry_location: str = "standOff", model: str = "deepseek-flash", stats: dict | None = None
                 ) -> tuple[etree._Element, etree._Element | None]:
    """Return (teiHeader, standOff or None)."""
    today = dt.date.today().isoformat()
    h = T("teiHeader", None, {"xml:lang": md.get("header_lang")})

    # ---------------- fileDesc
    fd = T("fileDesc")
    ts = T("titleStmt")
    titles = md.get("titles") or [{"text": md.get("title") or "[제목 미상 / Untitled]", "type": "main"}]
    for t in titles:
        ts.append(T("title", t.get("text"), {"type": t.get("type"), "xml:lang": t.get("lang")}))
    for a in md.get("authors", []):
        a = {"name": a} if isinstance(a, str) else a
        el = T("author", None, {"ref": a.get("ref")})
        _names(el, "persName", a.get("names") or [{"text": a.get("name"), "lang": a.get("lang")}])
        _idnos(el, a.get("idnos"))
        ts.append(el)
    for e in md.get("editors", []):
        e = {"name": e} if isinstance(e, str) else e
        ts.append(T("editor", e.get("name"), {"role": e.get("role"), "ref": e.get("ref")}))
    if md.get("funder"):
        ts.append(T("funder", md["funder"]))
    for r in md.get("resp", []):
        rs = T("respStmt", None, {"xml:id": r.get("id")})
        rs.append(T("resp", r.get("resp")))
        nm = T("name", r.get("name"), {"ref": r.get("ref")})
        _idnos(nm, r.get("idnos"))
        rs.append(nm)
        ts.append(rs)
    # machine annotation is always declared
    rs = T("respStmt", None, {"xml:id": "teiagent"})
    rs.append(T("resp", "Automatic TEI encoding (LLM-assisted), subject to human review"))
    rs.append(T("name", f"{APP_NAME} {APP_VERSION} with {MODEL_NAMES.get(model, model)}"))
    ts.append(rs)
    fd.append(ts)

    if md.get("edition"):
        fd.append(T("editionStmt", None, {}, T("edition", md["edition"])))
    if stats:
        ext = T("extent")
        for unit, q in stats.items():
            ext.append(T("measure", f"{q} {unit}", {"unit": unit, "quantity": q}))
        fd.append(ext)

    pub = md.get("publication", {})
    ps = T("publicationStmt")
    ps.append(T("publisher", pub.get("publisher") or "[발행처 미상]"))
    if pub.get("pubPlace"):
        ps.append(T("pubPlace", pub["pubPlace"]))
    ps.append(T("date", pub.get("date") or today, {"when": pub.get("when") or (today if not pub.get("date") else None)}))
    _idnos(ps, pub.get("idnos"))
    lic = md.get("licence") or {}
    if lic.get("target") or lic.get("text") or pub.get("availability"):
        av = T("availability", None, {"status": lic.get("status")})
        if lic.get("target") or lic.get("text"):
            av.append(T("licence", lic.get("text") or lic.get("target"), {"target": lic.get("target")}))
        _p(av, pub.get("availability"))
        ps.append(av)
    fd.append(ps)

    if md.get("series"):
        s = md["series"]
        st = T("seriesStmt")
        st.append(T("title", s.get("title")))
        _idnos(st, s.get("idnos"))
        fd.append(st)
    if md.get("notes"):
        ns = T("notesStmt")
        for n in md["notes"]:
            ns.append(T("note", n))
        fd.append(ns)

    sd = T("sourceDesc")
    sources = md.get("sources") or []
    for src in sources:
        sd.append(_bibl(src))
    if md.get("msDesc"):
        m = md["msDesc"]
        ms = T("msDesc")
        ident = T("msIdentifier")
        for k in ("country", "settlement", "institution", "repository", "collection"):
            if m.get(k):
                ident.append(T(k, m[k]))
        ident.append(T("idno", m.get("idno") or "[청구기호 미상]"))
        ms.append(ident)
        if any(m.get(k) for k in ("material", "dimensions", "condition", "objectType")):
            pd = T("physDesc")
            od = T("objectDesc", None, {"form": m.get("objectType")})
            sdesc = T("supportDesc", None, {"material": m.get("material")})
            sup = T("support")
            _p(sup, " ".join(x for x in (m.get("material"), m.get("dimensions")) if x))
            sdesc.append(sup)
            if m.get("condition"):
                c = T("condition")
                _p(c, m["condition"])
                sdesc.append(c)
            od.append(sdesc)
            pd.append(od)
            ms.append(pd)
        if m.get("origDate") or m.get("origPlace") or m.get("provenance"):
            hist = T("history")
            orig = T("origin")
            if m.get("origPlace"):
                orig.append(T("origPlace", m["origPlace"]))
            if m.get("origDate"):
                orig.append(T("origDate", m["origDate"], {"when": m.get("origWhen"), "notBefore": m.get("notBefore"), "notAfter": m.get("notAfter")}))
            hist.append(orig)
            if m.get("provenance"):
                pv = T("provenance")
                _p(pv, m["provenance"])
                hist.append(pv)
            ms.append(hist)
        sd.append(ms)
    if md.get("recording"):
        r = md["recording"]
        rst = T("recordingStmt")
        rec = T("recording", None, {"type": r.get("type", "audio"), "dur": r.get("dur")})
        if r.get("date") or r.get("place"):
            bc = T("p")
            bc.text = " ".join(x for x in (r.get("date"), r.get("place"), r.get("equipment")) if x)
            rec.append(bc)
        rst.append(rec)
        sd.append(rst)
    if not len(sd):
        sd.append(T("p", md.get("source_note") or "Born-digital transcription supplied by the user; source not yet described."))
    fd.append(sd)
    h.append(fd)

    # ---------------- encodingDesc
    ed = T("encodingDesc")
    pd_ = T("projectDesc")
    _p(pd_, md.get("project_desc") or f"Encoded according to the TEI P5 Guidelines {TEI_VERSION} (tei_all) with LLM-assisted tagging and interactive human refinement.")
    ed.append(pd_)
    if md.get("sampling"):
        sm = T("samplingDecl")
        _p(sm, md["sampling"])
        ed.append(sm)
    edl = md.get("editorial") or {}
    edl = {"normalization": "Original orthography and punctuation preserved; no silent normalisation.",
           "quotation": "Quotation marks retained in the text, outside <said>/<q>.", **edl}
    ed_el = T("editorialDecl")
    for k in ("correction", "normalization", "quotation", "hyphenation", "segmentation", "interpretation"):
        if edl.get(k):
            sub = T(k)
            _p(sub, edl[k])
            ed_el.append(sub)
    ed.append(ed_el)
    if tag_counts:
        td = T("tagsDecl")
        ns = T("namespace", None, {"name": TEI_NS})
        for gi, n in tag_counts.items():
            ns.append(T("tagUsage", None, {"gi": gi, "occurs": n}))
        td.append(ns)
        ed.append(td)
    if md.get("taxonomies"):
        cd = T("classDecl")
        for tx in md["taxonomies"]:
            tax = T("taxonomy", None, {"xml:id": tx.get("id")})
            for c in tx.get("categories", []):
                cat = T("category", None, {"xml:id": c.get("id")})
                cat.append(T("catDesc", c.get("desc")))
                tax.append(cat)
            cd.append(tax)
        ed.append(cd)
    ai = T("appInfo")
    app = T("application", None, {"ident": APP_NAME, "version": APP_VERSION, "when": today, "xml:id": "app-teiagent"})
    app.append(T("label", f"{APP_NAME} (LLM: {MODEL_NAMES.get(model, model)}; schema: tei_all {TEI_VERSION})"))
    ai.append(app)
    ed.append(ai)
    h.append(ed)

    # ---------------- profileDesc
    pr = T("profileDesc")
    if md.get("abstract"):
        ab = T("abstract")
        _p(ab, md["abstract"])
        pr.append(ab)
    cr = md.get("creation") or {}
    if cr:
        c = T("creation")
        if cr.get("date") or cr.get("when"):
            c.append(T("date", cr.get("date") or cr.get("when"), {"when": cr.get("when"), "notBefore": cr.get("notBefore"), "notAfter": cr.get("notAfter")}))
        if cr.get("place"):
            c.append(T("placeName", cr["place"]))
        pr.append(c)
    langs = md.get("languages") or []
    if langs:
        lu = T("langUsage")
        for l in langs:
            lu.append(T("language", l.get("label") or l.get("ident"), {"ident": l.get("ident"), "usage": l.get("usage")}))
        pr.append(lu)
    kws = md.get("keywords") or []
    if kws or md.get("genre_label"):
        tc = T("textClass")
        if md.get("genre_label"):
            kw = T("keywords", None, {"scheme": "#teiagent-genre"})
            kw.append(T("term", md["genre_label"]))
            tc.append(kw)
        for k in kws:
            kw = T("keywords", None, {"scheme": k.get("scheme")})
            for term in k.get("terms", []):
                term = {"text": term} if isinstance(term, str) else term
                kw.append(T("term", term.get("text"), {"ref": term.get("ref"), "xml:lang": term.get("lang")}))
            tc.append(kw)
        pr.append(tc)
    if md.get("corresp"):
        cdsc = T("correspDesc")
        for act in md["corresp"]:
            ca = T("correspAction", None, {"type": act.get("type")})
            if act.get("person"):
                ca.append(T("persName", act["person"], {"ref": act.get("person_ref")}))
            if act.get("place"):
                ca.append(T("placeName", act["place"], {"ref": act.get("place_ref")}))
            if act.get("date") or act.get("when"):
                ca.append(T("date", act.get("date"), {"when": act.get("when")}))
            cdsc.append(ca)
        pr.append(cdsc)
    if md.get("calendars"):
        cal = T("calendarDesc")
        for c in md["calendars"]:
            ce = T("calendar", None, {"xml:id": c.get("id")})
            _p(ce, c.get("desc"))
            cal.append(ce)
        pr.append(cal)
    persons = md.get("persons") or []
    if registry_location == "particDesc" and persons:
        pd2 = T("particDesc")
        lp = T("listPerson")
        for p in persons:
            lp.append(_person(p))
        pd2.append(lp)
        pr.append(pd2)
    if md.get("setting"):
        sdsc = T("settingDesc")
        _p(sdsc, md["setting"] if isinstance(md["setting"], str) else " ".join(str(v) for v in md["setting"].values()))
        pr.append(sdsc)
    if len(pr):
        h.append(pr)

    # ---------------- revisionDesc
    rv = T("revisionDesc")
    for c in md.get("revisions", []):
        rv.append(T("change", c.get("text"), {"when": c.get("when"), "who": c.get("who")}))
    if not len(rv):
        rv.append(T("change", "Automatic TEI encoding generated; awaiting human review.", {"when": today, "who": "#teiagent"}))
    h.append(rv)

    # ---------------- standOff (entity registries not placed in particDesc)
    so = T("standOff")
    if registry_location != "particDesc" and persons:
        lp = T("listPerson")
        for p in persons:
            lp.append(_person(p))
        so.append(lp)
    if md.get("places"):
        lpl = T("listPlace")
        for p in md["places"]:
            lpl.append(_place(p))
        so.append(lpl)
    if md.get("orgs"):
        lo = T("listOrg")
        for o in md["orgs"]:
            lo.append(_org(o))
        so.append(lo)
    if md.get("relations"):
        lr = T("listRelation")
        for r in md["relations"]:
            lr.append(T("relation", None, {"name": r.get("name"), "active": r.get("active"), "passive": r.get("passive"), "mutual": r.get("mutual")}))
        so.append(lr)
    return h, (so if len(so) else None)
