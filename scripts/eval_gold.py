"""Generality benchmark: tag held-out gold TEI files of any language/genre and score the result (0.1.3).

Generalises scripts/eval_knote.py (KNoTE only). For each gold file:
  raw text  = the gold body with tags removed (verse lines, speaker labels and <lb/> kept as line breaks,
              editorial additions such as <note>/<ex>/<supplied> left out), cut at --max-chars;
  pipeline  = analyse → registry → tag_all → recommend (→ accept) → validate, with the item's presets;
  scores    = per element, exact and overlap P/R/F1 over whitespace-free character offsets; micro averages for
              entity/speech/time markup and for structure; speaker (@who) agreement; text preservation; validity.

  python scripts/fetch_bench.py
  python scripts/eval_gold.py --manifest bench/manifest.json                 # all items, presets from manifest
  python scripts/eval_gold.py --manifest bench/manifest.json --no-presets    # neutral rules only
  python scripts/eval_gold.py --manifest bench/manifest.json --ids ko-knote-16 --accept rs,measure
  python scripts/eval_gold.py --package-root ../tei-agent-0.1.2 --no-presets --out bench/results/v012   # older version
  python scripts/compare_runs.py bench/results/v012 bench/results/<run>
Results: bench/results/<run>/<id>_pred.xml, <id>_report.json, summary.json, summary.md
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

ROOT = Path(__file__).resolve().parents[1]
# --package-root PATH: score another checkout of tei_agent (e.g. v0.1.2) with this same harness and benchmark
_pr = sys.argv.index("--package-root") if "--package-root" in sys.argv else -1
sys.path.insert(0, str(Path(sys.argv[_pr + 1]).resolve() if _pr >= 0 else ROOT))
from tei_agent.config import DATA_DIR, Settings  # noqa: E402
from tei_agent.pipeline import Session  # noqa: E402
from tei_agent.xmlutils import EDITORIAL, local, norm, parse_fragment, source_text  # noqa: E402

TEI = "http://www.tei-c.org/ns/1.0"
ENTITY = ["persName", "placeName", "orgName", "rs", "said", "q", "date", "time", "measure", "num", "foreign", "term",
          "title", "roleName", "name"]
STRUCTURE = ["head", "p", "l", "lg", "sp", "speaker", "stage", "opener", "closer", "salute", "dateline", "signed",
             "address", "addrLine", "ab"]
INNER_BLOCKS = {"p", "head", "l", "speaker", "stage", "ab", "u", "item", "dateline", "salute", "signed", "byline",
                "addrLine", "trailer", "castItem", "label"}
SKIP_RAW = EDITORIAL | {"fw", "expan"}
LB = " "


# ------------------------------------------------------------------ gold → blocks and raw text
def gold_blocks(xml_text: str, container: str = "") -> list[str]:
    """Top-level blocks of the gold body (divisions are walked into), as namespace-free XML strings."""
    root = etree.fromstring(xml_text.encode("utf-8"), etree.XMLParser(huge_tree=True, remove_comments=True))
    body = root.find(f".//{{{TEI}}}text/{{{TEI}}}body")
    if body is None:
        body = root.find(f".//{{{TEI}}}body")
    if container:  # e.g. "div[@type='edition']" (EpiDoc): only that part of the body is the source text
        hits = body.xpath(".//t:" + container, namespaces={"t": TEI})
        body = hits[0] if hits else body
    out = []

    def walk(el):
        for ch in el:
            if not isinstance(ch.tag, str):
                continue
            if local(ch.tag) in ("div", "div1", "div2", "div3", "group", "text", "body"):
                walk(ch)
            elif local(ch.tag) not in ("note", "fw", "pb", "milestone", "cb"):
                ch.tail = None
                out.append(re.sub(r' xmlns(:\w+)?="[^"]+"', "", etree.tostring(ch, encoding="unicode")))
    walk(body)
    return out


def raw_of_block(xml: str) -> str:
    """The text a user would paste for one block: inner blocks (verse lines, speaker label, paragraph) on their own
    lines, <lb/> as a line break, editorial additions left out."""
    el = parse_fragment(xml)

    def text_of(node, skip=False) -> str:
        out = [] if skip else [node.text or ""]
        for ch in node:
            if not isinstance(ch.tag, str):
                out.append("" if skip else ch.tail or "")
                continue
            n = local(ch.tag)
            ed = skip or n in SKIP_RAW and not (n == "expan" and local(ch.getparent().tag) != "choice")
            if n == "lb":
                out.append(LB)
            elif n == "space":
                out.append(" ")
            else:
                inner = text_of(ch, ed)
                out.append(LB + inner + LB if n in INNER_BLOCKS else inner)
            if not skip:
                out.append(ch.tail or "")
        return "".join(out)

    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text_of(el).split(LB)]
    return "\n".join(ln for ln in lines if ln)


# ------------------------------------------------------------------ scoring (same method as eval_knote.py)
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
            if not s and node is not root:
                out.append((name, start, pos, dict(node.attrib)))

        visit(root, False)
    return out


def text_of(xml_blocks: list[str]) -> str:
    return "".join(norm(source_text(parse_fragment(x))) for x in xml_blocks)


def align(pred, ptext, gtext):
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
    return round(p, 3), round(r, 3), round(2 * p * r / (p + r), 3) if p + r else 0.0


def score(gold, pred, tags):
    res = {}
    for t in tags:
        g = [(s, e) for n, s, e, _ in gold if n == t and e > s]
        p = [(s, e) for n, s, e, _ in pred if n == t and e > s]
        if not g and not p:
            continue
        remaining = {}
        for x in g:
            remaining[x] = remaining.get(x, 0) + 1
        exact = 0
        for x in p:
            if remaining.get(x):
                remaining[x] -= 1
                exact += 1
        used, overlap = set(), 0
        for ps, pe in p:
            for j, (gs, ge) in enumerate(g):
                if j not in used and ps < ge and gs < pe:
                    used.add(j)
                    overlap += 1
                    break
        res[t] = {"gold": len(g), "pred": len(p), "exact": exact, "overlap": overlap,
                  "exact_PRF": prf(exact, len(p), len(g)), "overlap_PRF": prf(overlap, len(p), len(g))}
    return res


def micro(scores, tags):
    rows = [scores[t] for t in tags if t in scores]
    G, P = sum(r["gold"] for r in rows), sum(r["pred"] for r in rows)
    return {"gold": G, "pred": P, "exact_PRF": prf(sum(r["exact"] for r in rows), P, G),
            "overlap_PRF": prf(sum(r["overlap"] for r in rows), P, G)}


def who_accuracy(gold, pred, greg, preg):
    def names(reg, rid):
        for k in ("persons", "places", "orgs"):
            for e in (reg or {}).get(k, []):
                if e["id"] == rid:
                    return {e.get("name") or ""} | set(e.get("variants") or [])
        return {rid}
    gmap = {(s, e): a.get("who", "") for n, s, e, a in gold if n in ("said", "sp")}
    ok = tot = 0
    for n, s, e, a in pred:
        if n not in ("said", "sp") or (s, e) not in gmap:
            continue
        gw, pw = gmap[(s, e)].split(" ")[0].lstrip("#"), a.get("who", "").split(" ")[0].lstrip("#")
        if not gw:
            continue
        tot += 1
        gn, pn = names(greg, gw), names(preg, pw)
        if gn & pn or any(x and y and (x in y or y in x) for x in gn for y in pn):
            ok += 1
    return {"compared": tot, "match": ok, "acc": round(ok / tot, 3) if tot else None}


# ------------------------------------------------------------------ one item
def load_presets(names: list[str]) -> str:
    missing = [n for n in names if not (DATA_DIR / "presets" / f"{n}.md").exists()]
    if missing:  # e.g. scoring v0.1.2, which has no knote_conventions preset: run it with --no-presets
        raise FileNotFoundError(f"preset(s) {missing} not in {DATA_DIR / 'presets'}")
    return "\n\n".join((DATA_DIR / "presets" / f"{n}.md").read_text(encoding="utf-8") for n in names)


def run_item(item: dict, xml_text: str, settings: Settings, *, presets: list[str], accept: list[str], hints: bool,
             llm_factory=None, max_chars: int | None = None) -> tuple[dict, str]:
    blocks = gold_blocks(xml_text, item.get("container", ""))
    limit = max_chars or item.get("max_chars") or 10 ** 9
    gb, raws, n = [], [], 0
    for x in blocks:
        r = raw_of_block(x)
        if not r:
            continue
        gb.append(x)
        raws.append(r)
        n += len(r)
        if n >= limit:
            break
    raw = "\n\n".join(raws)
    gold_reg = Session.from_tei(xml_text, settings).registry
    t0 = time.time()
    s = Session(raw, settings, llm_factory(settings) if llm_factory else None)
    if presets:
        s.set_project_rules(load_presets(presets))
    s.analyze({"genre": item.get("genre"), "lang": item.get("lang")} if hints else {})
    s.build_registry()
    s.tag_all()
    s.recommend_tags()
    if accept:
        s.accept_tags(accept)
    v = s.validate()
    pred_blocks = [b["xml"] for b in s.blocks]
    gtext, ptext = text_of(gb), text_of(pred_blocks)
    gold, pred = spans(gb), align(spans(pred_blocks), ptext, gtext)
    tags = [t for t in ENTITY + STRUCTURE if any(x[0] == t for x in gold + pred)]
    sc = score(gold, pred, tags)
    report = {
        "id": item["id"], "lang": item.get("lang"), "genre": item.get("genre"), "presets": presets, "accepted": accept,
        "hints": hints, "chars": len(raw), "gold_blocks": len(gb), "seconds": round(time.time() - t0, 1),
        "detected": {"genre": s.genre, "langs": s.langs},
        "gold_raw_consistent": norm(raw) == gtext,
        "text_identical": ptext == gtext, "block_status": s.summary()["block_status"],
        "valid": v.get("valid"), "schema_errors": len(v.get("errors", [])), "errors_sample": [e["message"] for e in v.get("errors", [])[:5]],
        "scores": sc, "micro_entities": micro(sc, ENTITY), "micro_structure": micro(sc, STRUCTURE),
        "who": who_accuracy(gold, pred, gold_reg, s.registry), "usage": s.llm.usage.as_dict(),
    }
    return report, s.to_xml()[0]


# ------------------------------------------------------------------ summary
def summary_md(reports: list[dict]) -> str:
    f = lambda t: "–" if not t or not t.get("gold") else f"{t['exact_PRF'][2]:.2f} / {t['overlap_PRF'][2]:.2f}"  # noqa: E731
    lines = ["| item | lang | genre | presets | detected | text kept | valid | entities F1 exact / overlap | structure F1 exact / overlap | @who | s |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in reports:
        if "error" in r:
            lines.append(f"| {r['id']} | | | | | | | error: {r['error'][:60]} | | | |")
            continue
        det = f"{r['detected']['genre']}/{','.join(r['detected']['langs'][:2])}"
        lines.append(f"| {r['id']} | {r['lang']} | {r['genre']} | {', '.join(r['presets']) or '–'} | {det} | "
                     f"{'✓' if r['text_identical'] else '✗'} | {'✓' if r['valid'] else '✗'} | {f(r['micro_entities'])} | "
                     f"{f(r['micro_structure'])} | {r['who']['acc'] if r['who']['acc'] is not None else '–'} | {r['seconds']} |")
    ok = [r for r in reports if "error" not in r]
    if ok:
        lines.append("")
        lines.append(f"Text preserved {sum(r['text_identical'] for r in ok)}/{len(ok)} · valid {sum(bool(r['valid']) for r in ok)}/{len(ok)} · "
                     f"genre detected {sum(r['detected']['genre'] == r['genre'] for r in ok)}/{len(ok)}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(ROOT / "bench" / "manifest.json"))
    ap.add_argument("--data", default=str(ROOT / "bench" / "data"))
    ap.add_argument("--ids", default="", help="comma-separated item ids (default: all)")
    ap.add_argument("--out", default="", help="output folder (default bench/results/<timestamp>)")
    ap.add_argument("--no-presets", action="store_true", help="ignore the presets listed in the manifest")
    ap.add_argument("--preset", action="append", default=[], help="extra preset for every item")
    ap.add_argument("--accept", default="", help="tag keys to accept after the first pass, e.g. rs,measure")
    ap.add_argument("--hints", action="store_true", help="pass the item's genre and language to the analysis")
    ap.add_argument("--max-chars", type=int, default=0, help="override the per-item text length")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--package-root", default="", help="import tei_agent from this checkout instead (compare versions)")
    a = ap.parse_args()
    items = json.loads(Path(a.manifest).read_text(encoding="utf-8"))["items"]
    if a.ids:
        want = set(a.ids.split(","))
        items = [i for i in items if i["id"] in want]
    out = Path(a.out or ROOT / "bench" / "results" / time.strftime("%Y%m%d-%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_env()
    accept = [k for k in a.accept.split(",") if k]

    def one(item):
        path = Path(a.data) / f"{item['id']}.xml"
        if not path.exists():
            return {"id": item["id"], "error": f"missing {path} (run scripts/fetch_bench.py)"}
        presets = ([] if a.no_presets else item.get("presets", [])) + a.preset
        try:
            rep, xml = run_item(item, path.read_text(encoding="utf-8"), settings, presets=presets, accept=accept,
                                hints=a.hints, max_chars=a.max_chars or None)
        except Exception as e:  # keep the other items running
            return {"id": item["id"], "error": f"{type(e).__name__}: {e}"}
        (out / f"{item['id']}_pred.xml").write_text(xml, encoding="utf-8")
        (out / f"{item['id']}_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{item['id']}: text {'ok' if rep['text_identical'] else 'CHANGED'}, valid {rep['valid']}, "
              f"entities {rep['micro_entities']['exact_PRF']}, structure {rep['micro_structure']['exact_PRF']}", file=sys.stderr)
        return rep

    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as pool:
        reports = list(pool.map(one, items))
    (out / "summary.json").write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")
    md = summary_md(reports)
    (out / "summary.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"→ {out}")


if __name__ == "__main__":
    main()
