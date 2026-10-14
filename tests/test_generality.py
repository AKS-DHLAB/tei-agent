"""0.1.3: language-neutral rules, exemplar selection, KNoTE preset, generality benchmark harness."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from tei_agent import exemplars as EX
from tei_agent import prompts as P
from tei_agent.config import DATA_DIR, Settings
from tei_agent.llm import MockLLM
from tei_agent.profiles import GENRES, TAGS, tag_rule
from tei_agent.xmlutils import check_preservation, parse_fragment, source_text

ROOT = Path(__file__).resolve().parents[1]
HANGUL = re.compile(r"[가-힣]")


def _ids(genre, langs):
    return [d["id"] for d in EX.select(genre, langs, GENRES[genre]["exemplars"])]


def test_core_rules_are_language_neutral():
    for k, t in TAGS.items():
        assert not HANGUL.search(t["rule"]), f"{k}: Korean text in the general rule"
        assert "KNoTE" not in t["rule"], k
    de = P.tag_system(genre="prose_fiction", tag_keys=list(TAGS), lang_rules="", cheatsheet="", exemplars="",
                      registry="", langs=["de"])
    assert not HANGUL.search(de) and "das Dorf" in de
    ko = tag_rule("measure", ["ko"])
    assert "삼 원" in ko and "two miles" not in ko


def test_exemplar_selection_genre_then_language():
    assert _ids("prose_fiction", ["de"]) == ["eltec-deu"]          # no Korean novel as a German example any more
    assert _ids("prose_fiction", ["ko"]) == ["knote-dongbaek", "knote-hyeol"]
    assert _ids("poetry", ["ko"]) == ["disco-sonnet", "knote-dongbaek"]
    assert _ids("speech_transcript", ["en"]) == ["parlamint-gb"]   # genre label fixed
    assert _ids("dictionary", ["en"]) == []                       # no running text as a dictionary example
    gold = {"id": "gold-x", "user": True, "lang": "ko", "genre": "poetry", "raw_input": "", "tei_body": "", "licence": "", "citation": ""}
    assert [d["id"] for d in EX.select("poetry", ["ko"], [], extra=[gold])][0] == "gold-x"


def test_knote_preset_holds_the_knote_conventions():
    t = (DATA_DIR / "presets" / "knote_conventions.md").read_text(encoding="utf-8")
    for needle in ('xml:lang="zh"', "persName", "type=\"age\"", "aloud", "계절"):
        assert needle in t


def test_source_text_skips_tails_inside_editorial_notes():
    x = '<p>krank<note>Er <rs>J</rs> hatte</note> ist.</p>'
    assert source_text(parse_fragment(x)) == "krank ist."
    assert check_preservation("krank ist.", x)["ok"]


def _identity_responder(messages, json_mode, tools_):
    sys_, user = messages[0]["content"], messages[-1]["content"]
    if "analyse a raw text" in sys_:
        return {"languages": [{"ident": "ko", "usage": 100}], "main_lang": "ko", "genre": "prose_fiction", "notes": ""}
    if "insert TEI markup" in sys_:
        blocks = json.loads(user.split("\n", 1)[1])["blocks"]
        return {"blocks": [{"i": b["i"], "div": None, "xml": f"<p>{escape(b['text'])}</p>"} for b in blocks]}
    return {}


def test_eval_gold_harness_end_to_end(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import eval_gold as G
    gold = (ROOT / "examples" / "live" / "heldout" / "13_pred.xml").read_text(encoding="utf-8")
    item = {"id": "t", "lang": "ko", "genre": "prose_fiction", "max_chars": 1200}
    rep, xml = G.run_item(item, gold, Settings(), presets=["knote_conventions"], accept=[], hints=False,
                          llm_factory=lambda s: MockLLM(s, _identity_responder))
    assert rep["gold_raw_consistent"] and rep["text_identical"]
    assert rep["scores"]["p"]["exact_PRF"][2] > 0.9            # one <p> per paragraph, as in the gold
    assert rep["micro_entities"]["gold"] > 0 and rep["micro_entities"]["pred"] == 0
    assert "<TEI" in xml
    md = G.summary_md([rep])
    assert "| t | ko | prose_fiction | knote_conventions |" in md
    m = json.loads((ROOT / "bench" / "manifest.json").read_text(encoding="utf-8"))
    ex_ids = {d["id"] for d in EX.all_exemplars().values()}
    assert len({i["id"] for i in m["items"]}) == len(m["items"]) and not ex_ids & {i["id"] for i in m["items"]}
