"""End-to-end tests with a mock DeepSeek (no network). Run: pytest -q"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tei_agent import tools
from tei_agent.config import Settings
from tei_agent.llm import MockLLM
from tei_agent.pipeline import Session
from tei_agent.profiles import GENRES, TAGS
from tei_agent.schema import index, quick_check, validate_document
from tei_agent.xmlutils import check_preservation

KO_TEXT = """운수 좋은 날

현진건

새침하게 흐린 품이 눈이 올 듯하더니 눈은 아니 오고 얼다가 만 비가 추적추적 내리는 날이었다.

이날이야말로 동소문 안에서 인력거꾼 노릇을 하는 김첨지에게는 오래간만에도 닥친 운수 좋은 날이었다. 문안에 들어간답시는 앞집 마나님을 전찻길까지 모셔다 드린 것을 비롯으로 행여나 손님이 있을까 하고 정류장에서 어정어정하며 내리는 사람 하나하나에게 거의 비는 듯한 눈결을 보내고 있다가 마침내 교원인 듯한 양복장이를 동광학교(東光學校)까지 태워다 주기로 되었다.

첫 번에 삼십 전, 둘째 번에 오십 전 - 아침 댓바람에 그리 흉하지 않은 일이었다.

"남대문 정거장까지 얼마요?"

