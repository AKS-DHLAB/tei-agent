/* UI layer for the browser edition (same layout as the server version). */
"use strict";
(function () {
  const A = window.TEIAgent;
  const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let S = null, busy = false, lastErrBlocks = new Set();

  function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 4000); }
  function settings() { return A.Settings.load(); }
  function refreshBadges() {
    const st = settings();
    $("#b-tei").textContent = `TEI P5 ${A.TEI_VERSION}`;
    $("#b-model").textContent = `${st.model}${st.thinking ? " · thinking" : ""}${st.apiKey ? "" : " · 키 없음"}`;
    $("#b-model").classList.toggle("bad", !st.apiKey);
    $("#key-card").classList.toggle("hidden", !!st.apiKey);
    if (S) { S.s = st; S.llm.s = st; const u = S.llm.usageDict(); $("#b-model").title = `호출 ${u.calls}회, 입력 ${u.prompt_tokens}, 출력 ${u.completion_tokens} 토큰, ≈$${u.est_cost_usd_peak} (피크 단가)`; }
  }
  function tabs(group) {
    $$(`[data-tabs=${group}] button`).forEach((b) => (b.onclick = () => {
      $$(`[data-tabs=${group}] button`).forEach((x) => x.classList.toggle("on", x === b));
      [...b.parentElement.querySelectorAll("button")].map((x) => x.dataset.t).forEach((p) => $$(`[data-pane=${p}]`).forEach((el) => el.classList.toggle("hidden", p !== b.dataset.t)));
      if (b.dataset.t === "xml") renderXml();
    }));
  }
  function refreshSessionList() {
    const sel = $("#sess-list"); sel.length = 1;
    A.Store.list().forEach((s) => sel.add(new Option(`${s.title || s.id} · ${s.genre || ""} · ${s.saved.slice(5, 16).replace("T", " ")}`, s.id)));
  }
  function save() { if (S && !A.Store.save(S)) toast("브라우저 저장 공간이 부족합니다. '작업 파일 저장'으로 내려받아 두세요."); refreshSessionList(); }

  async function run(label, fn) {
    if (busy) return toast("다른 작업이 진행 중입니다.");
    busy = true; $("#job").classList.remove("hidden"); $("#job-msg").textContent = label; $("#job-bar").style.width = "3%";
    $$("main button, header button").forEach((b) => (b.disabled = true));
    const progress = (msg, frac) => { $("#job-msg").textContent = `${label} · ${msg}`; $("#job-bar").style.width = `${Math.round(frac * 100)}%`; };
    try { const r = await fn(progress); return r; }
    catch (e) { console.error(e); toast("오류: " + e.message); }
    finally {
      busy = false; $("#job").classList.add("hidden"); $$("main button, header button").forEach((b) => (b.disabled = false));
      if (S) { save(); render(); } refreshBadges();
    }
  }

  function openSession(s) {
    S = s; $("#start").classList.add("hidden"); $("#ws").classList.remove("hidden"); render(); refreshBadges();
  }

  /* ---------- start screen */
  $("#btn-key-save").onclick = () => { const st = settings(); st.apiKey = $("#key-inline").value.trim(); A.Settings.save(st); $("#key-inline").value = ""; refreshBadges(); toast(st.apiKey ? "키를 저장했습니다." : "키가 비어 있습니다."); };
  $("#btn-key-test").onclick = async () => {
    const st = settings(); const k = $("#key-inline").value.trim(); if (k) st.apiKey = k;
    if (!st.apiKey) { $("#key-status").textContent = "✗ 키가 없습니다. 이 주소에서는 키를 처음부터 다시 넣어야 합니다(파일로 열었을 때 저장한 키는 넘어오지 않음)."; return; }
    $("#key-status").textContent = "연결 확인 중…";
    try { const l = new A.LLM(st); const m = await l.chat([{ role: "system", content: 'Reply in json like {"ok":true}' }, { role: "user", content: "ping" }], { json: true, maxTokens: 50, retries: 1 });
      $("#key-status").textContent = "✓ DeepSeek 연결 성공" + (k ? " — 이제 ‘저장’을 누르세요." : ""); }
    catch (e) { $("#key-status").textContent = "✗ " + e.message; }
  };
  $("#in-file").onchange = async (e) => { const f = e.target.files[0]; if (f) $("#in-text").value = await f.text(); };
  $("#in-tei").onchange = async (e) => { const f = e.target.files[0]; if (!f) return; try { const s = A.Session.fromTei(await f.text()); openSession(s); save(); toast("불러왔습니다. '검증'으로 스키마 오류를 확인하세요."); } catch (err) { toast(err.message); } };
  $("#in-session").onchange = async (e) => { const f = e.target.files[0]; if (!f) return; try { openSession(A.Session.fromState(JSON.parse(await f.text()))); save(); } catch (err) { toast("작업 파일을 읽을 수 없습니다: " + err.message); } };
  $("#btn-start").onclick = () => {
    const text = $("#in-text").value; if (!text.trim()) return toast("텍스트를 입력하세요");
    if (!settings().apiKey) toast("API 키가 없어 휴리스틱 분석만 합니다. 키를 넣으면 자동 태깅이 됩니다.");
    const s = new A.Session(text, settings()); s.setProjectRules($("#in-rules").value); rememberRules($("#in-rules").value); openSession(s);
    const hints = { genre: $("#in-genre").value || null, lang: $("#in-lang").value || null };
    const title = $("#in-title").value.trim(), author = $("#in-author").value.trim(), auto = $("#in-auto").checked;
    run("분석·태깅", async (p) => {
      p("텍스트 분석 중", 0.05); await s.analyze(hints);
      if (title) s.metadata.titles = [{ text: title, type: "main", lang: s.langs[0] }];
      if (author) s.metadata.authors = [{ name: author }];
      render();
      if (auto && settings().apiKey) {
        p("인물·장소 레지스트리 구축 중", 0.1); await s.buildRegistry();
        await s.tagAll(p); p("추천 생성 중", 0.95); await s.recommendTags();
      }
    });
  };
  $("#sess-list").onchange = (e) => { const id = e.target.value; if (!id) return; const s = A.Store.load(id); if (s) openSession(s); else toast("작업을 불러올 수 없습니다."); e.target.value = ""; };
  $("#btn-new").onclick = () => { S = null; $("#ws").classList.add("hidden"); $("#start").classList.remove("hidden"); };

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
    toast(A.Settings.save(st) ? "설정을 저장했습니다." : "이 브라우저는 저장을 막고 있어 이번 창에서만 유지됩니다."); refreshBadges();
  };
  $("#s-clear").onclick = () => { const st = settings(); st.apiKey = ""; A.Settings.save(st); refreshBadges(); toast("키를 삭제했습니다."); };

  /* ---------- render */
  function render() {
    if (!S) return;
    const s = S.summary();
    if (document.activeElement !== $("#ws-rules")) $("#ws-rules").value = S.project_rules || "";
    $("#genre").value = S.genre; $("#analysis-notes").textContent = (S.analysis && S.analysis.notes) || "";
    const counts = Object.entries(s.tag_counts).filter(([k]) => k !== "p"), max = Math.max(1, ...counts.map((c) => c[1]));
    $("#counts").innerHTML = counts.slice(0, 18).map(([k, v]) => `<div class="bar"><span class="lbl">${esc(k)}</span><span class="track"><span class="fill" style="display:block;width:${(100 * v) / max}%"></span></span><span class="c">${v}</span></div>`).join("") || '<span class="hint">아직 태그가 없습니다.</span>';
    $("#bstat").textContent = Object.entries(s.block_status).map(([k, v]) => `${k}: ${v}`).join(" · ") + ` · 언어: ${(S.langs || []).join(", ")}`
      + (() => { const u = S.llm.usageDict(); return u.calls ? ` · 이번 세션 호출 ${u.calls}회, 입력 ${u.prompt_tokens}(캐시 ${u.cached_tokens}) · 출력 ${u.completion_tokens} 토큰 ≈ $${u.est_cost_usd_peak} (피크 단가 어림)` : ""; })();
    $("#hist").innerHTML = S.history.slice(-12).reverse().map((h) => `<div>${esc(h.when.slice(11, 16))} ${esc(h.action)}</div>`).join("");
    renderDoc(); renderRecs(); renderQs(); renderChat(); renderRegistry(); renderMetaForm(); renderMetaRecs(); showValidation(true);
    if (!$("[data-pane=xml]").classList.contains("hidden")) renderXml();
  }
  function xmlToHtml(node) {
    if (node.nodeType === 3) return esc(node.nodeValue);
    if (node.nodeType !== 1) return "";
    const n = node.localName; let attrs = "", tip = `<${n}`;
    for (const a of node.attributes) { attrs += ` data-${a.localName.replace(/[^a-z0-9-]/gi, "")}="${esc(a.value)}"`; tip += ` ${a.name}="${a.value}"`; }
    return `<span class="t t-${n}" title="${esc(tip + ">")}"${attrs}>${[...node.childNodes].map(xmlToHtml).join("")}</span>`;
  }
  function renderDoc() {
    const used = new Set(Object.keys(S.summary().tag_counts));
    $("#legend").innerHTML = ["persName", "placeName", "orgName", "rs", "date", "time", "measure", "said", "q", "foreign", "term", "title", "roleName", "name"].filter((t) => used.has(t)).map((t) => `<span class="t-${t}">${t}</span>`).join("");
    const parser = new DOMParser(); let html = "";
    for (const b of S.blocks) {
      if (b.div) html += `<div class="divmark">${esc(b.div.type)} ${esc(b.div.n ?? "")}</div>`;
      const d = parser.parseFromString(`<w xmlns="http://www.tei-c.org/ns/1.0">${b.xml}</w>`, "application/xml");
      const inner = d.getElementsByTagName("parsererror").length ? `<span class="w">XML 오류</span> ${esc(b.raw)}` : [...d.documentElement.childNodes].map(xmlToHtml).join("");
      html += `<div class="blk ${b.status === "fallback" ? "fallback" : ""} ${lastErrBlocks.has(b.i) ? "err" : ""}" data-i="${b.i}"><span class="n">${b.i}</span>${inner}${(b.warnings || []).length ? `<div class="w">⚠ ${esc(b.warnings.join(" / "))}</div>` : ""}</div>`;
    }
    $("#doc").innerHTML = html || '<p class="hint">블록이 없습니다.</p>';
    $$("#doc .blk").forEach((el) => (el.ondblclick = () => { $("#chat-in").value = `블록 ${el.dataset.i}: `; $("#chat-in").focus(); }));
  }
  function renderXml() {
    const x = S.toXml()[0];
    $("#xml").innerHTML = esc(x).replace(/(&lt;\/?)([\w:]+)/g, '$1<span class="x-tag">$2</span>').replace(/([\w:]+)=(&quot;.*?&quot;)/g, '<span class="x-att">$1</span>=<span class="x-val">$2</span>');
  }
  function download(name, text, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); }
  const fname = () => ((S.metadata.titles || [{}])[0].text || S.id).replace(/[\\/:*?"<>|]/g, "_");
  $("#btn-dl").onclick = () => download(`${fname()}.xml`, S.toXml()[0], "application/xml");
  $("#btn-save-json").onclick = () => { const d = S.state(); d.snapshots = S.snapshots.slice(-5); download(`${fname()}.teiagent.json`, JSON.stringify(d), "application/json"); };

  /* ---------- validation */
  $("#btn-validate").onclick = () => run("tei_all 검증", async (p) => { p("스키마 로딩·검증 중 (10~20초)", 0.3); await S.validate(); });
  $("#btn-repair").onclick = () => run("자동 수리", (p) => S.repair(p));
  $("#btn-undo").onclick = () => { toast("되돌림: " + S.undo()); save(); render(); };
  function showValidation(quiet) {
    const v = S.validation; if (!v || v.valid === undefined) { $("#val-status").textContent = "미검증"; $("#val-errors").classList.add("hidden"); return; }
    lastErrBlocks = new Set((v.errors || []).map((e) => e.block).filter((x) => x !== null && x !== undefined));
    const n = (v.errors || []).length;
    $("#val-status").innerHTML = v.valid ? `<span class="val-ok">✓ ${esc(v.schema || "valid")}</span>` : `<span class="val-bad">✗ 오류 ${n}건</span>` + ((v.dangling_refs || []).length ? ` · 미정의 ref ${v.dangling_refs.length}` : "");
    const ul = $("#val-errors"); ul.classList.toggle("hidden", !!v.valid);
    ul.innerHTML = (v.errors || []).slice(0, 40).map((e) => `<li>${e.block !== null && e.block !== undefined ? `[블록 ${e.block}] ` : ""}line ${e.line}: ${esc(e.message)}</li>`).join("");
    if (!quiet) renderDoc();
  }

  /* ---------- recommendations, questions, chat */
  function renderRecs() {
    const r = (S.recommendations && S.recommendations.tags) || [];
    if (!r.length) { $("#recs").innerHTML = '<span class="hint">아직 추천이 없습니다. “추천 다시 받기”를 누르세요.</span>'; return; }
    $("#recs").innerHTML = r.map((t) => `<div class="rec p${t.priority || 3}"><label><input type="checkbox" value="${esc(t.key)}" ${t.priority === 1 ? "checked" : ""}>
      <div><b>${esc(t.label)}</b> <span class="k">${esc((t.elements || []).join(", "))} · ~${esc(t.estimated_count ?? "?")}</span>
      <div>${esc(t.why || "")}</div>${(t.examples || []).length ? `<div class="ex">예: ${t.examples.slice(0, 3).map(esc).join(" / ")}</div>` : ""}</div></label></div>`).join("");
  }
  $("#btn-rec").onclick = () => run("태그 추천", () => S.recommendTags());
  $("#btn-accept").onclick = () => { const keys = $$("#recs input:checked").map((i) => i.value); if (!keys.length) return toast("적용할 태그를 선택하세요"); run("추천 태그 적용", (p) => S.acceptTags(keys, $("#rec-guide").value, p)); };
  function renderQs() {
    const qs = (S.questions || []).slice().sort((a, b) => (a.answered ? 1 : 0) - (b.answered ? 1 : 0));
    if (!qs.length) { $("#questions").innerHTML = '<span class="hint">열린 질문이 없습니다.</span>'; return; }
    $("#questions").innerHTML = qs.slice(0, 20).map((q) => `<div class="q ${q.answered ? "done" : ""}" data-q="${esc(q.id)}">
      <div>${esc(q.question)} ${q.block !== null && q.block !== undefined ? `<span class="hint">(블록 ${q.block})</span>` : ""}</div>
      ${q.about ? `<div class="hint">${esc(q.about)}</div>` : ""}
      ${q.answered ? `<div class="hint">→ ${esc(q.answer)}</div>` : `<div class="chips">${(q.options || []).map((o) => `<span class="chip" data-a="${esc(o)}">${esc(o)}</span>`).join("")}</div>
      <div class="row" style="margin-top:4px"><input type="text" class="grow" placeholder="직접 답변"><button>답변</button></div>`}</div>`).join("");
    $$("#questions .q").forEach((el) => {
      const id = el.dataset.q, go = (a) => run("답변 반영", (p) => S.answerQuestion(id, a, p));
      el.querySelectorAll(".chip").forEach((c) => (c.onclick = () => go(c.dataset.a)));
      const b = el.querySelector("button"); if (b) b.onclick = () => { const v = el.querySelector("input").value; if (v) go(v); };
    });
  }
  function renderChat() {
    // show the tools the agent actually called (transparency: what the harness did, not only what the model said)
    $("#chat").innerHTML = (S.chat || []).filter((m) => (m.role === "user" || m.role === "assistant") && (m.content || (m.tool_calls || []).length)).map((m) =>
      (m.tool_calls || []).length && !m.content ? `<div class="msg tool hint">🔧 ${m.tool_calls.map((c) => esc(c.function.name)).join(" · ")}</div>`
        : `<div class="msg ${m.role}">${esc(m.content)}</div>` + ((m.tool_calls || []).length ? `<div class="msg tool hint">🔧 ${m.tool_calls.map((c) => esc(c.function.name)).join(" · ")}</div>` : "")).join("");
    $("#chat").scrollTop = 1e9;
  }
  $("#btn-chat").onclick = () => {
    const t = $("#chat-in").value.trim(); if (!t) return; $("#chat-in").value = "";
    if ($("#chat-agent").checked) run("에이전트", (p) => A.agentChat(S, t, p));
    else { S.chat.push({ role: "user", content: t }); run("지시 반영", async (p) => { const r = await S.applyInstruction(t, p); S.chat.push({ role: "assistant", content: r.reply || "반영했습니다." }); }); }
  };
  $("#chat-in").onkeydown = (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("#btn-chat").click(); };

  /* ---------- registry */
  function renderRegistry() {
    let h = "";
    for (const [k, label] of [["persons", "인물"], ["places", "장소"], ["orgs", "기관"]]) {
      const l = S.registry[k] || []; if (!l.length) continue;
      h += `<h3>${label} (${l.length})</h3><table class="reg">${l.map((e) => `<tr><td><code>#${esc(e.id)}</code></td><td><span class="ed" data-k="${k}" data-id="${esc(e.id)}" style="cursor:text">${esc(e.name)}</span>${e.note ? `<div class="hint">${esc(e.note)}</div>` : ""}</td></tr>`).join("")}</table>`;
    }
    $("#registry").innerHTML = h || '<span class="hint">레지스트리가 비어 있습니다.</span>';
    $$("#registry .ed").forEach((el) => (el.onclick = () => { const v = prompt("이름 수정", el.textContent); if (!v) return; S.editEntity("update", el.dataset.k, el.dataset.id, { name: v }); save(); render(); }));
  }

  /* ---------- metadata */
  const MF = [["title", "제목", "titles.0.text"], ["subtitle", "부제", "titles.1.text"], ["author", "저자", "authors.0.name"], ["authorRef", "저자 URI", "authors.0.ref"],
    ["publisher", "발행처", "publication.publisher"], ["pubPlace", "발행지", "publication.pubPlace"], ["licence", "라이선스 URL", "licence.target"],
    ["source", "저본 서지", "sources.0.title"], ["sourceDate", "저본 연도", "sources.0.date"], ["sourceUrl", "저본 URL", "sources.0.idnos.0.value"],
    ["creation", "창작 시기", "creation.date"], ["series", "컬렉션", "series.title"], ["funder", "지원기관", "funder"], ["abstract", "초록", "abstract"]];
  const getp = (o, p) => p.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
  function renderMetaForm() { $("#meta-form").innerHTML = MF.map(([id, l, p]) => `<label for="m-${id}">${l}</label><input type="text" id="m-${id}" value="${esc(getp(S.metadata, p) ?? "")}">`).join(""); }
  $("#btn-md-save").onclick = () => {
    const md = JSON.parse(JSON.stringify(S.metadata || {}));
    const setp = (o, p, v) => { const ks = p.split("."); let a = o; ks.forEach((k, i) => { if (i === ks.length - 1) a[k] = v; else { if (a[k] == null) a[k] = /^\d+$/.test(ks[i + 1]) ? [] : {}; a = a[k]; } }); };
    for (const [id, , p] of MF) { const v = $(`#m-${id}`).value.trim(); if (v || getp(md, p) != null) setp(md, p, v || null); }
    if (md.titles) { md.titles = md.titles.filter((t) => t && t.text); md.titles.forEach((t, i) => (t.type = t.type || (i ? "sub" : "main"))); }
    if (md.sources && md.sources[0]) { md.sources[0].type = md.sources[0].type || "originalSource"; (md.sources[0].idnos || []).forEach((i) => (i.type = i.type || "URL")); }
    if (md.licence && md.licence.target && !md.licence.text) md.licence.text = md.licence.target;
    S.updateMetadata(md); save(); render(); toast("메타데이터를 저장했습니다");
  };
  $("#btn-md-rec").onclick = () => run("메타데이터 추천", () => S.recommendMetadata());
  function renderMetaRecs() {
    const r = S.meta_recommendations || {}; let h = "";
    if ((r.suggestions || []).length) h += "<h3>제안된 값</h3>" + r.suggestions.map((s, i) => `<div class="rec"><b>${esc(s.key)}</b> <span class="k">${esc(s.confidence || "")}</span>${s.needs_verification ? ` <span class="badge bad">${s.not_in_text ? "검증 필요 · 원문에 없는 값" : s.model_written ? "모델 작성 · 검토" : "검증 필요 · 모델 지식 기반"}</span>` : ""}${(s.identifiers_removed || []).length ? ' <span class="badge">ID 제거됨 → 전거 검색 사용</span>' : ""}
      ${(s.not_in_text || []).length ? `<div class="hint">원문에서 확인 안 됨: ${esc(s.not_in_text.join(", "))}</div>` : ""}
      <div class="k">${esc(JSON.stringify(s.patch))}</div><div>${esc(s.why || "")}</div><div class="hint">근거: ${esc(s.evidence || "")}</div><button data-sug="${i}" style="margin-top:4px">적용</button></div>`).join("");
    if ((r.to_lookup || []).length) h += "<h3>전거 확인 필요</h3>" + r.to_lookup.map((t) => `<span class="chip" data-look="${esc(t.name)}" data-lang="${esc(t.lang || "")}">${esc(t.kind)}: ${esc(t.name)}</span>`).join(" ");
    if ((r.missing_fields || []).length) h += "<h3>추가 권장 헤더 요소</h3>" + r.missing_fields.map((f) => `<div class="rec"><b>${esc(f.label)}</b> <span class="k">${esc(f.level)} · ${esc(f.path)}</span><div class="hint">${esc(f.why)}</div></div>`).join("");
    $("#md-rec").innerHTML = h;
    $$("#md-rec [data-sug]").forEach((b) => (b.onclick = () => { const s = r.suggestions[+b.dataset.sug]; S.updateMetadata(s.patch); save(); render(); toast(`${s.key} 적용`); }));
    $$("#md-rec [data-look]").forEach((c) => (c.onclick = () => { $("#wd-q").value = c.dataset.look; wd(c.dataset.lang); }));
  }
  async function wd(lang) {
    const q = $("#wd-q").value.trim(); if (!q) return; $("#wd-res").textContent = "검색 중…";
    const r = await A.lookupAuthority(q, lang || (S.langs || ["en"])[0]);
    if (r.error) { $("#wd-res").textContent = r.error; return; }
    $("#wd-res").innerHTML = (r.candidates || []).map((c) => `<div class="rec"><b>${esc(c.label)}</b> <a href="${esc(c.uri)}" target="_blank" rel="noopener">${esc(c.qid)}</a><div>${esc(c.description)}</div><button data-qid="${esc(c.qid)}" data-uri="${esc(c.uri)}">저자 전거로 지정</button></div>`).join("") || "결과 없음";
    $$("#wd-res [data-qid]").forEach((b) => (b.onclick = () => {
      const a = S.metadata.authors && S.metadata.authors.length ? JSON.parse(JSON.stringify(S.metadata.authors)) : [{ name: q }];
      a[0] = { ...a[0], ref: b.dataset.uri, idnos: [...(a[0].idnos || []).filter((i) => i.type !== "wikidata"), { type: "wikidata", value: b.dataset.qid }] };
      S.updateMetadata({ authors: a }); save(); render(); toast("저자 전거를 추가했습니다");
    }));
  }
  $("#btn-wd").onclick = () => wd();
  $("#genre").onchange = (e) => { A.dispatch(S, "set_genre", { genre: e.target.value }); save(); render(); toast("장르 프로필을 바꿨습니다. 필요하면 추천을 다시 받으세요."); };

  /* ---------- init */
  /* ---------- project rules */
  function rememberRules(t) { try { localStorage.setItem("teiagent.rules", t || ""); } catch (e) { /* storage blocked */ } }
  const ruleCount = () => { const t = $("#in-rules").value.replace(/<!--[\s\S]*?-->/g, "").trim(); $("#rules-count").textContent = t ? `${t.split("\n").filter((l) => l.trim()).length}줄 · 태깅 지시에 덧붙음` : ""; };
  for (const [k, t] of Object.entries(A.PRESETS)) $("#rules-preset").add(new Option((t.split("\n")[0] || k).replace(/^#+\s*/, "").slice(0, 60), k));
  $("#rules-preset").onchange = (e) => { const k = e.target.value; if (k) { $("#in-rules").value = A.PRESETS[k]; ruleCount(); } e.target.value = ""; };
  $("#in-rules-file").onchange = async (e) => { const f = e.target.files[0]; if (f) { $("#in-rules").value = await f.text(); ruleCount(); } };
  $("#in-rules").oninput = ruleCount;
  try { $("#in-rules").value = localStorage.getItem("teiagent.rules") || ""; } catch (e) { /* ignore */ }
  ruleCount();
  $("#btn-rules-save").onclick = () => { if (!S) return; const r = S.setProjectRules($("#ws-rules").value); rememberRules(S.project_rules); save(); render(); toast(r.chars ? `지침 저장 (${r.chars}자). 이후 태깅·수정에 적용됩니다.` : "지침을 비웠습니다."); };
  $("#btn-rules-reapply").onclick = () => { if (!S) return; S.setProjectRules($("#ws-rules").value); rememberRules(S.project_rules);
    if (!S.project_rules) return toast("지침이 비어 있습니다."); run("지침으로 전체 다시 검토", (p) => S.reapplyProjectRules(p)); };
  for (const [k, g] of Object.entries(A.GENRES)) { $("#in-genre").add(new Option(g.ko, k)); $("#genre").add(new Option(`${g.ko} (${k})`, k)); }
  tabs("left"); tabs("view"); refreshBadges(); refreshSessionList();
  window.__teiUI = { get session() { return S; }, run };
})();
