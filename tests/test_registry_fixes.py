"""Deterministic registry fixes found on the full 『무정』 run (2026-10-13)."""
from tei_agent.config import Settings
from tei_agent.pipeline import Session


def _session():
    s = Session("1\n\n월향이 웃었다. 병욱이 왔다.\n\n2\n\n계향도 왔다.", Settings())
    s.genre, s.langs = "prose_fiction", ["ko"]
    s.blocks = s.segment()
    s.registry = {"persons": [
        {"id": "PYC", "name": "박영채", "variants": ["영채", "월향", "계월향"]},
        {"id": "KWH", "name": "계월화", "variants": ["월화", "형님"]},
        {"id": "PYU", "name": "병욱", "variants": []},
        {"id": "BYU", "name": "병욱", "variants": ["병옥"]},
        {"id": "KH", "name": "계향", "variants": []}], "places": [], "orgs": []}
    s.blocks[1]["xml"] = ('<p><persName ref="#KWH">월향</persName>이 웃었다. '
                          '<persName ref="#BYU">병욱</persName>이 왔다.</p>')
    s.blocks[3]["xml"] = '<p><persName ref="#PYC">계향</persName>도 왔다.</p>'
    return s


def test_merge_and_ref_fix_and_headings():
    s = _session()
    alias = s._merge_duplicate_names()
    assert alias == {"BYU": "PYU"}
    assert 'ref="#PYU">병욱' in s.blocks[1]["xml"]
    fixes = s.fix_name_refs()
    assert {(f["text"], f["to"]) for f in fixes} == {("월향", "PYC"), ("계향", "KH")}
    s.normalize_structure()
    assert s.blocks[0]["xml"] == "<head>1</head>" and s.blocks[0]["div"]["n"] == "1"
    assert s.blocks[2]["xml"] == "<head>2</head>"


def test_project_rules_in_prompt_header_and_state(tmp_path):
    from tei_agent import prompts as P
    s = _session()
    s.set_project_rules("- 직함형(김장로)은 rs\n<!-- 결정 필요: 인명 한자 -->")
    sys_prompt = s._tag_system()
    assert "9. PROJECT RULES" in sys_prompt and "직함형(김장로)은 rs" in sys_prompt
    assert "결정 필요" not in sys_prompt  # comments are notes for humans, never sent
    assert P.project_rules_block("") == ""
    xml = s.to_xml()[0]
    assert "<interpretation>" in xml and "직함형(김장로)은 rs" in xml and "결정 필요" not in xml
    s.save(tmp_path)
    s2 = Session.load(next(tmp_path.glob("*.json")), Settings())
    assert s2.project_rules == s.project_rules


def test_find_markup_and_rule_tools():
    from tei_agent import tools
    s = _session()
    s.blocks[1]["xml"] = '<p><persName ref="#KJ">김장로</persName>가 왔다. <said who="#PYC">네</said></p>'
    r = tools.dispatch(s, "find_markup", {"element": "persName", "text_regex": "장로$"})
    assert r["count"] == 1 and r["top_texts"][0][0] == "김장로"
    assert tools.dispatch(s, "find_markup", {"element": "said", "missing_attr": "aloud"})["count"] == 1
    tools.dispatch(s, "set_project_rules", {"text": "직함형은 rs"})
    tools.dispatch(s, "set_project_rules", {"text": "생각은 aloud=false"})
    assert s.project_rules == "직함형은 rs\n생각은 aloud=false"
    assert tools.dispatch(s, "get_project_rules", {})["rules"].count("\n") == 1