하고 학생은 물었다."""

REG = {"persons": [{"id": "KCJ", "name": "김첨지", "variants": ["인력거꾼"], "sex": "M", "role": "protagonist"},
                   {"id": "STU", "name": "학생", "variants": []}],
       "places": [{"id": "DSM", "name": "동소문"}, {"id": "NDM", "name": "남대문 정거장"}],
       "orgs": [{"id": "DKS", "name": "동광학교"}]}


def tag_block(i: int, raw: str, sabotage: bool) -> dict:
    x = raw.replace("&", "&amp;").replace("<", "&lt;")
    if i == 0:
        return {"i": i, "div": {"type": "chapter", "n": "1", "level": 1}, "xml": f"<head>{x}</head>"}
    if i == 1:
        return {"i": i, "div": None, "xml": f"<p><persName>{x}</persName></p>"}
    x = re.sub(r'"([^"]+)"', r'"<said who="#STU" mode="direct">\1</said>"', x)  # invalid @mode on purpose
    x = x.replace("김첨지", '<persName ref="#KCJ">김첨지</persName>')
    x = x.replace("동소문", '<placeName ref="#DSM">동소문</placeName>')
    x = x.replace("남대문 정거장", '<placeName ref="#NDM">남대문 정거장</placeName>')
    x = x.replace("동광학교", '<orgName ref="#DKS">동광학교</orgName>')
    x = x.replace("(東光學校)", '(<foreign xml:lang="ko-Hani">東光學校</foreign>)')
    if sabotage and "삼십 전" in x:
        x = x.replace("삼십 전", "30전")  # model 'normalises' text -> must be rejected
    if "학생은" in x:
        x = x.replace("학생", '<rs type="person" ref="#STU">학생</rs>')
    return {"i": i, "div": None, "xml": f"<p>{x}</p>"}


def responder_factory(sabotage=True):
    state = {"repair_calls": 0}

    def responder(messages, json_mode, tools_):
        sys_ = messages[0]["content"]
        user = messages[-1]["content"]
        if tools_:  # agent chat
            if messages[-1]["role"] == "user":
                return {"role": "assistant", "content": "", "reasoning_content": "check status first",
                        "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_status", "arguments": "{}"}}]}
            return {"role": "assistant", "content": "현재 장르는 산문 서사이며 persName 등이 태깅되어 있습니다."}
        if "analyse a raw text" in sys_:
            return {"languages": [{"ident": "ko", "label": "한국어", "usage": 97}, {"ident": "ko-Hani", "label": "한자", "usage": 3}],
                    "main_lang": "ko", "genre": "prose_fiction", "genre_confidence": 0.95, "period": "1924",
                    "title": "운수 좋은 날", "author": "현진건", "structure": {"has_dialogue": True}, "notes": "1920년대 단편소설."}
        if "entity registry" in sys_:
            return REG
        if "REVISION MODE" in sys_:
            blocks = json.loads(user.split("\n", 1)[1])["blocks"]
            out = []
            for b in blocks:
                x = b["xml"]
                x = re.sub(r"(삼십|오십) 전", lambda m: f'<measure type="currency" unit="jeon">{m.group(0)}</measure>', x)
                out.append({"i": b["i"], "xml": x})
            return {"blocks": out, "new_entities": [], "uncertain": []}
        if "insert TEI markup" in sys_:
            if "previous output for these blocks had problems" in user:
                state["repair_calls"] += 1
                return {"blocks": []}  # pretend the repair failed -> deterministic fallbacks must kick in
            payload = json.loads(user.split("\n", 1)[1])
            return {"blocks": [tag_block(b["i"], b["text"], sabotage) for b in payload["blocks"]],
                    "new_entities": [], "uncertain": [{"i": 5, "text": "학생", "question": "'학생'을 독립 인물로 등록할까요?"}]}
        if "Recommend ADDITIONAL" in sys_:
            return {"tags": [{"key": "measure", "why": "화폐 단위(전)가 반복되어 경제사적 분석에 유용합니다.", "examples": ["삼십 전"], "estimated_count": 2, "priority": 1},
                             {"key": "bogus", "why": "x"}],
                    "questions": [{"id": "q1", "question": "대명사 공지시(rs)도 태깅할까요?", "options": ["예", "주요 인물만", "아니오"]}]}
        if "enrich the TEI header" in sys_:
            return {"suggestions": [{"key": "creation", "patch": {"creation": {"date": "1924", "when": "1924"}}, "evidence": "개벽 1924년 6월호", "confidence": "high", "why": "초출 연도"}],
                    "to_lookup": [{"kind": "author", "name": "현진건", "lang": "ko"}], "questions": []}
        if "executable plan" in sys_:
            return {"kind": "retag", "tag_keys": ["measure"], "scope": "search", "search": ["전"],
                    "retag_instruction": "Tag currency amounts with measure.", "metadata_patch": {"licence": {"target": "https://creativecommons.org/licenses/by/4.0/", "text": "CC BY 4.0"}},
                    "entity_ops": [], "reply": "화폐 단위를 measure로 태깅하고 라이선스를 넣었습니다."}
        return {}
    return responder, state


@pytest.fixture()
def session(tmp_path):
    s = Settings()
    s.api_key = "test"
    s.sessions_dir = tmp_path
    s.max_workers = 2
    s.chunk_chars = 300
    responder, state = responder_factory()
    ses = Session(KO_TEXT, s, MockLLM(s, responder))
    ses._mock_state = state
    return ses


def test_profiles_use_only_valid_tei_elements():
    idx = index()
    for k, t in TAGS.items():
        for e in t["elements"]:
            assert e in idx, f"{k}: <{e}> not in TEI 4.12"
    for g in GENRES.values():
        assert all(k in TAGS for k in g["core"] + g["optional"])


def test_preservation_check():
    assert check_preservation("김첨지는 갔다.", '<persName ref="#K">김첨지</persName>는 갔다.')["ok"]
    assert not check_preservation("삼십 전", "30전")["ok"]
    assert check_preservation("a\n12\nb", 'a<pb n="12"/>b', allow_removals=True)["ok"]  # only when page numbers exist
    assert not check_preservation("1", '<pb n="1"/>')["ok"]  # section number must not vanish
    assert check_preservation("Dr Smith", "<choice><abbr>Dr</abbr><expan>Doctor</expan></choice> Smith")["ok"]


def test_quick_check_catches_legacy_knote_attributes():
    issues = quick_check('<said who="#A" mode="thought">x</said><measure ref="#B">3</measure>')
    assert "@mode is not allowed on <said>" in issues and "@ref is not allowed on <measure>" in issues


def test_full_workflow(session):
    s = session
    a = s.analyze()
    assert s.genre == "prose_fiction" and s.langs == ["ko", "ko-Hani"]
    assert len(s.blocks) == 7
    s.build_registry()
    r = s.tag_all()
    # sabotaged block (삼십 전 → 30전) must have been rejected, not silently accepted
    sab = [b for b in s.blocks if "삼십 전" in b["raw"]][0]
    assert sab["status"] == "fallback" and "30전" not in sab["xml"]
    # invalid said/@mode removed deterministically, @who kept
    said_blk = [b for b in s.blocks if "얼마요" in b["raw"]][0]
    assert 'mode=' not in said_blk["xml"] and 'who="#STU"' in said_blk["xml"]
    assert any("auto-fixed" in w for w in said_blk["warnings"])
    assert s.blocks[0]["div"]["type"] == "chapter"
    assert r["summary"]["tag_counts"]["persName"] >= 2
    assert any(q["source"] == "tagging" for q in s.questions)

    rec = s.recommend_tags()
    assert [t["key"] for t in rec["tags"]][0] == "measure"
    assert all(t["key"] in TAGS for t in rec["tags"])  # bogus key filtered

    res = s.apply_instruction("화폐 단위도 태깅하고 CC BY 라이선스 넣어줘")
    assert res["retag"]["changed"] >= 1
    assert "<measure" in "".join(b["xml"] for b in s.blocks)
    assert s.metadata["licence"]["text"] == "CC BY 4.0"

    m = s.recommend_metadata()
    assert m["suggestions"][0]["key"] == "creation"
    assert m["suggestions"][0]["needs_verification"] and "1924" in m["suggestions"][0]["not_in_text"]  # not in source text
    s.update_metadata(m["suggestions"][0]["patch"])

    v = s.validate()
    assert v["wellformed"], v
    assert v["valid"], v["errors"][:5]
    assert v["dangling_refs"] == []
    xml = s.to_xml()[0]
    assert 'xml:lang="ko"' in xml and "<particDesc>" in xml and 'gi="persName"' in xml
    assert "<licence target=\"https://creativecommons.org/licenses/by/4.0/\">" in xml

    # undo restores pre-instruction state
    before_undo = sum(b["xml"].count("<measure") for b in s.blocks)
    s.undo()
    s.undo()
    assert sum(b["xml"].count("<measure") for b in s.blocks) <= before_undo

    # persistence round-trip
    p = s.save()
    s2 = Session.load(p, s.s, s.llm)
    assert s2.to_xml()[0] == s.to_xml()[0]


def test_agent_chat_passes_reasoning_back(session):
    s = session
    s.analyze()
    out = tools.chat(s, "지금 상태 알려줘")
    assert out["actions"][0]["tool"] == "get_status"
    assistant_msgs = [m for m in s.chat if m["role"] == "assistant"]
    assert assistant_msgs[0].get("reasoning_content") == "check status first"  # kept for DeepSeek thinking+tools
    assert "산문" in out["reply"]


def test_import_knote_and_validate():
    knote = Path(__file__).resolve().parents[2] / "KNoTE" / "dataset" / "14_Hyun Jin-geon_A Lucky Day (Unsu Joeun Nal).xml"
    if not knote.exists():
        pytest.skip("KNoTE checkout not present")
    s = Session.from_tei(knote.read_text(encoding="utf-8"), Settings())
    assert len(s.blocks) > 20 and s.header_override.startswith("<teiHeader")
    v = s.validate()
    assert v["wellformed"]
    for e in v["errors"]:
        assert "line" in e


def test_offline_without_key(tmp_path):
    s = Settings()
    s.api_key = ""
    s.sessions_dir = tmp_path
    ses = Session("Dear Sir,\n\nI arrived in London on 3 May 1851.\n\nYours truly,\nJohn", s)
    a = ses.analyze()
    assert "unavailable" in a["notes"]
    r = ses.tag_all()
    assert r["errors"]  # reported, not crashed
    assert validate_document(ses.to_xml()[0])["wellformed"]
