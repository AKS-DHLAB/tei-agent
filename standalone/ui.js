/* UI layer for the browser edition (same layout as the server version). */
"use strict";
(function () {
  const A = window.TEIAgent;
  const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let S = null, busy = false, lastErrBlocks = new Set();

  /* ---------- UI language (ko / en). Static text: data-en / data-en-ph / data-en-title in ui_body.html; dynamic text: L(ko, en). */
  let LANG = A.Settings.load().uiLang === "en" ? "en" : "ko";
  const L = (ko, en) => (LANG === "en" ? en : ko);
  function applyLang() {
    document.documentElement.lang = LANG;
    for (const [attr, prop] of [["en", "innerHTML"], ["enPh", "placeholder"], ["enTitle", "title"]]) {
      $$(`[data-${attr.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase())}]`).forEach((el) => {
        const koKey = "ko" + attr.slice(2);
        if (el.dataset[koKey] === undefined) el.dataset[koKey] = el[prop];
        el[prop] = LANG === "en" ? el.dataset[attr] : el.dataset[koKey];
      });
    }
    $("#ui-lang").value = LANG;
    $$("#in-genre option, #genre option").forEach((o) => { const g = A.GENRES[o.value]; if (g) o.textContent = o.parentElement.id === "genre" ? `${LANG === "en" ? g.en : g.ko} (${o.value})` : (LANG === "en" ? g.en : g.ko); });
    ruleCount(); refreshSessionList(); refreshBadges(); if (S) render();
  }
  $("#ui-lang").onchange = (e) => {
    LANG = e.target.value === "en" ? "en" : "ko";
    const st = settings(); st.uiLang = LANG; A.Settings.save(st);
    if (S) S.setUiLang(LANG);
    applyLang();
    toast(L("화면 언어: 한국어 (질문·설명도 한국어로 생성)", "UI language: English (questions and explanations are generated in English too)"));
  };

  function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 4000); }
  function settings() { return A.Settings.load(); }
  function refreshBadges() {
    const st = settings();
    $("#b-tei").textContent = `TEI P5 ${A.TEI_VERSION}`;
    $("#b-model").textContent = `${st.model}${st.thinking ? " · thinking" : ""}${st.apiKey ? "" : L(" · 키 없음", " · no key")}`;
    $("#b-model").classList.toggle("bad", !st.apiKey);
    $("#key-card").classList.toggle("hidden", !!st.apiKey);
    if (S) { S.s = st; S.llm.s = st; const u = S.llm.usageDict(); $("#b-model").title = L(`호출 ${u.calls}회, 입력 ${u.prompt_tokens}, 출력 ${u.completion_tokens} 토큰, ≈$${u.est_cost_usd_peak} (피크 단가)`, `${u.calls} calls, ${u.prompt_tokens} input / ${u.completion_tokens} output tokens, ≈$${u.est_cost_usd_peak} (peak price)`); }
  }
  function tabs(group) {
    $$(`[data-tabs=${group}] button`).forEach((b) => (b.onclick = () => showTab(group, b.dataset.t)));
  }
  function showTab(group, t) {
    const btns = $$(`[data-tabs=${group}] button`);
    btns.forEach((x) => x.classList.toggle("on", x.dataset.t === t));
    btns.map((x) => x.dataset.t).forEach((p) => $$(`[data-pane=${p}]`).forEach((el) => el.classList.toggle("hidden", p !== t)));
    if (t === "xml") renderXml();
    if (t === "chatp") $("#chat").scrollTop = 1e9;
  }
  function refreshSessionList() {
    const sel = $("#sess-list"); sel.length = 1;
    A.Store.list().forEach((s) => sel.add(new Option(`${s.title || s.id} · ${s.genre || ""} · ${s.saved.slice(5, 16).replace("T", " ")}`, s.id)));
  }
  function save() { if (S && !A.Store.save(S)) toast(L("브라우저 저장 공간이 부족합니다. '작업 파일 저장'으로 내려받아 두세요.", "Browser storage is full. Download a copy with 'Save work file'.")); refreshSessionList(); }

  /* ---------- completion banner: a job's end is announced clearly and stays until dismissed */
  const baseTitle = document.title;
  function hideDone() { $("#done-banner").classList.add("hidden"); document.title = baseTitle; }
  function showDone(ok, title, detail) {
    const b = $("#done-banner");
    b.classList.toggle("bad", !ok); b.classList.remove("hidden");
    $("#done-ico").textContent = ok ? "✓" : "✗"; $("#done-title").textContent = title; $("#done-detail").textContent = detail || "";
    b.style.animation = "none"; void b.offsetWidth; b.style.animation = "";
    document.title = `${ok ? "✓" : "✗"} ${title} — ${baseTitle}`;
    $("#done-close").focus({ preventScroll: true });
  }
  $("#done-close").onclick = hideDone;
  function stateLine() {
    if (!S) return "";
    const s = S.summary(), tags = Object.entries(s.tag_counts).filter(([k]) => k !== "p").reduce((a, [, v]) => a + v, 0);
    const openQ = (S.questions || []).filter((q) => !q.answered).length, recs = ((S.recommendations && S.recommendations.tags) || []).length;
    const parts = [L(`블록 ${s.blocks}개`, `${s.blocks} blocks`), L(`태그 ${tags}개`, `${tags} tags`)];
    if (s.block_status.fallback) parts.push(L(`⚠ 원문 보존 실패로 되돌린 블록 ${s.block_status.fallback}개`, `⚠ ${s.block_status.fallback} blocks kept previous markup`));
    if (openQ) parts.push(L(`열린 질문 ${openQ}개`, `${openQ} open questions`));
    if (recs) parts.push(L(`추천 태그 ${recs}개`, `${recs} suggested tags`));
    const v = S.validation; if (v && v.valid !== undefined) parts.push(v.valid ? L("스키마 검증 통과", "schema valid") : L(`스키마 오류 ${(v.errors || []).length}건`, `${(v.errors || []).length} schema errors`));
    return parts.join(" · ");
  }
  function resultLine(r) {
    if (!r || typeof r !== "object") return "";
    const parts = [];
    const rt = r.retag || r;
    if (typeof rt.changed === "number" && typeof rt.targets === "number") parts.push(L(`변경된 블록 ${rt.changed}/${rt.targets}`, `${rt.changed}/${rt.targets} blocks changed`));
    if (typeof r.repaired === "number") parts.push(L(`수리한 블록 ${r.repaired}개`, `${r.repaired} blocks repaired`));
    if (r.metadata_updated) parts.push(L("메타데이터 갱신", "metadata updated"));
    if ((r.actions || []).length) parts.push(L(`도구 ${r.actions.length}회 사용`, `${r.actions.length} tool calls`));
    const errs = (rt.errors || []).length; if (errs) parts.push(L(`일부 청크 오류 ${errs}건 (작업 기록 참조)`, `${errs} chunk errors (see history)`));
    return parts.join(" · ");
  }

  async function run(label, fn) {
    if (busy) return toast(L("다른 작업이 진행 중입니다.", "Another job is running."));
    busy = true; hideDone(); $("#job").classList.remove("hidden"); $("#job-msg").textContent = label; $("#job-bar").style.width = "3%";
    $$("main button, header button").forEach((b) => (b.disabled = true));
    const progress = (msg, frac) => { $("#job-msg").textContent = `${label} · ${msg}`; $("#job-bar").style.width = `${Math.round(frac * 100)}%`; };
    let r, err = null;
    try { r = await fn(progress); }
    catch (e) { console.error(e); err = e; }
    finally {
      busy = false; $("#job").classList.add("hidden"); $$("main button, header button").forEach((b) => (b.disabled = false));
      $("#chat .pending")?.remove();
      if (S) { save(); render(); } refreshBadges();
    }
    if (err) { showDone(false, L(`${label} 실패`, `${label} failed`), err.message); toast(L("오류: ", "Error: ") + err.message); }
    else showDone(true, L(`${label} 완료`, `${label} finished`), [resultLine(r), stateLine()].filter(Boolean).join(" · "));
    return r;
  }

  function openSession(s) {
    S = s; S.setUiLang(LANG); $("#start").classList.add("hidden"); $("#ws").classList.remove("hidden"); render(); refreshBadges();
  }

  /* ---------- start screen */
  $("#btn-key-save").onclick = () => { const st = settings(); st.apiKey = $("#key-inline").value.trim(); A.Settings.save(st); $("#key-inline").value = ""; refreshBadges(); toast(st.apiKey ? L("키를 저장했습니다.", "Key saved.") : L("키가 비어 있습니다.", "The key is empty.")); };
  $("#btn-key-test").onclick = async () => {
    const st = settings(); const k = $("#key-inline").value.trim(); if (k) st.apiKey = k;
    if (!st.apiKey) { $("#key-status").textContent = L("✗ 키가 없습니다. 이 주소에서는 키를 처음부터 다시 넣어야 합니다(파일로 열었을 때 저장한 키는 넘어오지 않음).", "✗ No key. Enter it again for this address (a key saved while opening the file locally does not carry over)."); return; }
    $("#key-status").textContent = L("연결 확인 중…", "Checking connection…");
    try { const l = new A.LLM(st); await l.chat([{ role: "system", content: 'Reply in json like {"ok":true}' }, { role: "user", content: "ping" }], { json: true, maxTokens: 50, retries: 1 });
      $("#key-status").textContent = L("✓ DeepSeek 연결 성공", "✓ Connected to DeepSeek") + (k ? L(" — 이제 ‘저장’을 누르세요.", " — now press ‘Save’.") : ""); }
    catch (e) { $("#key-status").textContent = "✗ " + e.message; }
  };
  $("#in-file").onchange = async (e) => { const f = e.target.files[0]; if (f) $("#in-text").value = await f.text(); };
  $("#in-tei").onchange = async (e) => { const f = e.target.files[0]; if (!f) return; try { const s = A.Session.fromTei(await f.text()); openSession(s); save(); toast(L("불러왔습니다. '검증'으로 스키마 오류를 확인하세요.", "Loaded. Use 'Validate' to check for schema errors.")); } catch (err) { toast(err.message); } };
  $("#in-session").onchange = async (e) => { const f = e.target.files[0]; if (!f) return; try { openSession(A.Session.fromState(JSON.parse(await f.text()))); save(); } catch (err) { toast(L("작업 파일을 읽을 수 없습니다: ", "Cannot read the work file: ") + err.message); } };
  $("#btn-start").onclick = () => {
    const text = $("#in-text").value; if (!text.trim()) return toast(L("텍스트를 입력하세요", "Enter some text"));
    if (!settings().apiKey) toast(L("API 키가 없어 휴리스틱 분석만 합니다. 키를 넣으면 자동 태깅이 됩니다.", "No API key: heuristic analysis only. Add a key to enable auto-tagging."));
    const s = new A.Session(text, settings()); s.setProjectRules($("#in-rules").value); rememberRules($("#in-rules").value); openSession(s);
    const hints = { genre: $("#in-genre").value || null, lang: $("#in-lang").value || null };
    const title = $("#in-title").value.trim(), author = $("#in-author").value.trim(), auto = $("#in-auto").checked;
    run(L("분석·태깅", "Analysis & tagging"), async (p) => {
      p(L("텍스트 분석 중", "analysing text"), 0.05); await s.analyze(hints);
      if (title) s.metadata.titles = [{ text: title, type: "main", lang: s.langs[0] }];
      if (author) s.metadata.authors = [{ name: author }];
      render();
      if (auto && settings().apiKey) {
        p(L("인물·장소 레지스트리 구축 중", "building person/place registry"), 0.1); await s.buildRegistry();
        const r = await s.tagAll(p); p(L("추천 생성 중", "generating suggestions"), 0.95); await s.recommendTags();
        return r;
      }
    });
  };
  $("#sess-list").onchange = (e) => { const id = e.target.value; if (!id) return; const s = A.Store.load(id); if (s) openSession(s); else toast(L("작업을 불러올 수 없습니다.", "Cannot open this work.")); e.target.value = ""; };
  $("#btn-new").onclick = () => { S = null; hideDone(); $("#ws").classList.add("hidden"); $("#start").classList.remove("hidden"); };

  $("#credit-ver").textContent = "v" + A.APP_VERSION;
  // plain close buttons (type="button"), so Enter in a dialog field never triggers "Close" or "Delete key"
  $$("dialog [data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
  /* ---------- settings dialog */
  $("#btn-settings").onclick = () => {
    const st = settings();
    $("#s-key").value = st.apiKey; $("#s-model").value = st.model; $("#s-base").value = st.baseUrl; $("#s-chunk").value = st.chunkChars;
    $("#s-workers").value = st.maxWorkers; $("#s-think").checked = st.thinking; $("#dlg-settings").showModal();
  };
  $("#s-save").onclick = () => {
    const st = settings();
    Object.assign(st, { apiKey: $("#s-key").value.trim(), model: $("#s-model").value.trim() || "deepseek-flash", baseUrl: $("#s-base").value.trim() || "https://api.deepseek.com",
      chunkChars: parseInt($("#s-chunk").value, 10) || 2500, maxWorkers: parseInt($("#s-workers").value, 10) || 4, thinking: $("#s-think").checked });
    toast(A.Settings.save(st) ? L("설정을 저장했습니다.", "Settings saved.") : L("이 브라우저는 저장을 막고 있어 이번 창에서만 유지됩니다.", "This browser blocks storage; settings last for this window only.")); refreshBadges();
  };
  $("#s-clear").onclick = () => { const st = settings(); st.apiKey = ""; A.Settings.save(st); refreshBadges(); toast(L("키를 삭제했습니다.", "Key deleted.")); };

  /* ---------- render */
  function render() {
    if (!S) return;
    const s = S.summary();
    if (document.activeElement !== $("#ws-rules")) $("#ws-rules").value = S.project_rules || "";
    $("#genre").value = S.genre; $("#analysis-notes").textContent = (S.analysis && S.analysis.notes) || "";
    const counts = Object.entries(s.tag_counts).filter(([k]) => k !== "p"), max = Math.max(1, ...counts.map((c) => c[1]));
    $("#counts").innerHTML = counts.slice(0, 18).map(([k, v]) => `<div class="bar"><span class="lbl">${esc(k)}</span><span class="track"><span class="fill" style="display:block;width:${(100 * v) / max}%"></span></span><span class="c">${v}</span></div>`).join("") || `<span class="hint">${L("아직 태그가 없습니다.", "No tags yet.")}</span>`;
    $("#bstat").textContent = Object.entries(s.block_status).map(([k, v]) => `${k}: ${v}`).join(" · ") + L(" · 언어: ", " · languages: ") + (S.langs || []).join(", ")
      + (() => { const u = S.llm.usageDict(); return u.calls ? L(` · 이번 세션 호출 ${u.calls}회, 입력 ${u.prompt_tokens}(캐시 ${u.cached_tokens}) · 출력 ${u.completion_tokens} 토큰 ≈ $${u.est_cost_usd_peak} (피크 단가 어림)`, ` · ${u.calls} calls this session, input ${u.prompt_tokens} (cached ${u.cached_tokens}) · output ${u.completion_tokens} tokens ≈ $${u.est_cost_usd_peak} (peak price estimate)`) : ""; })();
    $("#hist").innerHTML = S.history.slice(-12).reverse().map((h) => `<div>${esc(h.when.slice(11, 16))} ${esc(h.action)}</div>`).join("");
    renderDoc(); renderRecs(); renderQs(); renderChat(); renderRegistry(); renderMetaForm(); renderMetaRecs(); showValidation(true);
    if (!$("[data-pane=xml]").classList.contains("hidden")) renderXml();
  }
  // element spans carry data-ei (pre-order element index in the block), text runs data-ti (text-node index) → direct editing
  const STRUCT = new Set(["p", "ab", "head", "l", "lg", "sp", "u", "div", "floatingText", "body", "list", "item", "table", "row", "cell"]);
  function xmlToHtml(node, c, top = false) {
    if (node.nodeType === 3) return `<span class="tx" data-ti="${c.t++}">${esc(node.nodeValue)}</span>`;
    if (node.nodeType !== 1) return "";
    const n = node.localName, ei = c.e++; let attrs = "", tip = `<${n}`;
    for (const a of node.attributes) { attrs += ` data-${a.localName.replace(/[^a-z0-9-]/gi, "")}="${esc(a.value)}"`; tip += ` ${a.name}="${a.value}"`; }
    return `<span class="t t-${n}${top && STRUCT.has(n) ? " s" : ""}" title="${esc(tip + ">")}"${attrs} data-ei="${ei}">${[...node.childNodes].map((ch) => xmlToHtml(ch, c)).join("")}</span>`;
  }
  function renderDoc() {
    const used = new Set(Object.keys(S.summary().tag_counts));
    $("#legend").innerHTML = ["persName", "placeName", "orgName", "rs", "date", "time", "measure", "said", "q", "foreign", "term", "title", "roleName", "name"].filter((t) => used.has(t)).map((t) => `<span class="t-${t}">${t}</span>`).join("");
    const parser = new DOMParser(); let html = "";
    for (const b of S.blocks) {
      if (b.part) html += `<div class="divmark part">${esc(b.part.type)} ${esc(b.part.n ?? "")}</div>`;
      if (b.div) html += `<div class="divmark">${esc(b.div.type)} ${esc(b.div.n ?? "")}</div>`;
      const d = parser.parseFromString(`<w xmlns="http://www.tei-c.org/ns/1.0">${b.xml}</w>`, "application/xml");
      const c = { e: 0, t: 0 };
      const inner = d.getElementsByTagName("parsererror").length ? `<span class="w">${L("XML 오류", "XML error")}</span> ${esc(b.raw)}` : [...d.documentElement.childNodes].map((ch) => xmlToHtml(ch, c, true)).join("");
      html += `<div class="blk ${b.status === "fallback" ? "fallback" : ""} ${b.status === "edited" ? "edited" : ""} ${lastErrBlocks.has(b.i) ? "err" : ""}" data-i="${b.i}"><span class="n">${b.i}</span>`
        + `<span class="bt"><button type="button" data-act="xml" title="${L("이 블록의 XML 직접 수정", "Edit this block's XML")}">✎ XML</button><button type="button" data-act="chat" title="${L("이 블록에 대해 대화로 지시", "Give an instruction about this block")}">💬</button></span>`
        + `${inner}${(b.warnings || []).length ? `<div class="w">⚠ ${esc(b.warnings.join(" / "))}</div>` : ""}</div>`;
    }
    $("#doc").innerHTML = html || `<p class="hint">${L("블록이 없습니다.", "No blocks.")}</p>`;
  }
  function flashBlock(i) { const el = $(`#doc .blk[data-i="${i}"]`); if (el) { el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1700); } }
  function renderXml() {
    const x = S.toXml()[0];
    $("#xml").innerHTML = esc(x).replace(/(&lt;\/?)([\w:]+)/g, '$1<span class="x-tag">$2</span>').replace(/([\w:]+)=(&quot;.*?&quot;)/g, '<span class="x-att">$1</span>=<span class="x-val">$2</span>');
  }
  function download(name, text, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); }
  const fname = () => ((S.metadata.titles || [{}])[0].text || S.id).replace(/[\\/:*?"<>|]/g, "_");
  $("#btn-dl").onclick = () => { download(`${fname()}.xml`, S.toXml()[0], "application/xml"); showDone(true, L("XML 저장 완료", "XML saved"), `${fname()}.xml · ${stateLine()}`); };
  $("#btn-save-json").onclick = () => { const d = S.state(); d.snapshots = S.snapshots.slice(-5); download(`${fname()}.teiagent.json`, JSON.stringify(d), "application/json"); showDone(true, L("작업 파일 저장 완료", "Work file saved"), `${fname()}.teiagent.json`); };

  /* ---------- direct editing in the reading view */
  const ED = { mode: null, i: null, ei: null, sel: null, force: false };
  const blockOf = (el) => S.blocks.find((b) => b.i === +el.closest(".blk").dataset.i);
  function elementAt(b, ei) { try { return new DOMParser().parseFromString(`<w xmlns="http://www.tei-c.org/ns/1.0">${b.xml}</w>`, "application/xml").documentElement.getElementsByTagName("*")[ei]; } catch (e) { return null; } }
  function fillNames() { const dl = $("#ed-names"); if (!dl.options.length) dl.innerHTML = A.elementNames().map((n) => `<option value="${esc(n)}">`).join(""); }
  function refOptions() { return ["persons", "places", "orgs"].flatMap((k) => (S.registry[k] || []).map((e) => `<option value="#${esc(e.id)}">${esc(e.name)}</option>`)).join(""); }
  function attrRow(k = "", v = "") {
    const d = document.createElement("div"); d.className = "ed-attr";
    d.innerHTML = `<input type="text" class="ak" placeholder="${L("속성", "attribute")}" value="${esc(k)}"><input type="text" class="av" placeholder="${L("값", "value")}" value="${esc(v)}"><button type="button" title="${L("삭제", "remove")}">✕</button>`;
    const ak = d.querySelector(".ak"), av = d.querySelector(".av");
    const sync = () => { av.setAttribute("list", /^(ref|who|corresp|key)$/.test(ak.value.trim()) ? "ed-refs" : ""); };
    ak.oninput = sync; sync(); d.querySelector("button").onclick = () => d.remove();
    $("#ed-attrs").appendChild(d);
  }
  function showAllowed() {
    const n = $("#ed-name").value.trim();
    $("#ed-allowed").textContent = !n ? "" : !A.elementExists(n) ? L(`⚠ <${n}>는 TEI 요소가 아닙니다`, `⚠ <${n}> is not a TEI element`)
      : L("허용 속성(전역 제외): ", "allowed attributes (besides global): ") + (A.allowedAttrs(n).slice(0, 18).join(", ") || "—");
  }
  function edProblems(r) {
    const box = $("#ed-problems");
    if (!r || r.ok) { box.classList.add("hidden"); return; }
    box.classList.remove("hidden"); box.classList.toggle("warn", !r.fatal);
    box.textContent = (r.fatal ? L("적용할 수 없습니다 — 원문 글자가 바뀌었거나 XML이 올바르지 않습니다:\n", "Cannot apply — the source text changed or the XML is not well-formed:\n")
      : L("스키마 문제가 있습니다. 고치거나 ‘그래도 적용’을 누르세요:\n", "Schema problems found. Fix them or press ‘Apply anyway’:\n")) + r.problems.slice(0, 6).join("\n");
    ED.force = !r.fatal; $("#ed-apply").textContent = ED.force ? L("그래도 적용", "Apply anyway") : L("적용", "Apply");
  }
  function openEditor(mode, i, extra = {}) {
    fillNames(); Object.assign(ED, { mode, i, ei: extra.ei ?? null, sel: extra.sel || null, force: false });
    $("#ed-refs")?.remove(); const dl = document.createElement("datalist"); dl.id = "ed-refs"; dl.innerHTML = refOptions(); $("#edit-form").appendChild(dl);
    $("#ed-attrs").innerHTML = ""; edProblems(null); $("#ed-apply").textContent = L("적용", "Apply");
    $("#ed-elem").classList.toggle("hidden", mode === "xml"); $("#ed-raw").classList.toggle("hidden", mode !== "xml");
    $("#ed-unwrap").classList.toggle("hidden", mode !== "elem");
    const b = S.blocks.find((x) => x.i === i);
    if (mode === "xml") {
      $("#ed-title").textContent = L(`블록 ${i} XML 수정`, `Edit XML of block ${i}`);
      $("#ed-text").textContent = L("태그만 바꿀 수 있습니다. 원문 글자를 바꾸면 적용되지 않습니다.", "Only markup may change; edits that alter the source text are rejected.");
      $("#ed-xml").value = b.xml;
    } else if (mode === "elem") {
      const el = elementAt(b, ED.ei); if (!el) return toast(L("요소를 찾을 수 없습니다", "Element not found"));
      $("#ed-title").textContent = L(`블록 ${i} · <${el.localName}> 수정`, `Block ${i} · edit <${el.localName}>`);
      // breadcrumb: ancestors inside the block, so a nested tag's parent can be edited too
      const top = el.ownerDocument.documentElement, chain = []; for (let p = el; p && p !== top; p = p.parentNode) chain.unshift(p);
      const all = [...top.getElementsByTagName("*")];
      $("#ed-text").innerHTML = `“${esc((el.textContent || "").slice(0, 80))}”<div class="chips">${chain.map((p) => `<span class="chip ${p === el ? "on" : ""}" data-ei="${all.indexOf(p)}">&lt;${esc(p.localName)}&gt;</span>`).join(" › ")}</div>`;
      $$("#ed-text .chip").forEach((c) => (c.onclick = () => { if (+c.dataset.ei !== ED.ei) openEditor("elem", i, { ei: +c.dataset.ei }); }));
      $("#ed-name").value = el.localName;
      for (const a of el.attributes) if (!/^xmlns/.test(a.name)) attrRow(a.namespaceURI === "http://www.w3.org/XML/1998/namespace" ? "xml:" + a.localName : a.name, a.value);
    } else {
      $("#ed-title").textContent = L(`블록 ${i} · 선택한 글자에 태그 추가`, `Block ${i} · tag the selected text`);
      $("#ed-text").textContent = `“${ED.sel.text.slice(0, 80)}”`;
      $("#ed-name").value = $("#ed-name").dataset.last || "persName";
    }
    showAllowed();
    if (!$("#dlg-edit").open) $("#dlg-edit").showModal();
    if (mode === "wrap") $("#ed-name").select();
  }
  $("#ed-name").oninput = showAllowed;
  $("#ed-add-attr").onclick = () => attrRow();
  function collectAttrs() {
    const o = {}; $$("#ed-attrs .ed-attr").forEach((r) => { const k = r.querySelector(".ak").value.trim(), v = r.querySelector(".av").value; if (k) o[k] = v; }); return o;
  }
  function afterEdit(r, i, msg) {
    if (!r.ok) return edProblems(r);
    $("#dlg-edit").close(); hidePop(); window.getSelection()?.removeAllRanges();
    if (r.unchanged) return toast(L("바뀐 내용이 없습니다.", "Nothing changed."));
    S.validation = {}; save(); render(); flashBlock(i);
    toast(msg + (r.problems.length ? L(" (스키마 경고 있음)", " (with schema warnings)") : "") + L(" · 되돌리기로 취소 가능", " · Undo to revert"));
  }
  // Enter in a field submits the form: apply the edit instead of closing the dialog (the old default button was "Cancel")
  $("#edit-form").addEventListener("submit", (e) => { e.preventDefault(); applyEdit(); });
  function applyEdit() {
    const i = ED.i, opts = { force: ED.force }; let r;
    try {
      if (ED.mode === "xml") r = S.setBlockXml(i, $("#ed-xml").value, L("XML 직접 수정", "manual XML edit"), opts);
      else {
        const name = $("#ed-name").value.trim(); if (!name) return toast(L("요소 이름을 입력하세요", "Enter an element name"));
        if (ED.mode === "elem") r = S.editElement(i, ED.ei, { name, attrs: collectAttrs() }, opts);
        else { r = S.wrapText(i, ED.sel.ti, ED.sel.start, ED.sel.end, name, collectAttrs(), opts); $("#ed-name").dataset.last = name; }
      }
    } catch (e) { r = { ok: false, fatal: true, problems: [e.message] }; }
    afterEdit(r, i, L(`블록 ${i}을(를) 수정했습니다`, `Block ${i} updated`));
  }
  $("#ed-unwrap").onclick = () => { let r; try { r = S.editElement(ED.i, ED.ei, { unwrap: true }, { force: true }); } catch (e) { r = { ok: false, fatal: true, problems: [e.message] }; } afterEdit(r, ED.i, L("태그를 제거했습니다", "Tag removed")); };
  // invalidate the 'apply anyway' state once the user changes something
  $("#edit-form").addEventListener("input", () => { if (ED.force) { ED.force = false; $("#ed-apply").textContent = L("적용", "Apply"); } });

  function hidePop() { $("#sel-pop").classList.add("hidden"); }
  function selectionInfo() {
    const sel = window.getSelection(); if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    const r = sel.getRangeAt(0), a = r.startContainer, z = r.endContainer;
    const blk = a.parentElement && a.parentElement.closest(".blk"); if (!blk || !$("#doc").contains(blk)) return null;
    const txA = a.nodeType === 3 && a.parentElement.closest(".tx"), txZ = z.nodeType === 3 && z.parentElement.closest(".tx");
    if (!txA || txA !== txZ || r.startOffset === r.endOffset) return { blk, crossing: true, rect: r.getBoundingClientRect() };
    return { blk, i: +blk.dataset.i, ti: +txA.dataset.ti, start: r.startOffset, end: r.endOffset, text: r.toString(), rect: r.getBoundingClientRect() };
  }
  $("#doc").addEventListener("mouseup", () => setTimeout(() => {
    const info = selectionInfo(); if (!info) return hidePop();
    const pop = $("#sel-pop"), btn = $("#sel-add");
    ED.pending = info.crossing ? null : info; ED.pendingBlk = +info.blk.dataset.i;
    btn.textContent = info.crossing ? L("태그 경계에 걸침 — ✎ XML로 수정", "Crosses a tag boundary — use ✎ XML") : L("+ 태그 추가", "+ Add tag");
    pop.style.left = `${Math.max(8, info.rect.left + window.scrollX)}px`; pop.style.top = `${info.rect.bottom + window.scrollY + 6}px`;
    pop.classList.remove("hidden");
  }, 0));
  $("#sel-add").onmousedown = (e) => e.preventDefault();
  $("#sel-add").onclick = () => {
    const info = ED.pending; hidePop();
    if (!info) return openEditor("xml", ED.pendingBlk);
    openEditor("wrap", info.i, { sel: info });
  };
  document.addEventListener("mousedown", (e) => { if (!e.target.closest("#sel-pop")) hidePop(); });
  $("#doc").addEventListener("click", (e) => {
    const act = e.target.closest(".bt button");
    if (act) {
      const i = +act.closest(".blk").dataset.i;
      if (act.dataset.act === "xml") openEditor("xml", i);
      else { showTab("side", "chatp"); $("#chat-in").value = L(`블록 ${i}: `, `Block ${i}: `); $("#chat-in").focus(); scrollToChat(); }
      return;
    }
    const sel = window.getSelection(); if (sel && !sel.isCollapsed) return; // selecting text, not clicking a tag
    const t = e.target.closest(".t:not(.s)"); if (!t || !$("#doc").contains(t)) return;
    openEditor("elem", blockOf(t).i, { ei: +t.dataset.ei });
  });
  function scrollToChat() { if (window.matchMedia("(max-width:820px)").matches) $(".right").scrollIntoView({ behavior: "smooth" }); }
  $("#fab-chat").onclick = () => { showTab("side", "chatp"); scrollToChat(); $("#chat-in").focus({ preventScroll: true }); };

  /* ---------- validation */
  $("#btn-validate").onclick = () => run(L("tei_all 검증", "tei_all validation"), async (p) => { p(L("스키마 로딩·검증 중 (10~20초)", "loading schema and validating (10–20 s)"), 0.3); await S.validate(); });
  $("#btn-repair").onclick = () => run(L("자동 수리", "Auto-repair"), (p) => S.repair(p));
  $("#btn-undo").onclick = () => { if (!S.snapshots.length) return toast(L("되돌릴 작업이 없습니다", "Nothing to undo")); toast(L("되돌림: ", "Undone: ") + S.undo()); S.validation = {}; save(); render(); };
  function showValidation(quiet) {
    const v = S.validation; if (!v || v.valid === undefined) { lastErrBlocks = new Set(); $("#val-status").textContent = L("미검증", "Not validated"); $("#val-errors").classList.add("hidden"); return; }
    lastErrBlocks = new Set((v.errors || []).map((e) => e.block).filter((x) => x !== null && x !== undefined));
    const n = (v.errors || []).length;
    $("#val-status").innerHTML = v.valid ? `<span class="val-ok">✓ ${esc(v.schema || "valid")}</span>` : `<span class="val-bad">✗ ${L(`오류 ${n}건`, `${n} errors`)}</span>` + ((v.dangling_refs || []).length ? L(` · 미정의 ref ${v.dangling_refs.length}`, ` · ${v.dangling_refs.length} undefined refs`) : "");
    const ul = $("#val-errors"); ul.classList.toggle("hidden", !!v.valid);
    ul.innerHTML = (v.errors || []).slice(0, 40).map((e) => `<li>${e.block !== null && e.block !== undefined ? `[${L("블록", "block")} ${e.block}] ` : ""}line ${e.line}: ${esc(e.message)}</li>`).join("");
    if (!quiet) renderDoc();
  }

  /* ---------- recommendations, questions, chat */
  function renderRecs() {
    const r = (S.recommendations && S.recommendations.tags) || [];
    $("#r-cnt").textContent = r.length || "";
    if (!r.length) { $("#recs").innerHTML = `<span class="hint">${L("아직 추천이 없습니다. “추천 다시 받기”를 누르세요.", "No suggestions yet. Press “Get suggestions again”.")}</span>`; return; }
    $("#recs").innerHTML = r.map((t) => `<div class="rec p${t.priority || 3}"><label><input type="checkbox" value="${esc(t.key)}" ${t.priority === 1 ? "checked" : ""}>
      <div><b>${esc(t.label)}</b> <span class="k">${esc((t.elements || []).join(", "))} · ~${esc(t.estimated_count ?? "?")}</span>
      <div>${esc(t.why || "")}</div>${(t.examples || []).length ? `<div class="ex">${L("예", "e.g.")}: ${t.examples.slice(0, 3).map(esc).join(" / ")}</div>` : ""}</div></label></div>`).join("");
  }
  $("#btn-rec").onclick = () => run(L("태그 추천", "Tag suggestions"), () => S.recommendTags());
  $("#btn-accept").onclick = () => { const keys = $$("#recs input:checked").map((i) => i.value); if (!keys.length) return toast(L("적용할 태그를 선택하세요", "Select tags to apply")); run(L("추천 태그 적용", "Applying suggested tags"), (p) => S.acceptTags(keys, $("#rec-guide").value, p)); };
  function renderQs() {
    const qs = (S.questions || []).slice().sort((a, b) => (a.answered ? 1 : 0) - (b.answered ? 1 : 0));
    const open = qs.filter((q) => !q.answered).length; $("#q-cnt").textContent = open || "";
    if (!qs.length) { $("#questions").innerHTML = `<span class="hint">${L("열린 질문이 없습니다.", "No open questions.")}</span>`; return; }
    $("#questions").innerHTML = qs.slice(0, 20).map((q) => `<div class="q ${q.answered ? "done" : ""}" data-q="${esc(q.id)}">
      <div>${esc(q.question)} ${q.block !== null && q.block !== undefined ? `<span class="hint">(${L("블록", "block")} ${q.block})</span>` : ""}</div>
      ${q.about ? `<div class="hint">${esc(q.about)}</div>` : ""}
      ${q.answered ? `<div class="hint">→ ${esc(q.answer)}</div>` : `<div class="chips">${(q.options || []).map((o) => `<span class="chip" data-a="${esc(o)}">${esc(o)}</span>`).join("")}</div>
      <div class="row" style="margin-top:4px"><input type="text" class="grow" placeholder="${L("직접 답변", "Your answer")}"><button>${L("답변", "Answer")}</button></div>`}</div>`).join("");
    $$("#questions .q").forEach((el) => {
      const id = el.dataset.q, go = (a) => run(L("답변 반영", "Applying answer"), (p) => S.answerQuestion(id, a, p));
      el.querySelectorAll(".chip").forEach((c) => (c.onclick = () => go(c.dataset.a)));
      const b = el.querySelector("button"); if (b) b.onclick = () => { const v = el.querySelector("input").value; if (v) go(v); };
    });
  }
  const CHAT_EXAMPLES = () => L(["‘그’가 주인공을 가리키는 곳은 rs로 연결해줘", "날짜 표현에 when 속성을 넣어줘", "저자 Wikidata ID 찾아서 헤더에 넣어줘"],
    ["Link pronouns that refer to the protagonist with rs", "Add @when to every date", "Find the author's Wikidata ID and add it to the header"]);
  function renderChat() {
    // show the tools the agent actually called (transparency: what the harness did, not only what the model said)
    const msgs = (S.chat || []).filter((m) => (m.role === "user" || m.role === "assistant") && (m.content || (m.tool_calls || []).length));
    $("#chat").innerHTML = msgs.length ? msgs.map((m) =>
      (m.tool_calls || []).length && !m.content ? `<div class="msg tool hint">🔧 ${m.tool_calls.map((c) => esc(c.function.name)).join(" · ")}</div>`
        : `<div class="msg ${m.role}">${esc(m.content)}</div>` + ((m.tool_calls || []).length ? `<div class="msg tool hint">🔧 ${m.tool_calls.map((c) => esc(c.function.name)).join(" · ")}</div>` : "")).join("")
      : `<div class="chat-empty">${L("잘못 붙은 태그나 빠진 태그를 말로 지시하세요. 예:", "Describe in words what to fix or add. For example:")}<div>${CHAT_EXAMPLES().map((x) => `<span class="chip" data-ex="${esc(x)}">${esc(x)}</span>`).join("")}</div></div>`;
    $$("#chat [data-ex]").forEach((c) => (c.onclick = () => { $("#chat-in").value = c.dataset.ex; $("#chat-in").focus(); }));
    $("#chat").scrollTop = 1e9;
  }
  $("#btn-chat").onclick = () => {
    const t = $("#chat-in").value.trim(); if (!t || busy) { if (busy) toast(L("다른 작업이 진행 중입니다.", "Another job is running.")); return; } $("#chat-in").value = "";
    let job;
    if ($("#chat-agent").checked) job = run(L("에이전트 작업", "Agent task"), (p) => A.agentChat(S, t, p));
    else { S.chat.push({ role: "user", content: t }); job = run(L("지시 반영", "Applying instruction"), async (p) => { const r = await S.applyInstruction(t, p); S.chat.push({ role: "assistant", content: r.reply || L("반영했습니다.", "Done.") }); return r; }); }
    renderChat(); $("#chat").insertAdjacentHTML("beforeend", `<div class="msg pending">${L("작업 중…", "Working…")}</div>`); $("#chat").scrollTop = 1e9;
    return job;
  };
  $("#chat-in").onkeydown = (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("#btn-chat").click(); };

  /* ---------- registry */
  function renderRegistry() {
    let h = "";
    for (const [k, label] of [["persons", L("인물", "Persons")], ["places", L("장소", "Places")], ["orgs", L("기관", "Organisations")]]) {
      const l = S.registry[k] || []; if (!l.length) continue;
      h += `<h3>${label} (${l.length})</h3><table class="reg">${l.map((e) => `<tr><td><code>#${esc(e.id)}</code></td><td><span class="ed" data-k="${k}" data-id="${esc(e.id)}" style="cursor:text">${esc(e.name)}</span>${e.note ? `<div class="hint">${esc(e.note)}</div>` : ""}</td></tr>`).join("")}</table>`;
    }
    $("#registry").innerHTML = h || `<span class="hint">${L("레지스트리가 비어 있습니다.", "The registry is empty.")}</span>`;
    $$("#registry .ed").forEach((el) => (el.onclick = () => { const v = prompt(L("이름 수정", "Edit name"), el.textContent); if (!v) return; S.editEntity("update", el.dataset.k, el.dataset.id, { name: v }); save(); render(); }));
  }

  /* ---------- metadata */
  const MF = [["title", "제목", "Title", "titles.0.text"], ["subtitle", "부제", "Subtitle", "titles.1.text"], ["author", "저자", "Author", "authors.0.name"], ["authorRef", "저자 URI", "Author URI", "authors.0.ref"],
    ["publisher", "발행처", "Publisher", "publication.publisher"], ["pubPlace", "발행지", "Place of publ.", "publication.pubPlace"], ["licence", "라이선스 URL", "Licence URL", "licence.target"],
    ["source", "저본 서지", "Source", "sources.0.title"], ["sourceDate", "저본 연도", "Source date", "sources.0.date"], ["sourceUrl", "저본 URL", "Source URL", "sources.0.idnos.0.value"],
    ["creation", "창작 시기", "Created", "creation.date"], ["series", "컬렉션", "Collection", "series.title"], ["funder", "지원기관", "Funder", "funder"], ["abstract", "초록", "Abstract", "abstract"]];
  const getp = (o, p) => p.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
  function renderMetaForm() { $("#meta-form").innerHTML = MF.map(([id, ko, en, p]) => `<label for="m-${id}">${L(ko, en)}</label><input type="text" id="m-${id}" value="${esc(getp(S.metadata, p) ?? "")}">`).join(""); }
  $("#btn-md-save").onclick = () => {
    const md = JSON.parse(JSON.stringify(S.metadata || {}));
    const setp = (o, p, v) => { const ks = p.split("."); let a = o; ks.forEach((k, i) => { if (i === ks.length - 1) a[k] = v; else { if (a[k] == null) a[k] = /^\d+$/.test(ks[i + 1]) ? [] : {}; a = a[k]; } }); };
    for (const [id, , , p] of MF) { const v = $(`#m-${id}`).value.trim(); if (v || getp(md, p) != null) setp(md, p, v || null); }
    if (md.titles) { md.titles = md.titles.filter((t) => t && t.text); md.titles.forEach((t, i) => (t.type = t.type || (i ? "sub" : "main"))); }
    if (md.sources && md.sources[0]) { md.sources[0].type = md.sources[0].type || "originalSource"; (md.sources[0].idnos || []).forEach((i) => (i.type = i.type || "URL")); }
    if (md.licence && md.licence.target && !md.licence.text) md.licence.text = md.licence.target;
    S.updateMetadata(md); save(); render(); toast(L("메타데이터를 저장했습니다", "Metadata saved"));
  };
  $("#btn-md-rec").onclick = () => run(L("메타데이터 추천", "Metadata suggestions"), () => S.recommendMetadata());
  function renderMetaRecs() {
    const r = S.meta_recommendations || {}; let h = "";
    if ((r.suggestions || []).length) h += `<h3>${L("제안된 값", "Suggested values")}</h3>` + r.suggestions.map((s, i) => `<div class="rec"><b>${esc(s.key)}</b> <span class="k">${esc(s.confidence || "")}</span>${s.needs_verification ? ` <span class="badge bad">${s.not_in_text ? L("검증 필요 · 원문에 없는 값", "verify · not in the text") : s.model_written ? L("모델 작성 · 검토", "written by model · review") : L("검증 필요 · 모델 지식 기반", "verify · from model knowledge")}</span>` : ""}${(s.identifiers_removed || []).length ? ` <span class="badge">${L("ID 제거됨 → 전거 검색 사용", "IDs removed → use authority search")}</span>` : ""}
      ${(s.not_in_text || []).length ? `<div class="hint">${L("원문에서 확인 안 됨: ", "Not found in the text: ")}${esc(s.not_in_text.join(", "))}</div>` : ""}
      <div class="k">${esc(JSON.stringify(s.patch))}</div><div>${esc(s.why || "")}</div><div class="hint">${L("근거: ", "Evidence: ")}${esc(s.evidence || "")}</div><button data-sug="${i}" style="margin-top:4px">${L("적용", "Apply")}</button></div>`).join("");
    if ((r.to_lookup || []).length) h += `<h3>${L("전거 확인 필요", "Authorities to check")}</h3>` + r.to_lookup.map((t) => `<span class="chip" data-look="${esc(t.name)}" data-lang="${esc(t.lang || "")}">${esc(t.kind)}: ${esc(t.name)}</span>`).join(" ");
    if ((r.missing_fields || []).length) h += `<h3>${L("추가 권장 헤더 요소", "Recommended header elements")}</h3>` + r.missing_fields.map((f) => `<div class="rec"><b>${esc(f.label)}</b> <span class="k">${esc(f.level)} · ${esc(f.path)}</span><div class="hint">${esc(f.why)}</div></div>`).join("");
    $("#md-rec").innerHTML = h;
    $$("#md-rec [data-sug]").forEach((b) => (b.onclick = () => { const s = r.suggestions[+b.dataset.sug]; S.updateMetadata(s.patch); save(); render(); toast(L(`${s.key} 적용`, `${s.key} applied`)); }));
    $$("#md-rec [data-look]").forEach((c) => (c.onclick = () => { $("#wd-q").value = c.dataset.look; wd(c.dataset.lang); }));
  }
  async function wd(lang) {
    const q = $("#wd-q").value.trim(); if (!q) return; $("#wd-res").textContent = L("검색 중…", "Searching…");
    const r = await A.lookupAuthority(q, lang || (S.langs || ["en"])[0]);
    if (r.error) { $("#wd-res").textContent = r.error; return; }
    $("#wd-res").innerHTML = (r.candidates || []).map((c) => `<div class="rec"><b>${esc(c.label)}</b> <a href="${esc(c.uri)}" target="_blank" rel="noopener">${esc(c.qid)}</a><div>${esc(c.description)}</div><button data-qid="${esc(c.qid)}" data-uri="${esc(c.uri)}">${L("저자 전거로 지정", "Set as author authority")}</button></div>`).join("") || L("결과 없음", "No results");
    $$("#wd-res [data-qid]").forEach((b) => (b.onclick = () => {
      const a = S.metadata.authors && S.metadata.authors.length ? JSON.parse(JSON.stringify(S.metadata.authors)) : [{ name: q }];
      a[0] = { ...a[0], ref: b.dataset.uri, idnos: [...(a[0].idnos || []).filter((i) => i.type !== "wikidata"), { type: "wikidata", value: b.dataset.qid }] };
      S.updateMetadata({ authors: a }); save(); render(); toast(L("저자 전거를 추가했습니다", "Author authority added"));
    }));
  }
  $("#btn-wd").onclick = () => wd();
  $("#genre").onchange = (e) => { A.dispatch(S, "set_genre", { genre: e.target.value }); save(); render(); toast(L("장르 프로필을 바꿨습니다. 필요하면 추천을 다시 받으세요.", "Genre profile changed. Get new suggestions if needed.")); };

  /* ---------- gold data: few-shot examples + scoring */
  function renderGold() {
    const l = A.Gold.list();
    let bytes = 0; try { bytes = (localStorage.getItem(A.Gold.key) || "").length * 2; } catch (e) { /* ignore */ }
    $("#gold-size").textContent = l.length ? L(`${l.length}개 · 약 ${(bytes / 1e6).toFixed(2)} MB`, `${l.length} entries · ~${(bytes / 1e6).toFixed(2)} MB`) : "";
    $("#gold-from-session").disabled = !S;
    $("#gold-list").innerHTML = l.length ? l.map((g) => {
      const top = Object.entries(g.counts || {}).filter(([k]) => !["p", "div", "head"].includes(k)).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, v]) => `${k} ${v}`).join(", ");
      return `<div class="gold-item" data-g="${esc(g.id)}"><div><b>${esc(g.title)}</b> <span class="k">${esc(g.lang)} · ${esc(g.genre)} · ${g.blocks.length} ${L("블록", "blocks")}</span>
        <div class="hint">${esc(top)}${g.file ? ` · ${esc(g.file)}` : ""}</div></div>
        <div class="acts"><label class="hint"><input type="checkbox" data-act="use" ${g.use ? "checked" : ""}> ${L("예시로 사용", "use as example")}</label>
        <button type="button" data-act="eval" ${S ? "" : "disabled"}>${L("현재 문서와 비교", "Score current document")}</button>
        <button type="button" data-act="text">${L("원문으로 새 태깅", "Tag its text anew")}</button>
        <button type="button" data-act="del" class="danger">${L("삭제", "Delete")}</button></div></div>`;
    }).join("") : `<p class="hint">${L("아직 정답 데이터가 없습니다.", "No gold data yet.")}</p>`;
    $$("#gold-list .gold-item").forEach((el) => {
      const id = el.dataset.g;
      el.querySelector("[data-act=use]").onchange = (e) => { A.Gold.setUse(id, e.target.checked); toast(e.target.checked ? L("태깅 예시로 사용합니다", "Used as tagging example") : L("예시에서 뺐습니다", "No longer used as example")); };
      el.querySelector("[data-act=del]").onclick = () => { if (confirm(L("이 정답 데이터를 삭제할까요?", "Delete this gold entry?"))) { A.Gold.remove(id); renderGold(); } };
      el.querySelector("[data-act=text]").onclick = () => {
        const g = A.Gold.get(id); $("#dlg-gold").close();
        S = null; hideDone(); $("#ws").classList.add("hidden"); $("#start").classList.remove("hidden");
        $("#in-text").value = g.raw; $("#in-title").value = g.title; $("#in-lang").value = g.lang;
        toast(L("정답의 원문을 넣었습니다. 태깅 후 ‘📚 정답 데이터 → 현재 문서와 비교’로 점수를 확인하세요.", "Gold text loaded. After tagging, use ‘📚 Gold data → Score current document’."));
      };
      el.querySelector("[data-act=eval]").onclick = () => showEval(A.evaluateAgainstGold(S.blocks.map((b) => b.xml), A.Gold.get(id), S.registry));
    });
  }
  function showEval(r) {
    const f = (x) => x.map((v) => v.toFixed(2)).join(" / ");
    $("#gold-eval").innerHTML = `<h3>${L("평가", "Evaluation")}: ${esc(r.gold_title)}</h3>
      <p class="hint">${r.text_identical ? L("✓ 원문이 정답과 같습니다.", "✓ Text identical to the gold.") : L(`⚠ 원문이 정답과 다릅니다 (정답 ${r.text_chars.gold}자, 현재 ${r.text_chars.pred}자). 위치를 맞춰 비교했으니 수치는 참고용입니다.`, `⚠ Text differs from the gold (${r.text_chars.gold} vs ${r.text_chars.pred} chars); spans were aligned, treat scores as indicative.`)}
      ${r.who.compared ? L(` · 화자(@who) 일치 ${r.who.match}/${r.who.compared} = ${r.who.acc}`, ` · speaker (@who) agreement ${r.who.match}/${r.who.compared} = ${r.who.acc}`) : ""}</p>
      <table class="evtable"><tr><th>${L("요소", "element")}</th><th>${L("정답", "gold")}</th><th>${L("예측", "pred")}</th><th>${L("정확 일치 P / R / F1", "exact P / R / F1")}</th><th>${L("겹침 P / R / F1", "overlap P / R / F1")}</th></tr>
      ${r.rows.map((x) => `<tr><td>${esc(x.tag)}</td><td>${x.gold}</td><td>${x.pred}</td><td>${f(x.exact)}</td><td>${f(x.overlap)}</td></tr>`).join("")}
      <tr class="sum"><td>micro</td><td>${r.rows.reduce((a, x) => a + x.gold, 0)}</td><td>${r.rows.reduce((a, x) => a + x.pred, 0)}</td><td>${f(r.micro.exact)}</td><td>${f(r.micro.overlap)}</td></tr></table>
      <div class="row" style="margin-top:6px"><button type="button" id="eval-dl">${L("평가 결과 저장(.json)", "Save evaluation (.json)")}</button></div>`;
    $("#eval-dl").onclick = () => download(`${S ? fname() : "eval"}.eval.json`, JSON.stringify(r, null, 1), "application/json");
    S.log("evaluate", { gold: r.gold_title, micro: r.micro }); save();
    showDone(true, L("정답 비교 완료", "Evaluation finished"), L(`${r.gold_title} · 정확 일치 micro F1 ${r.micro.exact[2]} · 겹침 micro F1 ${r.micro.overlap[2]}`, `${r.gold_title} · exact micro F1 ${r.micro.exact[2]} · overlap micro F1 ${r.micro.overlap[2]}`));
    $("#gold-eval").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  $("#btn-gold").onclick = () => { $("#gold-eval").innerHTML = ""; renderGold(); $("#dlg-gold").showModal(); };
  $("#gold-files").onchange = async (e) => {
    const files = [...e.target.files]; e.target.value = ""; const ok = [], bad = [];
    for (const f of files) { try { A.Gold.add(A.Gold.fromTei(await f.text(), f.name)); ok.push(f.name); } catch (err) { bad.push(`${f.name}: ${err.message}`); } }
    renderGold();
    if (ok.length) showDone(!bad.length, L(`정답 데이터 ${ok.length}개 추가`, `${ok.length} gold file(s) added`), bad.length ? L("실패: ", "Failed: ") + bad.join(" / ") : ok.join(", "));
    else if (bad.length) toast(bad.join(" / "));
  };
  $("#gold-from-session").onclick = () => {
    if (!S) return;
    try { const g = A.Gold.add(A.Gold.fromSession(S, { title: ((S.metadata.titles || [{}])[0] || {}).text || "" })); renderGold(); toast(L(`‘${g.title}’을(를) 정답으로 추가했습니다`, `‘${g.title}’ added as gold`)); }
    catch (err) { toast(err.message); }
  };

  /* ---------- merge several TEI documents */
  let mergeDocs = [];
  function renderMerge() {
    $("#merge-list").innerHTML = mergeDocs.map((d, k) => `<li><div class="row"><span class="grow">${esc(d.name)}</span>
      <button type="button" data-up="${k}" ${k ? "" : "disabled"}>▲</button><button type="button" data-down="${k}" ${k < mergeDocs.length - 1 ? "" : "disabled"}>▼</button><button type="button" data-rm="${k}">✕</button></div></li>`).join("")
      || `<p class="hint">${L("아직 고른 문서가 없습니다.", "No documents selected yet.")}</p>`;
    $$("#merge-list [data-up]").forEach((b) => (b.onclick = () => { const k = +b.dataset.up; [mergeDocs[k - 1], mergeDocs[k]] = [mergeDocs[k], mergeDocs[k - 1]]; renderMerge(); }));
    $$("#merge-list [data-down]").forEach((b) => (b.onclick = () => { const k = +b.dataset.down; [mergeDocs[k + 1], mergeDocs[k]] = [mergeDocs[k], mergeDocs[k + 1]]; renderMerge(); }));
    $$("#merge-list [data-rm]").forEach((b) => (b.onclick = () => { mergeDocs.splice(+b.dataset.rm, 1); renderMerge(); }));
    $("#merge-add-current").disabled = !S; $("#merge-run").disabled = mergeDocs.length < 2;
  }
  $("#btn-merge").onclick = () => { $("#merge-msg").classList.add("hidden"); renderMerge(); $("#dlg-merge").showModal(); };
  $("#merge-files").onchange = async (e) => { for (const f of e.target.files) mergeDocs.push({ name: f.name, xml: await f.text() }); e.target.value = ""; renderMerge(); };
  $("#merge-add-current").onclick = () => { if (S) { mergeDocs.push({ name: L("(현재 문서) ", "(current) ") + fname(), xml: S.toXml()[0] }); renderMerge(); } };
  $("#merge-run").onclick = async () => {
    const mode = ($$("input[name=merge-mode]").find((r) => r.checked) || {}).value, title = $("#merge-title").value.trim(), msg = $("#merge-msg");
    msg.classList.add("hidden");
    try {
      if (mode === "single") {
        const r = A.mergeAsSession(mergeDocs, { title, divType: $("#merge-divtype").value.trim() || "chapter", settings: settings() });
        $("#dlg-merge").close(); mergeDocs = []; openSession(r.session); save();
        run(L("TEI 합치기", "Merging TEI"), async (p) => { p(L("합친 문서 검증 중", "validating merged document"), 0.4); await S.validate();
          return { merged: r.titles.length }; }).then(() => { if (r.renamed.length) toast(L(`겹친 id ${r.renamed.length}개 이름 변경: `, `${r.renamed.length} duplicate ids renamed: `) + r.renamed.slice(0, 5).join(", ")); });
      } else {
        const r = A.mergeAsCorpus(mergeDocs, { title });
        const v = await A.rngValidate(r.xml);
        const name = (title || r.titles.join("_")).replace(/[\\/:*?"<>|]/g, "_").slice(0, 80) || "corpus";
        download(`${name}.teiCorpus.xml`, r.xml, "application/xml");
        $("#dlg-merge").close(); mergeDocs = [];
        showDone(v.valid, v.valid ? L("TEI 합치기 완료 (teiCorpus)", "Merged into a teiCorpus") : L("teiCorpus를 저장했지만 스키마 오류가 있습니다", "teiCorpus saved, but it has schema errors"),
          L(`문서 ${r.titles.length}개 · 겹친 id ${r.renamed.length}개 이름 변경 · `, `${r.titles.length} documents · ${r.renamed.length} duplicate ids renamed · `)
          + (v.valid ? L("tei_all 검증 통과", "tei_all valid") : L(`오류 ${v.errors.length}건 (원본 문서의 오류일 수 있음): `, `${v.errors.length} errors (may come from the source files): `) + v.errors.slice(0, 2).map((e) => `line ${e.line}: ${e.message}`).join(" / ")));
      }
    } catch (err) { msg.textContent = err.message; msg.classList.remove("hidden"); }
  };

  /* ---------- project rules */
  function rememberRules(t) { try { localStorage.setItem("teiagent.rules", t || ""); } catch (e) { /* storage blocked */ } }
  function ruleCount() { const t = $("#in-rules").value.replace(/<!--[\s\S]*?-->/g, "").trim(); const n = t ? t.split("\n").filter((l) => l.trim()).length : 0; $("#rules-count").textContent = n ? L(`${n}줄 · 태깅 지시에 덧붙음`, `${n} lines · appended to tagging instructions`) : ""; }
  for (const [k, t] of Object.entries(A.PRESETS)) $("#rules-preset").add(new Option((t.split("\n")[0] || k).replace(/^#+\s*/, "").slice(0, 60), k));
  $("#rules-preset").onchange = (e) => { const k = e.target.value; if (k) { $("#in-rules").value = A.PRESETS[k]; ruleCount(); } e.target.value = ""; };
  $("#in-rules-file").onchange = async (e) => { const f = e.target.files[0]; if (f) { $("#in-rules").value = await f.text(); ruleCount(); } };
  $("#in-rules").oninput = ruleCount;
  try { $("#in-rules").value = localStorage.getItem("teiagent.rules") || ""; } catch (e) { /* ignore */ }
  $("#btn-rules-save").onclick = () => { if (!S) return; const r = S.setProjectRules($("#ws-rules").value); rememberRules(S.project_rules); save(); render(); toast(r.chars ? L(`지침 저장 (${r.chars}자). 이후 태깅·수정에 적용됩니다.`, `Rules saved (${r.chars} chars). Applied to later tagging and edits.`) : L("지침을 비웠습니다.", "Rules cleared.")); };
  $("#btn-rules-reapply").onclick = () => { if (!S) return; S.setProjectRules($("#ws-rules").value); rememberRules(S.project_rules);
    if (!S.project_rules) return toast(L("지침이 비어 있습니다.", "The rules are empty.")); run(L("지침으로 전체 다시 검토", "Re-checking against rules"), (p) => S.reapplyProjectRules(p)); };

  /* ---------- init */
  for (const [k, g] of Object.entries(A.GENRES)) { $("#in-genre").add(new Option(g.ko, k)); $("#genre").add(new Option(`${g.ko} (${k})`, k)); }
  tabs("left"); tabs("view"); tabs("side"); applyLang();
  window.__teiUI = { get session() { return S; }, run, setLang: (l) => { $("#ui-lang").value = l; $("#ui-lang").onchange({ target: $("#ui-lang") }); } };
})();
