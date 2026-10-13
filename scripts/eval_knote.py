"""Evaluate automatic tagging against KNoTE gold encodings.

Raw input = source text of each KNoTE body block (paragraphs separated by blank lines).
Spans are compared in whitespace-free character offsets of the source text.

  python scripts/eval_knote.py ../KNoTE/dataset/15_*.xml ... --out examples/live
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tei_agent.config import Settings  # noqa: E402
from tei_agent.pipeline import Session  # noqa: E402
from tei_agent.xmlutils import EDITORIAL, local, norm, parse_fragment  # noqa: E402

TAGS = ["persName", "placeName", "orgName", "said", "date", "time", "measure", "foreign", "rs"]


def spans(xml_blocks: list[str]) -> list[tuple]:
    out, pos = [], 0
    for x in xml_blocks:
        try:
            root = parse_fragment(x)
        except etree.XMLSyntaxError:
            continue

        def visit(node, skip):
            nonlocal pos
            name = local(node.tag)
            parent = node.getparent()
            s = skip or name in EDITORIAL or (name == "expan" and parent is not None and local(parent.tag) == "choice")
            start = pos
            if node.text and not s:
                pos += len(norm(node.text))
            for ch in node:
                if isinstance(ch.tag, str):
                    visit(ch, s)
                if ch.tail and not s:
                    pos += len(norm(ch.tail))
            if name in TAGS and not s:
                out.append((name, start, pos, dict(node.attrib)))

        visit(root, False)
    return out


def text_of(xml_blocks):
    from tei_agent.xmlutils import source_text
    return "".join(norm(source_text(parse_fragment(x))) for x in xml_blocks)


def align(pred, ptext, gtext):
    """Map predicted offsets onto gold text offsets when the two texts differ."""
    if ptext == gtext:
        return pred
    import difflib
    m = {}
    for a, b, size in difflib.SequenceMatcher(None, ptext, gtext, autojunk=False).get_matching_blocks():
        for k in range(size + 1):
            m[a + k] = b + k
    return [(n, m.get(s, -1), m.get(e, -1), at) for n, s, e, at in pred if s in m and e in m]


def prf(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def score(gold, pred):
    res = {}
    for t in TAGS:
        g = [(s, e) for n, s, e, _ in gold if n == t and e > s]
        p = [(s, e) for n, s, e, _ in pred if n == t and e > s]
        exact = len(set(g) & set(p))
        used, partial = set(), 0
        for ps, pe in p:
            for j, (gs, ge) in enumerate(g):
                if j not in used and ps < ge and gs < pe:
                    used.add(j)
                    partial += 1
                    break
        res[t] = {"gold": len(g), "pred": len(p), "exact_PRF": prf(exact, len(p), len(g)), "overlap_PRF": prf(partial, len(p), len(g))}
    return res


def name_of(reg: dict, rid: str) -> set[str]:
    for k in ("persons", "places", "orgs"):
        for e in reg.get(k, []):
            if e["id"] == rid:
                return {e.get("name") or ""} | set(e.get("variants") or [])
    return set()


def who_accuracy(gold, pred, greg, preg):
    gmap = {(s, e): a.get("who", "") for n, s, e, a in gold if n == "said"}
    ok = tot = 0
    for n, s, e, a in pred:
        if n != "said" or (s, e) not in gmap:
            continue
        gw, pw = gmap[(s, e)].lstrip("#"), a.get("who", "").lstrip("#")
        if not gw:
            continue
        tot += 1
        gn, pn = name_of(greg, gw), name_of(preg, pw)
        if gn & pn or any(x and y and (x in y or y in x) for x in gn for y in pn):
            ok += 1
    return {"said_with_gold_who": tot, "speaker_name_match": ok, "acc": round(ok / tot, 3) if tot else None}


def run(path: Path, settings: Settings, outdir: Path, accept: list[str]):
    gold_s = Session.from_tei(path.read_text(encoding="utf-8"), settings)
    gold_blocks = [b["xml"] for b in gold_s.blocks]
    raw = "\n\n".join(b["raw"] for b in gold_s.blocks)
    t0 = time.time()
    s = Session(raw, settings)
    s.analyze()
    s.build_registry()
    s.tag_all()
    stage1 = {"pred": spans([b["xml"] for b in s.blocks])}
    rec = s.recommend_tags()
    if accept:
        s.accept_tags(accept)
    v = s.validate()
    elapsed = time.time() - t0
    gtext, ptext = text_of(gold_blocks), text_of([b["xml"] for b in s.blocks])
    gold = spans(gold_blocks)
    pred = align(spans([b["xml"] for b in s.blocks]), ptext, gtext)
    stage1["pred"] = align(stage1["pred"], ptext, gtext)
    report = {
        "file": path.name, "chars": len(raw), "blocks": len(s.blocks), "genre": s.genre, "langs": s.langs,
        "seconds": round(elapsed, 1), "usage": s.llm.usage.as_dict(),
        "text_identical": ptext == gtext, "block_status": s.summary()["block_status"], "valid": v["valid"], "schema_errors": len(v.get("errors", [])),
        "dangling_refs": v.get("dangling_refs"), "registry": {k: len(x) for k, x in s.registry.items()},
        "stage1_scores": score(gold, stage1["pred"]), "final_scores": score(gold, pred),
        "who": who_accuracy(gold, pred, gold_s.registry, s.registry),
        "recommended": [(t["key"], t.get("priority"), t.get("estimated_count")) for t in rec["tags"]],
        "questions": [q["question"] for q in s.questions][:8], "accepted": accept,
        "errors_sample": [e["message"] for e in v.get("errors", [])[:8]],
    }
    outdir.mkdir(parents=True, exist_ok=True)
    stem = path.stem.split("_")[0]
    (outdir / f"{stem}_pred.xml").write_text(s.to_xml()[0], encoding="utf-8")
    (outdir / f"{stem}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    s.save(outdir / "sessions")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="examples/live")
    ap.add_argument("--accept", default="", help="comma-separated tag keys to accept after first pass (e.g. rs,measure)")
    a = ap.parse_args()
    settings = Settings.from_env()
    accept = [k for k in a.accept.split(",") if k]
    with ThreadPoolExecutor(max_workers=3) as pool:
        reps = list(pool.map(lambda f: run(Path(f), settings, Path(a.out), accept), a.files))
    for r in reps:
        print(json.dumps({k: r[k] for k in ("file", "seconds", "usage", "text_identical", "block_status", "valid", "schema_errors", "who")}, ensure_ascii=False))
        for t, sc in r["final_scores"].items():
            print(f"   {t:10s} gold {sc['gold']:4d} pred {sc['pred']:4d}  exact P/R/F {sc['exact_PRF']}  overlap P/R/F {sc['overlap_PRF']}")


if __name__ == "__main__":
    main()
