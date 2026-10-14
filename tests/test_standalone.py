"""Browser edition (dist/TEI_Agent.html) — runs in headless Chromium from file:// with a mocked DeepSeek.
Skipped when Playwright/Chromium is not installed. Build first: python scripts/build_standalone.py"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_pipeline import KO_TEXT, responder_factory

HTML = Path(__file__).resolve().parents[1] / "dist" / "TEI_Agent.html"
pw = pytest.importorskip("playwright.sync_api")


def _handler(responder):
    def handle(route):
        body = json.loads(route.request.post_data)
        out = responder(body["messages"], "response_format" in body, body.get("tools"))
        if isinstance(out, str):
            out = {"role": "assistant", "content": out}
        elif not (isinstance(out, dict) and out.get("role") == "assistant"):
            out = {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)}
        route.fulfill(status=200, headers={"access-control-allow-origin": "*", "content-type": "application/json"},
                      body=json.dumps({"choices": [{"message": out}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}))
    return handle


@pytest.mark.skipif(not HTML.exists(), reason="dist/TEI_Agent.html not built")
def test_browser_edition_end_to_end():
    responder, _ = responder_factory()
    errors = []
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=["--no-proxy-server"])
        except Exception as e:  # no browser installed
            pytest.skip(f"chromium not available: {e}")
        pg = b.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.route("https://api.deepseek.com/**", _handler(responder))
        pg.goto(HTML.as_uri())
        unit = pg.evaluate("""() => { const A = window.TEIAgent; return [
            A.checkPreservation('삼십 전', '30전').ok, A.checkPreservation('1', '<pb n="1"/>').ok,
            A.quickCheck('<said mode="x">a</said>').length, A.toArabic('열세')]; }""")
        assert unit == [False, False, 1, "13"]
        pg.fill("#key-inline", "sk-mock"); pg.click("#btn-key-save")
        pg.fill("#in-text", KO_TEXT); pg.click("#btn-start")
        pg.wait_for_function("() => window.__teiUI.session && window.__teiUI.session.status === 'tagged'", timeout=60000)
        pg.wait_for_selector("#job.hidden", state="attached")
        st = pg.evaluate("() => window.__teiUI.session.summary()")
        assert st["block_status"].get("fallback") == 1 and st["tag_counts"]["persName"] >= 2
        # 1) a finished job is announced in a banner that stays until dismissed
        pg.wait_for_selector("#done-banner:not(.hidden)")
        assert "완료" in pg.inner_text("#done-title")
        # 2) direct edits: markup changes are applied, text changes are rejected
        ed = pg.evaluate("""() => { const S = window.__teiUI.session, b = S.blocks.find((x) => x.xml.includes('<persName'));
            const f = new DOMParser().parseFromString(`<w xmlns="http://www.tei-c.org/ns/1.0">${b.xml}</w>`, 'application/xml');
            const ei = [...f.documentElement.getElementsByTagName('*')].findIndex((e) => e.localName === 'persName');
            const r1 = S.editElement(b.i, ei, { name: 'rs', attrs: { type: 'person' } });
            const r2 = S.setBlockXml(b.i, '<p>changed</p>');
            return [r1.ok, b.xml.includes('<rs type="person"'), r2.ok, !!r2.fatal]; }""")
        assert ed == [True, True, False, True]
        # 3) UI language switch
        pg.evaluate("() => window.__teiUI.setLang('en')")
        assert pg.inner_text("#btn-validate") == "Validate (tei_all)"
        pg.evaluate("() => window.__teiUI.setLang('ko')")
        assert pg.inner_text("#btn-validate") == "검증 (tei_all)"
        v = pg.evaluate("async () => await window.__teiUI.session.validate()")
        assert v["valid"], v["errors"][:3]
        # 4) gold data: stored, preferred as few-shot example, perfect score against itself
        live = Path(__file__).resolve().parents[1] / "examples" / "live" / "heldout"
        a, c = (live / "13_pred.xml").read_text(encoding="utf-8"), (live / "18_pred.xml").read_text(encoding="utf-8")
        g = pg.evaluate("""(x) => { const A = window.TEIAgent, g = A.Gold.add(A.Gold.fromTei(x, '13_pred.xml'));
            const ex = A.selectExemplars('prose_fiction', ['ko'], [], 2);
            const r = A.evaluateAgainstGold(g.blocks, g, g.registry); A.Gold.remove(g.id);
            return [ex[0].id === g.id, r.text_identical, r.micro.exact[2], r.who.acc]; }""", a)
        assert g == [True, True, 1, 1]
        # 5) merging: teiCorpus (ids deduplicated) and one TEI, both schema-valid
        m = pg.evaluate("""async ([a, c]) => { const A = window.TEIAgent, docs = [{ name: 'a', xml: a }, { name: 'c', xml: c }, { name: 'a2', xml: a }];
            const k = A.mergeAsCorpus(docs, { title: 'T' }), vk = await A.rngValidate(k.xml);
            const s = A.mergeAsSession(docs.slice(0, 2), { title: 'T' }).session, vs = await s.validate();
            return [vk.valid, k.renamed.length > 0, (k.xml.match(/<TEI[ >]/g) || []).length, vs.valid, vs.dangling_refs.length]; }""", [a, c])
        assert m == [True, True, 3, True, 0]
        b.close()
    assert not errors
