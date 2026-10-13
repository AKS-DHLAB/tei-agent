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
        b.close()
    assert not errors
