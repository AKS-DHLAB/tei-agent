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


def _launch(p):
    try:
        return p.chromium.launch(args=["--no-proxy-server"])
    except Exception as e:  # no browser for this Playwright version: a preinstalled Chromium, else skip
        exe = Path("/opt/pw-browsers/chromium")
        if exe.exists():
            return p.chromium.launch(executable_path=str(exe), args=["--no-proxy-server"])
        pytest.skip(f"chromium not available: {e}")


@pytest.mark.skipif(not HTML.exists(), reason="dist/TEI_Agent.html not built")
def test_browser_edition_end_to_end():
    responder, _ = responder_factory()
    errors = []
    with pw.sync_playwright() as p:
        b = _launch(p)
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
        # 3b) the edit dialog (the language switch re-rendered the reading view): Enter in a field applies the edit (it used to hit "Cancel"); Cancel discards
        is_open = "() => document.querySelector('#dlg-edit').open"
        n = pg.locator("#doc .t-persName").count()
        pg.locator("#doc .t-persName").first.click(); pg.fill("#ed-name", "rs"); pg.press("#ed-name", "Enter")
        assert not pg.evaluate(is_open) and pg.locator("#doc .t-persName").count() == n - 1
        m = pg.locator("#doc .t-placeName").count()
        pg.locator("#doc .t-placeName").first.click(); pg.fill("#ed-name", "rs"); pg.click("#dlg-edit [data-close]")
        assert not pg.evaluate(is_open) and pg.locator("#doc .t-placeName").count() == m > 0
        # settings: Enter saves (and never presses "Delete key")
        pg.click("#btn-settings"); pg.fill("#s-chunk", "2400"); pg.press("#s-chunk", "Enter")
        assert pg.evaluate("() => { const s = window.TEIAgent.Settings.load(); return [s.chunkChars, !!s.apiKey]; }") == [2400, True]
        v = pg.evaluate("async () => await window.__teiUI.session.validate()")
        assert v["valid"], v["errors"][:3]
        # 0.1.3: exemplar selection and language-filtered rules match the Python edition
        from tei_agent import exemplars as EX
        from tei_agent.profiles import GENRES, tag_rule
        cases = [["prose_fiction", ["de"]], ["prose_fiction", ["ko"]], ["poetry", ["ko"]], ["correspondence", ["ko"]],
                 ["dictionary", ["en"]], ["drama", ["ru"]], ["generic", ["zh"]]]
        js = pg.evaluate("""(cases) => cases.map(([g, l]) => window.TEIAgent.selectExemplars(g, l, window.TEIAgent.GENRES[g].exemplars || []).map((d) => d.id))""", cases)
        assert js == [[d["id"] for d in EX.select(g, l, GENRES[g]["exemplars"])] for g, l in cases]
        assert pg.evaluate("() => window.TEIAgent.tagRule('placeName', ['de'])") == tag_rule("placeName", ["de"])
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


def _anthropic_handler(responder, log):
    """Messages API mock: translate to the OpenAI-style messages the responder knows, and the answer back."""
    def handle(route):
        if route.request.method == "OPTIONS":
            return route.fulfill(status=204, headers={"access-control-allow-origin": "*", "access-control-allow-headers": "*"})
        body = json.loads(route.request.post_data)
        log.append({"headers": route.request.headers, "body": body, "url": route.request.url})
        msgs = [{"role": "system", "content": body.get("system", "")}]
        for m in body["messages"]:
            blocks = m["content"]
            if any(b.get("type") == "tool_result" for b in blocks):
                msgs.append({"role": "tool", "content": blocks[-1]["content"]})
            else:
                msgs.append({"role": m["role"], "content": "".join(b.get("text", "") for b in blocks)})
        out = responder(msgs, "JSON object only" in body.get("system", ""), body.get("tools"))
        if isinstance(out, (dict, list)) and not (isinstance(out, dict) and out.get("role") == "assistant"):
            out = {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)}
        if isinstance(out, str):
            out = {"role": "assistant", "content": out}
        content = [{"type": "thinking", "thinking": "", "signature": "sig"}]
        if out.get("content"):
            content.append({"type": "text", "text": out["content"]})
        for tc in out.get("tool_calls") or []:
            content.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"], "input": json.loads(tc["function"]["arguments"])})
        route.fulfill(status=200, headers={"access-control-allow-origin": "*", "content-type": "application/json"},
                      body=json.dumps({"content": content, "stop_reason": "end_turn",
                                       "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 2}}))
    return handle


@pytest.mark.skipif(not HTML.exists(), reason="dist/TEI_Agent.html not built")
def test_browser_providers_theme_and_language_picker():
    """0.1.4: ChatGPT / Claude / Gemini through the settings dialog; dark-mode button; globe language picker."""
    errors = []
    with pw.sync_playwright() as p:
        b = _launch(p)
        pg = b.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        logs = {"openai": [], "anthropic": [], "gemini": []}

        def logged(name, responder):
            inner = _handler(responder)
            def handle(route):
                if route.request.method == "GET" and route.request.url.endswith("/models"):
                    logs[name + "_models"] = route.request.headers
                    return route.fulfill(status=200, headers={"access-control-allow-origin": "*", "content-type": "application/json"},
                                         body=json.dumps({"object": "list", "data": [{"id": "models/gemini-3.8-flash"}, {"id": "models/gemini-9-new"},
                                                                                      {"id": "models/text-embedding-9"}, {"id": "gpt-9-new"}, {"id": "whisper-9"}]}))
                if route.request.method != "OPTIONS":
                    logs[name].append({"headers": route.request.headers, "body": json.loads(route.request.post_data), "url": route.request.url})
                inner(route)
            return handle
        # settings saved by 0.1.3 (one DeepSeek key) must survive the upgrade
        pg.add_init_script("""if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');
            localStorage.setItem('teiagent.settings', JSON.stringify({apiKey: 'sk-old-deepseek', model: 'deepseek-flash', baseUrl: 'https://api.deepseek.com'})); }""")
        pg.goto(HTML.as_uri())
        st = pg.evaluate("() => { const s = window.TEIAgent.Settings.load(); return [s.provider, s.apiKey, s.keys.deepseek]; }")
        assert st == ["deepseek", "sk-old-deepseek", "sk-old-deepseek"]
        # language picker: a globe icon and both language names
        assert pg.locator(".lang-pick svg").count() == 1 and "Korean" in pg.inner_text(".lang-pick")
        # theme button toggles and is remembered
        before = pg.evaluate("() => getComputedStyle(document.body).backgroundColor")
        pg.click("#btn-theme")
        theme = pg.evaluate("() => document.documentElement.dataset.theme")
        assert theme in ("dark", "light") and pg.evaluate("() => localStorage.getItem('teiagent.theme')") == theme
        assert pg.evaluate("() => getComputedStyle(document.body).backgroundColor") != before
        pg.reload()
        assert pg.evaluate("() => document.documentElement.dataset.theme") == theme

        for name, host in (("openai", "https://api.openai.com/**"), ("anthropic", "https://api.anthropic.com/**"),
                           ("gemini", "https://generativelanguage.googleapis.com/**")):
            responder, _ = responder_factory()
            pg.route(host, _anthropic_handler(responder, logs[name]) if name == "anthropic" else logged(name, responder))
            pg.click("#btn-settings"); pg.select_option("#s-provider", name)
            assert pg.input_value("#s-model") == pg.evaluate(f"() => window.TEIAgent.PROVIDERS['{name}'].model")
            pg.fill("#s-key", f"key-{name}")
            if name in ("openai", "gemini"):  # the service's own model list joins the suggestions
                pg.click("#s-model-fetch"); pg.wait_for_function("() => document.querySelector('#s-model-pick optgroup')")
                opts = pg.eval_on_selector_all("#s-model-pick option", "els => els.map(e => e.value)")
                want = "gemini-9-new" if name == "gemini" else "gpt-9-new"
                assert want in opts and not any("embed" in o or "whisper" in o for o in opts), opts
                assert logs[name + "_models"]["authorization"] == f"Bearer key-{name}"
                pg.select_option("#s-model-pick", want); assert pg.input_value("#s-model") == want
            pg.click("#s-save")
            pg.evaluate("() => window.__teiUI && document.querySelector('#btn-new').click()")
            pg.fill("#in-text", KO_TEXT); pg.click("#btn-start")
            pg.wait_for_function("() => window.__teiUI.session && window.__teiUI.session.status === 'tagged'", timeout=60000)
            pg.wait_for_selector("#job.hidden", state="attached")
            assert pg.evaluate("() => window.__teiUI.session.summary().tag_counts.persName") >= 2, name
            assert logs[name], name
            req = logs[name][0]
            if name == "anthropic":
                assert req["url"].endswith("/v1/messages") and req["headers"]["x-api-key"] == "key-anthropic"
                assert req["headers"]["anthropic-version"] == "2023-06-01" and req["headers"]["anthropic-dangerous-direct-browser-access"] == "true"
                assert "response_format" not in req["body"] and "temperature" not in req["body"] and req["body"]["fallbacks"] == "default"
                # agent chat: tool call, tool result, Claude's blocks sent back unchanged
                out = pg.evaluate("async () => await window.TEIAgent.agentChat(window.__teiUI.session, '지금 상태 알려줘', () => {})")
                assert out["actions"][0]["tool"] == "get_status"
                last = logs[name][-1]["body"]["messages"]
                assert last[-1]["content"][0]["type"] == "tool_result" and last[-2]["content"][0]["signature"] == "sig"
            else:
                assert req["headers"]["authorization"] == f"Bearer key-{name}" and req["url"].endswith("/chat/completions")
                assert "thinking" not in req["body"]
                assert ("max_completion_tokens" in req["body"]) == (name == "openai")
                assert req["body"]["model"] == ("gemini-9-new" if name == "gemini" else "gpt-9-new")
            pg.unroute(host)
        # each service keeps its own key; the old DeepSeek key is still there
        models = pg.evaluate("() => window.TEIAgent.Settings.load().models")
        assert models["gemini"] == "gemini-9-new" and models["openai"] == "gpt-9-new"
        keys = pg.evaluate("() => window.TEIAgent.Settings.load().keys")
        assert keys["deepseek"] == "sk-old-deepseek" and keys["anthropic"] == "key-anthropic" and keys["gemini"] == "key-gemini"
        b.close()
    assert not errors, errors


@pytest.mark.skipif(not HTML.exists(), reason="dist/TEI_Agent.html not built")
def test_browser_old_hangul_matches_python():
    from tei_agent.hangul import compat_to_conjoining
    from tei_agent.xmlutils import check_preservation
    raw = "ᄒᆞᆫ 사ᄅᆞ〮ᆷ이 나랏〮말ᄊᆞ미"
    xmls = ["<persName>ᄒᆞᆫ 사ᄅᆞ〮ᆷ</persName>이 나랏〮말ᄊᆞ미", "<persName>ᄒᆞ</persName>ᆫ 사ᄅᆞ〮ᆷ이 나랏〮말ᄊᆞ미",
            "ᄒᆞᆫ <rs>사ᄅᆞ</rs>〮ᆷ이 나랏〮말ᄊᆞ미"]
    texts = ["ㅅㆍㅁ ㄱㆍㅿ ㄱ, ㄴ ㄱㅏ ㅎㆍㄴ ㆍ", "ㅂㆍㄹㆍㅁ ㆁㆍㆁ", "ㄷㆎ ㅅㅸㆍ"]
    with pw.sync_playwright() as p:
        b = _launch(p)
        pg = b.new_page()
        pg.goto(HTML.as_uri())
        js = pg.evaluate("""([raw, xmls, texts]) => [xmls.map((x) => window.TEIAgent.checkPreservation(raw, x).ok),
            texts.map((t) => window.TEIAgent.compatToConjoining(t))]""", [raw, xmls, texts])
        # the start screen offers the join button for compatibility jamo
        pg.fill("#in-text", "ㅎㆍㄴ 사ㄹㆍㅁ"); pg.wait_for_selector("#hangul-note:not(.hidden)")
        pg.click("#hangul-fix")
        joined = pg.input_value("#in-text")
        b.close()
    assert js[0] == [check_preservation(raw, x)["ok"] for x in xmls] == [True, False, False]
    assert [tuple(r) for r in js[1]] == [compat_to_conjoining(t) for t in texts]
    assert joined == compat_to_conjoining("ㅎㆍㄴ 사ㄹㆍㅁ")[0] and "\u119e" in joined
