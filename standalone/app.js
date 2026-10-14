/* TEI Agent — browser edition. Port of the Python package (tei_agent/*) to a single HTML file.
 * Same rules (exported from Python at build time), same pipeline, same safeguards.
 * Network: DeepSeek API (user's own key, kept in this browser only) and Wikidata (on request). */
"use strict";
const D = JSON.parse(document.getElementById("tei-data").textContent);
const TEI_NS = "http://www.tei-c.org/ns/1.0";
const XML_NS = "http://www.w3.org/XML/1998/namespace";
const { TAGS, GENRES, LANG_RULES, METADATA_FIELDS, INDEX, EXEMPLARS, TEI_VERSION, APP_VERSION, MODEL_NAMES } = D;
/** A tag's language-neutral rule plus the examples for the document's languages only (mirror of profiles.tag_rule). */
function tagRule(k, langs = []) {
  const t = TAGS[k], ex = t.examples || {};
  const picks = [...new Set(langs.map((l) => String(l).split("-")[0]))].filter((l) => ex[l]).map((l) => `${l}: ${ex[l]}`);
  return t.rule + (picks.length ? ` Examples (${picks.join("; ")}).` : "");
}
const APP_NAME = "TEI-Agent";

/* ------------------------------------------------------------------ settings */
const Settings = {
  defaults: { apiKey: "", baseUrl: "https://api.deepseek.com", model: "deepseek-flash", thinking: false,
              reasoningEffort: "high", temperature: 0.1, chunkChars: 2500, maxWorkers: 4, maxTokens: 32000, uiLang: "ko" },
  load() {
    let s = {};
    try { s = JSON.parse(localStorage.getItem("teiagent.settings") || "{}"); } catch (e) { /* storage blocked */ }
    return Object.assign({}, this.defaults, s);
  },
  save(s) { try { localStorage.setItem("teiagent.settings", JSON.stringify(s)); return true; } catch (e) { return false; } },
};

/* ------------------------------------------------------------------ small utils */
const localIso = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString();
const nowIso = () => localIso().slice(0, 19);
const today = () => localIso().slice(0, 10);
const clone = (o) => JSON.parse(JSON.stringify(o));
const uid = () => Math.random().toString(16).slice(2, 12);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const escXml = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escAttr = (s) => escXml(s).replace(/"/g, "&quot;");
const norm = (s) => String(s).replace(/\s+/g, "");
const uniq = (a) => [...new Set(a)];

class LLMError extends Error {}

function parseJsonLoose(text) {
  if (!text) throw new LLMError("empty response");
  let t = text.trim().replace(/^```(?:json)?\s*|\s*```$/g, "");
  try { return JSON.parse(t); } catch (e) { /* fall through */ }
  const starts = [t.indexOf("{"), t.indexOf("[")].filter((i) => i >= 0);
  if (!starts.length) throw new LLMError("no JSON found: " + t.slice(0, 200));
  const st = Math.min(...starts);
  for (let end = t.length; end > st; end--) {
    if ("}]".includes(t[end - 1])) { try { return JSON.parse(t.slice(st, end)); } catch (e) { /* continue */ } }
  }
  throw new LLMError("could not parse JSON: " + t.slice(0, 200));
}

/* ------------------------------------------------------------------ LLM (DeepSeek, OpenAI-compatible) */
class LLM {
  constructor(settings) { this.s = settings; this.usage = { calls: 0, prompt_tokens: 0, completion_tokens: 0, cached_tokens: 0 }; }
  usageDict() {
    const u = this.usage, miss = Math.max(u.prompt_tokens - u.cached_tokens, 0);
    // peak-hour list prices for deepseek-flash, USD / 1M tokens (2026-10-12)
    return { ...u, est_cost_usd_peak: Math.round(((u.cached_tokens * 0.006 + miss * 0.3 + u.completion_tokens * 1.2) / 1e6) * 1e4) / 1e4 };
  }
  async chat(messages, { json = false, tools = null, maxTokens = null, thinking = null, retries = 3 } = {}) {
    if (!this.s.apiKey) throw new LLMError("DeepSeek API 키가 설정되지 않았습니다 (⚙ 설정).");
    thinking = thinking ?? this.s.thinking;
    const body = { model: this.s.model, messages, max_tokens: maxTokens || this.s.maxTokens,
                   thinking: { type: thinking ? "enabled" : "disabled" } };
    if (thinking) body.reasoning_effort = this.s.reasoningEffort; else body.temperature = this.s.temperature;
    if (json) body.response_format = { type: "json_object" };
    if (tools) body.tools = tools;
    let last;
    for (let a = 0; a < retries; a++) {
      try {
        const r = await fetch(this.s.baseUrl.replace(/\/$/, "") + "/chat/completions", {
          method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + this.s.apiKey },
          body: JSON.stringify(body) });
        if (r.status === 401) throw new LLMError("API 키가 올바르지 않습니다 (401).");
        if (r.status === 402) throw new LLMError("DeepSeek 계정 잔액이 부족합니다 (402). platform.deepseek.com에서 충전한 뒤 다시 시도하세요.");
        if (!r.ok) throw new Error(`HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
        const d = await r.json();
        const u = d.usage || {};
        this.usage.calls++; this.usage.prompt_tokens += u.prompt_tokens || 0;
        this.usage.completion_tokens += u.completion_tokens || 0; this.usage.cached_tokens += u.prompt_cache_hit_tokens || 0;
        const m = d.choices[0].message;
        const out = { role: "assistant", content: m.content || "" };
        if (m.reasoning_content) out.reasoning_content = m.reasoning_content;
        if (m.tool_calls && m.tool_calls.length) out.tool_calls = m.tool_calls.map((tc) => ({ id: tc.id, type: "function",
          function: { name: tc.function.name, arguments: tc.function.arguments } }));
        if (json && !out.content.trim()) throw new Error("empty JSON content");
        return out;
      } catch (e) {
        last = e;
        if (e instanceof LLMError) throw e;
        if (e instanceof TypeError) last = new Error("네트워크 오류 — 브라우저가 api.deepseek.com에 닿지 못했습니다. 인터넷 연결, 학교·기관 방화벽, 광고 차단 확장 프로그램, VPN을 확인하세요");
        await sleep(1500 * (a + 1));
      }
    }
    throw new LLMError(`DeepSeek 호출 실패 (${retries}회): ${last && last.message ? last.message : last}`);
  }
  async json(system, user, maxTokens) {
    let last;
    for (let k = 0; k < 2; k++) { // one fresh retry when the model returns malformed / truncated JSON
      const m = await this.chat([{ role: "system", content: system }, { role: "user", content: user }], { json: true, maxTokens });
      try { return parseJsonLoose(m.content); } catch (e) { last = e; }
    }
    throw last;
  }
}

async function pool(items, n, fn, onDone) {
  const results = new Array(items.length); let next = 0, done = 0;
  async function worker() {
    while (next < items.length) { const i = next++; results[i] = await fn(items[i], i); done++; onDone && onDone(done, items.length); }
  }
  await Promise.all(Array.from({ length: Math.max(1, Math.min(n, items.length)) }, worker));
  return results;
}

/* ------------------------------------------------------------------ XML helpers */
const EDITORIAL = new Set(["reg", "corr", "ex", "supplied", "note", "gloss", "rt"]);
const REMOVABLE_CHAR = /[\d\-–—_.\[\]()|pP·•*]/;
const lname = (el) => el.localName;
const domParser = new DOMParser();
const xmlSer = new XMLSerializer();
const stripNs = (s) => s.replace(/\s+xmlns(:\w+)?="[^"]+"/g, "");

function parseFragment(xml) {
  const doc = domParser.parseFromString(`<wrap xmlns="${TEI_NS}">${xml}</wrap>`, "application/xml");
  const err = doc.getElementsByTagName("parsererror")[0];
  if (err) { const e = new Error("XML not well-formed: " + err.textContent.split("\n")[0].slice(0, 160)); e.xml = true; throw e; }
  return doc.documentElement;
}
function sourceText(el) {
  const out = [];
  (function rec(node, skip) {
    for (const ch of node.childNodes) {
      if (ch.nodeType === 3 || ch.nodeType === 4) { if (!skip) out.push(ch.nodeValue); }
      else if (ch.nodeType === 1) {
        const n = lname(ch), p = ch.parentNode;
        const ed = EDITORIAL.has(n) || (n === "expan" && p && p.localName === "choice");
        rec(ch, skip || ed);
      }
    }
  })(el, false);
  return out.join("");
}
function innerXml(el) {
  let s = "";
  for (const ch of el.childNodes) s += ch.nodeType === 1 ? xmlSer.serializeToString(ch) : ch.nodeType === 3 ? escXml(ch.nodeValue) : "";
  return stripNs(s);
}
const plainP = (raw, tag = "p") => `<${tag}>${escXml(raw.trim())}</${tag}>`;

/** Text preservation: only tag insertion allowed; optional tolerated removal of page-number-like snippets. */
function checkPreservation(raw, xml, allowRemovals = false) {
  let frag;
  try { frag = parseFragment(xml); } catch (e) { return { ok: false, problems: [e.message], removed: [] }; }
  const a = norm(raw), b = norm(sourceText(frag));
  if (a === b) return { ok: true, problems: [], removed: [] };
  const removed = [];
  if (allowRemovals) {
    let i = 0, j = 0, ok = true;
    while (i < a.length || j < b.length) {
      if (i < a.length && j < b.length && a[i] === b[j]) { i++; j++; continue; }
      let k = i;
      while (k < a.length && k - i < 14 && REMOVABLE_CHAR.test(a[k]) && !(j < b.length && a[k] === b[j] && k > i)) k++;
      if (k > i && (j >= b.length ? k === a.length : a[k] === b[j])) { removed.push(a.slice(i, k)); i = k; continue; }
      ok = false; break;
    }
    if (ok) return { ok: true, problems: [], removed };
  }
  let p = 0; while (p < a.length && p < b.length && a[p] === b[p]) p++;
  let s = 0; while (s < a.length - p && s < b.length - p && a[a.length - 1 - s] === b[b.length - 1 - s]) s++;
  const src = a.slice(p, a.length - s), out = b.slice(p, b.length - s);
  const op = !out ? "delete" : !src ? "insert" : "replace";
  return { ok: false, removed, problems: [`${op}: source '${src.slice(0, 60)}' -> output '${out.slice(0, 60)}' (context: …${a.slice(Math.max(0, p - 12), p + 24)}…)`] };
}
function elementCounts(xmls) {
  const c = {};
  for (const x of xmls) {
    let f; try { f = parseFragment(x); } catch (e) { continue; }
    for (const el of f.getElementsByTagName("*")) c[lname(el)] = (c[lname(el)] || 0) + 1;
  }
  return Object.fromEntries(Object.entries(c).sort((x, y) => y[1] - x[1]));
}
function refsIn(xmls) {
  const out = new Set();
  for (const x of xmls) for (const m of x.matchAll(/\b(?:ref|who|corresp|sameAs)="([^"]+)"/g))
    for (const t of m[1].split(/\s+/)) if (t.startsWith("#")) out.add(t.slice(1));
  return out;
}

/* ------------------------------------------------------------------ numerals (Korean/Han → Arabic) */
const NUMERIC = /^-?(\d+(\.\d+)?([eE][-+]?\d+)?|\d+\/\d+)$/;
const NUMERIC_ATTRS = new Set(["quantity", "atLeast", "atMost", "min", "max"]);
const SINO_D = { 영: 0, 공: 0, 일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 륙: 6, 칠: 7, 팔: 8, 구: 9, "〇": 0, 零: 0, 一: 1, 二: 2, 三: 3,
  四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 壹: 1, 貳: 2, 參: 3 };
const SINO_U = { 십: 10, 백: 100, 천: 1000, 十: 10, 百: 100, 千: 1000, 拾: 10 };
const BIG = { 만: 1e4, 억: 1e8, 萬: 1e4, 億: 1e8 };
const NATIVE = { 하나: 1, 한: 1, 둘: 2, 두: 2, 셋: 3, 세: 3, 석: 3, 서: 3, 넷: 4, 네: 4, 넉: 4, 너: 4, 다섯: 5, 닷: 5, 여섯: 6, 엿: 6, 일곱: 7, 여덟: 8, 아홉: 9 };
const NATIVE_T = { 열: 10, 스물: 20, 스무: 20, 서른: 30, 마흔: 40, 쉰: 50, 예순: 60, 일흔: 70, 여든: 80, 아흔: 90 };
function sino(s) {
  let total = 0, section = 0, digit = null;
  for (const ch of s) {
    if (ch in SINO_D) { if (digit !== null) return null; digit = SINO_D[ch]; }
    else if (ch in SINO_U) { section += (digit ?? 1) * SINO_U[ch]; digit = null; }
    else if (ch in BIG) { section += digit || 0; total += (section || 1) * BIG[ch]; section = 0; digit = null; }
    else return null;
  }
  return total + section + (digit || 0);
}
function nativeNum(s) {
  let val = 0, rest = s;
  for (const [w, n] of Object.entries(NATIVE_T).sort((a, b) => b[0].length - a[0].length)) if (rest.startsWith(w)) { val = n; rest = rest.slice(w.length); break; }
  if (rest) { if (rest in NATIVE) val += NATIVE[rest]; else return null; }
  return val || null;
}
function toArabic(v) {
  v = String(v).trim().replace(/,/g, "");
  if (NUMERIC.test(v)) return v;
  if (!v) return null;
  let n = nativeNum(v); if (n === null) n = sino(v);
  return n === null ? null : String(n);
}

/* ------------------------------------------------------------------ schema knowledge (TEI 4.12.0) */
const COMMON = new Set(INDEX.common);
const ISO_DATE_ATTRS = new Set(["when", "from", "to", "notBefore", "notAfter"]);
const ISO = /^-?\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01])(T([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$|^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$|^--(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?$|^---(0[1-9]|[12]\d|3[01])$/; // month 01-12, day 01-31, 24h time
const elementExists = (n) => n in INDEX.elements;
const attrAllowed = (el, a) => COMMON.has(a) || (INDEX.elements[el] || []).includes(a);
function badValue(el, att, val) {
  const v = String(val).trim();
  if (ISO_DATE_ATTRS.has(att)) return !ISO.test(v) || v.replace(/^-+/, "").startsWith("0000");
  if (NUMERIC_ATTRS.has(att) || (att === "value" && el === "num")) return !NUMERIC.test(v);
  return false;
}
function fixDate(v) {
  const m = /^0000-(\d{2})(-(\d{2}))?$/.exec(String(v).trim());
  return m ? (m[3] ? `--${m[1]}-${m[3]}` : `--${m[1]}`) : null;
}
const attName = (a) => (a.namespaceURI === XML_NS ? "xml:" + a.localName : a.localName);
function quickCheck(fragment) {
  let root; try { root = parseFragment(fragment); } catch (e) { return ["not well-formed: " + e.message]; }
  const issues = new Set();
  for (const el of root.getElementsByTagName("*")) {
    const n = lname(el);
    if (!elementExists(n)) { issues.add(`<${n}> is not a TEI element`); continue; }
    for (const a of el.attributes) {
      const an = attName(a);
      if (an === "xmlns" || an.startsWith("xmlns:")) continue;
      if (!attrAllowed(n, an)) issues.add(`@${an} is not allowed on <${n}>`);
      else if (badValue(n, an, a.value)) issues.add(`@${an}="${a.value}" on <${n}> has an invalid value (dates: ISO 8601; numbers: Arabic numerals)`);
    }
  }
  return [...issues].sort();
}
function stripDisallowed(fragment) {
  const root = parseFragment(fragment), log = [];
  for (const el of [...root.getElementsByTagName("*")]) {
    const n = lname(el);
    if (!elementExists(n)) { log.push(`unwrapped <${n}>`); while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el); el.remove(); continue; }
    for (const a of [...el.attributes]) {
      const an = attName(a);
      if (an === "xmlns" || an.startsWith("xmlns:")) continue;
      if (attrAllowed(n, an) && badValue(n, an, a.value)) {
        const conv = ISO_DATE_ATTRS.has(an) ? fixDate(a.value) : toArabic(a.value);
        if (conv !== null) { log.push(`@${an}: "${a.value}" → "${conv}" on <${n}>`); a.value = conv; continue; }
      }
      if (!attrAllowed(n, an) || badValue(n, an, a.value)) { log.push(`removed @${an}="${a.value}" from <${n}>`); el.removeAttributeNode(a); }
    }
  }
  return [innerXml(root), log];
}
function attributeCheatsheet(elements) {
  const glob = new Set(INDEX.cheatsheet_globals);
  return uniq(elements).sort().filter(elementExists).map((e) => {
    const all = [...INDEX.common, ...INDEX.elements[e]];
    const spec = all.filter((a) => !glob.has(a) && !a.endsWith("-iso") && !a.endsWith("-custom")).sort();
    const vals = Object.entries(INDEX.values[e] || {}).filter(([a]) => ["type", "unit", "aloud", "direct", "calendar", "reason", "place"].includes(a))
      .map(([a, v]) => `${a}∈{${v.join(",")}}`);
    return `- ${e}: ${spec.length ? "@" + spec.join(" @") : "(globals only)"}` + (vals.length ? `  [${vals.join("; ")}]` : "");
  }).join("\n");
}

/* ------------------------------------------------------------------ full RELAX NG validation (xmllint → wasm, in a worker) */
let WASM_BYTES = null, WORKER_URL = null;
function rngValidate(xml) {
  if (!WASM_BYTES) {
    const b64 = document.getElementById("xmllint-wasm").textContent.trim();
    const bin = atob(b64); WASM_BYTES = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) WASM_BYTES[i] = bin.charCodeAt(i);
    WORKER_URL = URL.createObjectURL(new Blob([document.getElementById("xmllint-worker").textContent], { type: "text/javascript" }));
  }
  const rng = document.getElementById("tei-all-rng").textContent;
  return new Promise((resolve, reject) => {
    const w = new Worker(WORKER_URL);
    w.onmessage = (ev) => {
      const d = ev.data; if (!d || d["xmllint-wasm"] !== true) return;
      w.terminate();
      if (d.exitCode !== 0 && d.exitCode !== 3 && d.exitCode !== 4) return reject(new Error(d.stderr || "xmllint error " + d.exitCode));
      const errors = d.stderr.split("\n").filter((l) => l.startsWith("doc.xml:")).map((l) => {
        const [, line, ...rest] = l.split(":");
        const msg = rest.join(":").replace(/^.*?Relax-NG validity error\s*:\s*/, "").replace(/^\s*parser error\s*:\s*/, "").trim();
        return { line: parseInt(line, 10), message: msg };
      });
      resolve({ wellformed: !/parser error/.test(d.stderr), valid: d.exitCode === 0, errors: errors.slice(0, 200), schema: `tei_all ${TEI_VERSION}` });
    };
    w.onerror = (e) => { w.terminate(); reject(new Error("validation worker failed: " + (e.message || e))); };
    w.postMessage({ "xmllint-wasm": true, inputFiles: [{ fileName: "doc.xml", contents: xml }, { fileName: "tei_all.rng", contents: rng }],
      args: ["--relaxng", "tei_all.rng", "--noout", "doc.xml"], initialMemory: 256, maxMemory: 16384, wasmBinary: WASM_BYTES });
  });
}

/* ------------------------------------------------------------------ heuristics */
const PAT = Object.fromEntries(Object.entries(D.PATTERNS).map(([k, [p, f]]) => [k, new RegExp(p, f)]));
function scriptProfile(text) {
  const c = {}; let total = 0;
  for (const ch of text) {
    if (!/\p{L}/u.test(ch)) continue;
    const cp = ch.codePointAt(0);
    const k = (cp >= 0xac00 && cp <= 0xd7a3) || (cp >= 0x1100 && cp <= 0x11ff) || (cp >= 0x3130 && cp <= 0x318f) ? "Hangul"
      : (cp >= 0x4e00 && cp <= 0x9fff) || (cp >= 0x3400 && cp <= 0x4dbf) || (cp >= 0x20000 && cp <= 0x2ebef) ? "Han"
      : cp >= 0x3040 && cp <= 0x30ff ? "Kana" : (cp >= 0x370 && cp <= 0x3ff) || (cp >= 0x1f00 && cp <= 0x1fff) ? "Greek"
      : cp >= 0x400 && cp <= 0x4ff ? "Cyrillic" : /\p{Script=Latin}/u.test(ch) ? "Latin" : "Other";
    c[k] = (c[k] || 0) + 1; total++;
  }
  return Object.fromEntries(Object.entries(c).sort((a, b) => b[1] - a[1]).map(([k, v]) => [k, Math.round((100 * v) / (total || 1))]));
}
function signals(text) {
  const out = {};
  for (const [k, rx] of Object.entries(PAT)) {
    rx.lastIndex = 0;
    const ms = [...text.matchAll(rx)];
    if (ms.length) out[k] = { count: ms.length, examples: ms.slice(0, 4).map((m) => m[0].slice(0, 80)) };
  }
  const lines = text.split("\n").filter((l) => l.trim());
  if (lines.length) out._short_line_ratio = { count: Math.round((100 * lines.filter((l) => l.trim().length < 45).length) / lines.length), examples: [] };
  return out;
}
function guess(text) {
  const sp = scriptProfile(text), sig = signals(text);
  let main = "en";
  if ((sp.Hangul || 0) > 20) main = "ko"; else if ((sp.Kana || 0) > 5) main = "ja"; else if ((sp.Han || 0) > 50) main = "lzh";
  else if ((sp.Greek || 0) > 50) main = "grc";
  else if ((sp.Latin || 0) > 50) {
    const toks = text.toLowerCase().match(/[a-zà-ÿß]+/g) || [];
    const stop = { en: "the and of to i was in on my you sir yours is it that", de: "und der die das nicht ich ist zu mit sie ein eine",
      fr: "et le la les une est je il que de des du", la: "et est cum ad non sed quod qui atque enim vixit annis" };
    const sc = Object.fromEntries(Object.entries(stop).map(([l, w]) => { const s = new Set(w.split(" ")); return [l, toks.filter((t) => s.has(t)).length]; }));
    main = Object.entries(sc).sort((a, b) => b[1] - a[1])[0][1] ? Object.entries(sc).sort((a, b) => b[1] - a[1])[0][0] : "en";
  }
  let genre = "prose_fiction";
  if (sig.letter_open || sig.letter_close) genre = "correspondence";
  else if ((sig.speaker_colon?.count || 0) > 5) genre = sig.act_scene || sig.stage_paren ? "drama" : "speech_transcript";
  else if ((sig._short_line_ratio?.count || 0) > 70 && text.length < 20000 && text.split("\n").length > 8) genre = "poetry";
  else if ((sig.gap_marks?.count || 0) > 3 && text.length < 3000) genre = "inscription";
  let langs = [{ ident: main, label: main, usage: 100 }];
  if (main === "ko" && (sp.Han || 0) >= 1) langs = [{ ident: "ko", label: "Korean", usage: 100 - sp.Han }, { ident: "ko-Hani", label: "Korean in Han script", usage: sp.Han }];
  return { main_lang: main, languages: langs, genre, genre_confidence: 0.3, scripts: sp, title: null, author: null, structure: {}, notes: "offline heuristic analysis" };
}

/* ------------------------------------------------------------------ prompts (mirror of tei_agent/prompts.py) */
const LANG_NAME = { ko: "Korean", en: "English", de: "German", fr: "French", ja: "Japanese", zh: "Chinese" };
const ui = (l) => LANG_NAME[l] || l;
const ROLE = `You are an expert digital-humanities encoder who applies the TEI P5 Guidelines version ${TEI_VERSION} (released 2026-07-28; schema tei_all) to multilingual humanities texts. You produce valid, conservative, scholarly markup and you never alter the source text.`;
const J = (o) => JSON.stringify(o);
const P = {
  analyze: (u) => `${ROLE}
Task: analyse a raw text before encoding. Reply in json only, with this shape:
{"languages":[{"ident":"BCP-47 tag e.g. ko, ko-Hani, lzh, en, de, fr, la, grc, ja","label":"name in ${ui(u)}","usage":percent_int}],
 "main_lang":"BCP-47","genre":"one of the keys below","genre_confidence":0.0-1.0,
 "period":"approximate date of composition or null","title":"title if stated or inferable, else null",
 "author":"author if stated, else null","structure":{"divisions":"how chapters/sections/acts/entries are marked, or null",
 "division_type":"chapter|section|act|scene|entry|letter|poem|article|null","has_dialogue":bool,"dialogue_markers":["“”", "「」", "colon after speaker", ...],
 "verse":bool,"page_numbers":bool,"letter_parts":bool,"speaker_labels":bool},
 "notes":"one or two sentences in ${ui(u)} describing the text and encoding challenges"}
Genre keys:
${Object.entries(GENRES).map(([k, v]) => `- ${k}: ${v.en} / ${v.ko}`).join("\n")}`,
  registry: (u, genre) => `${ROLE}
Task: build an entity registry for consistent cross-references in the whole document (genre: ${genre}).
List every person/character (including unnamed but recurring ones such as "나", "the narrator", "the old man"),
place and organisation that is mentioned. Reply in json only:
{"persons":[{"id":"ASCII xml:id, letter first, short & mnemonic (e.g. JS, LHS, emilia)","name":"canonical name as in text",
  "variants":["other forms used in text: nicknames, titles, kinship terms, pronoun cues"],"sex":"M|F|U or null",
  "role":"protagonist|antagonist|minor|historical|speaker|author|addressee|null","note":"one short ${ui(u)} line"}],
 "places":[{"id":"...","name":"...","variants":[],"type":"country|city|district|building|natural|fictional|null","note":"..."}],
 "orgs":[{"id":"...","name":"...","variants":[],"type":"...","note":"..."}]}
Rules: ids are unique across all three lists; do not invent entities not in the text; never add external
identifiers (Wikidata, VIAF …) — those are looked up and verified separately.`,
  tag: ({ genre, tagKeys, langRules, cheatsheet, exemplars, registry, extra = "", u = "ko", pageNumbers = false, langs = [] }) => {
    const g = GENRES[genre];
    const pageRule = pageNumbers ? 'Exception: this text contains printed page numbers; a standalone page number may become <pb n="…"/>.'
      : 'This text has NO page numbers: a number standing alone as a block is a section/chapter heading → <head>1</head> (and set "div"); never turn it into <pb/>.';
    const rules = tagKeys.filter((k) => TAGS[k]).map((k) => `- ${tagRule(k, langs)}`).join("\n");
    return `${ROLE}
Task: insert TEI markup into numbered source blocks. Genre profile: ${g.en}. ${g.notes}

HARD CONSTRAINTS
1. Text preservation: every character of each source block (letters, punctuation, quotation marks, brackets, spaces
   between words) must appear in your output in the same order. You ONLY add tags. Never correct, translate,
   normalise, summarise or drop text. ${pageRule}
   Editorial additions are allowed only inside <reg>, <corr>, <expan> (in <choice>), <ex>, <supplied>, <note>.
2. Output one item per input block, same index. Each item's "xml" is one or more block-level elements
   (p, head, lg, sp, stage, u, opener, closer, postscript, list, quote, ab, castList, entry, floatingText, note …).
3. Use ONLY these markup categories now:
${rules}
4. Use ONLY attributes valid in TEI ${TEI_VERSION}. Allowed non-global attributes for the elements in play:
${cheatsheet}
   Global attributes allowed everywhere: xml:id, xml:lang, n, rend, ana, corresp, sameAs, cert, resp, source.
5. Entity references: @ref/@who must point to an id in the registry ("#id"). If you meet a new recurring entity,
   invent a new id and list it in "new_entities". Do not put @ref on elements that do not allow it.
6. Uncertain decisions: still tag, add cert="low", and add a short question in "uncertain" written in ${ui(u)}.
7. Divisions: if a block starts a new chapter/section/act/scene/entry/letter, set "div" for that block
   ({"type":"chapter","n":"1","level":1}); its heading goes in <head>. Otherwise "div": null.
   Never write <div> tags yourself inside "xml" — the div field creates them.
   A title line at the very start → <head>; an author line directly under it → <byline><docAuthor>…</docAuthor></byline>;
   a date/place line of a letter or entry → <dateline>.
8. Language rules: ${langRules}
${extra}
ENTITY REGISTRY (id → name; variants):
${registry}

${exemplars}

Reply in json only:
{"blocks":[{"i":0,"div":null,"xml":"<p>…</p>"}],
 "new_entities":[{"kind":"person|place|org","id":"…","name":"…","note":"…"}],
 "uncertain":[{"i":0,"text":"tagged span","question":"short question to the human encoder, in ${ui(u)}"}]}`;
  },
  tagUser: (blocks, ctx = "") => "Encode these blocks (json):\n" + J({ context_before_do_not_tag: ctx ? ctx.slice(-600) : "", blocks: blocks.map((b) => ({ i: b.i, text: b.raw })) }),
  repairUser: (items) => 'Your previous output for these blocks had problems. Fix ONLY the listed problems, keep all other markup, and reply in json {"blocks":[{"i":…,"xml":"…"}]}.\n' + J(items),
  plan: (u) => `${ROLE}
You turn a user's instruction about an ongoing TEI encoding into an executable plan. Reply in json only:
{"kind":"retag|metadata|entity|answer|mixed",
 "tag_keys":["catalog keys to ADD to the active tagset (may be empty)"],
 "remove_tag_keys":["catalog keys to remove"],
 "elements":["explicit TEI element names mentioned, if any"],
 "scope":"all|blocks|search","block_ids":[],"search":["literal strings that identify affected blocks"],
 "retag_instruction":"precise English instruction for the block re-encoder, or empty",
 "metadata_patch":{} ,
 "entity_ops":[{"op":"add|update|merge|delete","kind":"person|place|org","id":"…","data":{},"into":"id for merge"}],
 "reply":"short confirmation for the user in ${ui(u)}"}
metadata_patch uses the metadata JSON model (keys like titles, authors, publication, licence, sources, creation,
languages, keywords, abstract, editorial, resp, corresp, calendars, msDesc, recording, series, funder).
Tag catalog keys:
${Object.entries(TAGS).map(([k, v]) => `- ${k}: ${v.ko} — ${v.rule.slice(0, 90)}`).join("\n")}`,
  retag: (base, instruction) => base + `

REVISION MODE: you receive blocks that are ALREADY encoded ("xml"). Apply this instruction and return the full
revised xml for every block you were given (unchanged blocks may be returned as-is):
INSTRUCTION: ${instruction}
Keep existing correct markup. The underlying text must stay identical.`,
  retagUser: (blocks) => "Revise these encoded blocks (json):\n" + J({ blocks: blocks.map((b) => ({ i: b.i, xml: b.xml })) }),
  recTags: (u, genre, cands, langs = []) => `${ROLE}
Recommend ADDITIONAL TEI markup that would add scholarly value to this ${GENRES[genre].en} text, choosing only from
the candidate catalog below, and ask the human encoder the questions needed to encode precisely.
Base each recommendation on concrete evidence in the text (quote short examples verbatim). Reply in json only:
{"tags":[{"key":"catalog key","why":"${ui(u)}, 1-2 sentences on research value","examples":["verbatim snippet", "..."],
  "estimated_count":int,"priority":1|2|3}],
 "questions":[{"id":"q1","question":"${ui(u)}","options":["…","…"],"about":"catalog key or topic"}]}
priority 1 = strongly recommended. At most 8 tags, at most 4 questions (e.g. ambiguous speakers, Hanja language tag
ko-Hani vs lzh, whether to encode pronoun coreference, calendar of dates).
Candidate catalog:
${cands.map((k) => `- ${k}: ${TAGS[k].ko} — ${tagRule(k, langs)}`).join("\n")}`,
  recMeta: (u, genre) => `${ROLE}
You enrich the TEI header. Given the current metadata JSON, the text analysis and text excerpts, (a) propose concrete
VALUES you can justify from the text or from well-established bibliographic knowledge, and (b) recommend which further
header fields are worth adding, with a reason. NEVER output identifiers (Wikidata QIDs, VIAF, ISNI, GND, URIs of
authority records) — put every person/place/work that needs one in "to_lookup"; the tool verifies identifiers itself.
Mark each suggestion's basis: "text" if the value is stated in the given text, "knowledge" if it comes from your
background knowledge (these will be shown to the user as needing verification). Reply in json only:
{"suggestions":[{"key":"field key","patch":{ metadata JSON fragment to merge },"evidence":"quote from the text or the reference you rely on",
   "basis":"text|knowledge","confidence":"high|medium|low","why":"${ui(u)}"}],
 "to_lookup":[{"kind":"author|place|org|work","name":"…","lang":"…"}],
 "questions":[{"id":"m1","question":"${ui(u)}","field":"key","options":[]}]}
Metadata JSON model examples:
 titles:[{"text":"…","type":"main|sub|alt","lang":"ko"}]; authors:[{"name":"…","lang":"ko"}]
 sources:[{"type":"originalSource|digitalSource","title":"…","level":"a|m|j","author":"…","publisher":"…","pubPlace":"…","date":"1936","when":"1936-05","biblScope":[{"unit":"page","from":"1","to":"20"}],"idnos":[{"type":"URL","value":"…"}]}]
 creation:{"date":"…","when":"YYYY"}; licence:{"target":"https://creativecommons.org/licenses/by/4.0/","text":"CC BY 4.0"}
 keywords:[{"scheme":"https://www.wikidata.org/","terms":[{"text":"…","ref":"…"}]}]; editorial:{"normalization":"…","quotation":"…"}
 corresp:[{"type":"sent","person":"…","place":"…","when":"YYYY-MM-DD"}]; calendars:[{"id":"lunar","desc":"…"}]
 msDesc:{"repository":"…","idno":"…","material":"…","origDate":"…"}; recording:{"type":"audio","date":"…","place":"…","dur":"PT1H"}
Fields for this genre (key (level): path — label):
${METADATA_FIELDS.filter((f) => f.genres === "*" || f.genres.includes(genre)).map((f) => `- ${f.key} (${f.level}): ${f.path} — ${f.ko}`).join("\n")}`,
  agent: (u) => `${ROLE}
You are the conversational front-end of an interactive TEI tagging workbench. The user is a humanities researcher.
Write every message in ${ui(u)}, including short notes before tool calls. Use the tools to inspect and modify the current document; never claim a change you did not make
with a tool. Ask a clarifying question when an instruction is ambiguous instead of guessing. Keep answers short;
cite element names in backticks.

Working loop for every correction the user asks for:
1. MEASURE first with find_markup (e.g. persName whose text ends in 장로; said without @aloud) so you know the scale.
2. DECIDE the scope. If the user states a general convention ("직함으로 부르면 rs", "생각은 aloud=false", "한자는 zh"),
   it must also hold for all future tagging: call set_project_rules (mode "append", one short imperative line, in the
   user's words) and tell the user it was added to the project rules. A one-off fix ("이 문단의 그는 영채") is NOT a rule.
3. APPLY with apply_instruction. Restrict the scope with concrete search strings when the rule concerns specific words
   (cheaper and safer); use reapply_project_rules only when the user wants the whole text re-checked.
4. VERIFY with find_markup again and report before/after numbers and 2–3 examples. If the change did not take, say so
   and propose the next step. Text preservation and schema validity are enforced by code; do not try to bypass them.
Typical first turn after automatic tagging: report what was tagged, suggest further elements (recommend_tags) and
header enrichments (recommend_metadata), then validate when the user is done.`,
};

/* ------------------------------------------------------------------ exemplars */
function selectExemplars(genre, langs, preferred, k = 2) {
  // mirror of exemplars.select (0.1.3): slot 1 = same genre (same language first); slot 2 = the document's language
  // (only same genre + language if slot 1 already has the language). User gold marked "use" outranks bundled exemplars.
  langs = langs.map((l) => String(l).split("-")[0]);
  const pool = [...Gold.list().filter((g) => g.use).map((g) => Gold.asExemplar(g)), ...EXEMPLARS];
  const pref = (d) => (preferred.includes(d.id) ? 1 - 0.05 * preferred.indexOf(d.id) : 0), user = (d) => (d.user ? 2 : 0);
  const best = (c, score) => c.reduce((a, d) => (a === null || score(d) > score(a) ? d : a), null);
  const first = best(pool.filter((d) => d.genre === genre), (d) => (langs.includes(d.lang) ? 3 : 0) + user(d) + pref(d));
  if (!first && GENRES[genre] && GENRES[genre].exemplar_fallback === false) return [];
  const second = first && langs.includes(first.lang)
    ? best(pool.filter((d) => d !== first && d.genre === genre && langs.includes(d.lang)), (d) => user(d) + pref(d))
    : best(pool.filter((d) => d !== first && langs.includes(d.lang)), (d) => (d.genre === genre ? 3 : 0) + user(d) + pref(d));
  return [first, second].filter(Boolean).slice(0, k);
}
const formatExemplar = (d, max = 2200) => `### Exemplar \`${d.id}\` (${d.lang}, ${d.genre}; ${d.licence}; ${d.citation})
Raw input (excerpt):
${d.raw_input.slice(0, max / 2)}

Expert TEI encoding (excerpt, may be truncated):
${d.tei_body.slice(0, max)}
${d.user ? "This is the PROJECT'S OWN GOLD ENCODING supplied by the encoders: follow its element choices, span boundaries and attribute conventions closely.\n" : ""}NOTE: exemplars show conventions, not an attribute allow-list. Some legacy exemplar attributes (e.g. said/@mode, measure/@ref, rs/@sex) are INVALID in TEI 4.12 — never copy them.`;

/* ------------------------------------------------------------------ authority (Wikidata) */
async function wikidataSearch(name, lang = "en", limit = 5) {
  const q = new URLSearchParams({ action: "wbsearchentities", search: name, language: lang.split("-")[0], uselang: lang.split("-")[0],
    limit, format: "json", type: "item", origin: "*" });
  const r = await fetch("https://www.wikidata.org/w/api.php?" + q);
  if (!r.ok) throw new Error("HTTP " + r.status);
  const d = await r.json();
  return (d.search || []).map((x) => ({ qid: x.id, label: x.label, description: x.description || "", uri: `http://www.wikidata.org/entity/${x.id}` }));
}
async function lookupAuthority(name, lang = "en", kind = "") {
  try {
    let res = await wikidataSearch(name, lang);
    if (!res.length && lang !== "en") res = await wikidataSearch(name, "en");
    return { query: name, kind, candidates: res, note: "Candidates only — confirm the right QID before adding it to the header." };
  } catch (e) { return { query: name, kind, candidates: [], error: "Wikidata not reachable: " + e.message }; }
}
const AUTH_HOSTS = ["wikidata.org", "viaf.org", "isni.org", "d-nb.info", "orcid.org", "id.loc.gov", "geonames.org"];
const AUTH_TYPES = new Set(["wikidata", "viaf", "isni", "gnd", "orcid", "lccn", "geonames"]);
function stripIdentifiers(obj, found = [], ctx = "") {
  if (Array.isArray(obj)) return obj.map((x) => stripIdentifiers(x, found, ctx));
  if (obj && typeof obj === "object") {
    const name = obj.name || obj.text || ctx, out = {};
    for (const [k, v] of Object.entries(obj)) {
      if (["ref", "sameAs", "uri"].includes(k) && typeof v === "string" && AUTH_HOSTS.some((h) => v.includes(h))) { found.push([name, v]); continue; }
      if (k === "idnos" && Array.isArray(v)) {
        const keep = v.filter((i) => !(i && AUTH_TYPES.has(String(i.type || "").toLowerCase())));
        v.filter((i) => !keep.includes(i)).forEach((i) => found.push([name, i.value]));
        if (keep.length) out[k] = keep; continue;
      }
      if (["wikidata", "viaf", "isni"].includes(k)) { found.push([name, v]); continue; }
      out[k] = stripIdentifiers(v, found, name);
    }
    return out;
  }
  return obj;
}

/* ------------------------------------------------------------------ header builder (mirror of header.py) */
const N = (tag, text = null, attrs = {}, ...kids) => ({ tag, text: text === null || text === undefined || text === "" ? null : String(text), attrs, kids: kids.filter(Boolean) });
function ser(n, ind = "") {
  const at = Object.entries(n.attrs || {}).filter(([, v]) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length))
    .map(([k, v]) => ` ${k}="${escAttr(v)}"`).join("");
  if (!n.kids.length) return n.text === null ? `${ind}<${n.tag}${at}/>` : `${ind}<${n.tag}${at}>${escXml(n.text)}</${n.tag}>`;
  return `${ind}<${n.tag}${at}>${n.text ? escXml(n.text) : ""}\n` + n.kids.map((k) => ser(k, ind + "  ")).join("\n") + `\n${ind}</${n.tag}>`;
}
const idnos = (p, list) => (list || []).forEach((i) => i && i.value && p.kids.push(N("idno", i.value, { type: i.type })));
const names = (p, tag, list) => (list || []).forEach((n) => { if (typeof n === "string") n = { text: n }; if (n && n.text) p.kids.push(N(tag, n.text, { "xml:lang": n.lang, type: n.type })); });
const paras = (p, text, tag = "p") => { if (text) String(text).split(/\n\s*\n/).filter((t) => t.trim()).forEach((t) => p.kids.push(N(tag, t.trim()))); };
function bibl(src) {
  const b = N("bibl", null, { type: src.type, "xml:lang": src.lang });
  (src.titles || (src.title ? [{ text: src.title, level: src.level }] : [])).forEach((t) => b.kids.push(N("title", t.text, { level: t.level, "xml:lang": t.lang })));
  (src.authors || (src.author ? [src.author] : [])).forEach((a) => { a = typeof a === "string" ? { name: a } : a; b.kids.push(N("author", a.name, { ref: a.ref })); });
  for (const k of ["editor", "publisher", "pubPlace"]) if (src[k]) b.kids.push(N(k, src[k]));
  if (src.date || src.when) b.kids.push(N("date", src.date || src.when, { when: src.when }));
  (src.biblScope || []).forEach((sc) => b.kids.push(N("biblScope", sc.text, { unit: sc.unit, from: sc.from, to: sc.to })));
  idnos(b, src.idnos); if (src.note) b.kids.push(N("note", src.note));
  return b;
}
function person(p) {
  const el = N("person", null, { "xml:id": p.id, role: p.role, sex: p.sex, gender: p.gender, age: p.age, sameAs: p.sameAs });
  names(el, "persName", p.names || (p.name ? [p.name] : []));
  if (p.birth) el.kids.push(N("birth", p.birth.text, { when: p.birth.when, where: p.birth.where }));
  if (p.death) el.kids.push(N("death", p.death.text, { when: p.death.when, where: p.death.where }));
  if (p.occupation) el.kids.push(N("occupation", p.occupation));
  idnos(el, p.idnos); if (p.note) el.kids.push(N("note", p.note));
  return el;
}
function placeEl(p) {
  const el = N("place", null, { "xml:id": p.id, type: p.type }); names(el, "placeName", p.names || (p.name ? [p.name] : []));
  if (p.geo) el.kids.push(N("location", null, {}, N("geo", p.geo))); idnos(el, p.idnos); if (p.note) el.kids.push(N("note", p.note)); return el;
}
function orgEl(o) {
  const el = N("org", null, { "xml:id": o.id, type: o.type }); names(el, "orgName", o.names || (o.name ? [o.name] : []));
  idnos(el, o.idnos); if (o.note) el.kids.push(N("note", o.note)); return el;
}
function buildHeader(md, { tagCounts = null, registryLocation = "standOff", model = "deepseek-flash", stats = null } = {}) {
  const mname = MODEL_NAMES[model] || model, d = today();
  const h = N("teiHeader", null, { "xml:lang": md.header_lang });
  const fd = N("fileDesc"), ts = N("titleStmt");
  (md.titles && md.titles.length ? md.titles : [{ text: md.title || "[제목 미상 / Untitled]", type: "main" }]).forEach((t) => ts.kids.push(N("title", t.text, { type: t.type, "xml:lang": t.lang })));
  (md.authors || []).forEach((a) => { a = typeof a === "string" ? { name: a } : a; const el = N("author", null, { ref: a.ref }); names(el, "persName", a.names || [{ text: a.name, lang: a.lang }]); idnos(el, a.idnos); ts.kids.push(el); });
  (md.editors || []).forEach((e) => { e = typeof e === "string" ? { name: e } : e; ts.kids.push(N("editor", e.name, { role: e.role, ref: e.ref })); });
  if (md.funder) ts.kids.push(N("funder", md.funder));
  (md.resp || []).forEach((r) => { const rs = N("respStmt", null, { "xml:id": r.id }); rs.kids.push(N("resp", r.resp || r.role)); const nm = N("name", r.name, { ref: r.ref }); idnos(nm, r.idnos); rs.kids.push(nm); ts.kids.push(rs); });
  ts.kids.push(N("respStmt", null, { "xml:id": "teiagent" }, N("resp", "Automatic TEI encoding (LLM-assisted), subject to human review"), N("name", `${APP_NAME} ${APP_VERSION} (browser) with ${mname}`)));
  fd.kids.push(ts);
  if (md.edition) fd.kids.push(N("editionStmt", null, {}, N("edition", md.edition)));
  if (stats) { const ext = N("extent"); Object.entries(stats).forEach(([u, q]) => ext.kids.push(N("measure", `${q} ${u}`, { unit: u, quantity: q }))); fd.kids.push(ext); }
  const pub = md.publication || {}, ps = N("publicationStmt");
  ps.kids.push(N("publisher", pub.publisher || "[발행처 미상]"));
  if (pub.pubPlace) ps.kids.push(N("pubPlace", pub.pubPlace));
  ps.kids.push(N("date", pub.date || d, { when: pub.when || (pub.date ? null : d) }));
  idnos(ps, pub.idnos);
  const lic = md.licence || {};
  if (lic.target || lic.text || pub.availability) {
    const av = N("availability", null, { status: lic.status });
    if (lic.target || lic.text) av.kids.push(N("licence", lic.text || lic.target, { target: lic.target }));
    paras(av, pub.availability); ps.kids.push(av);
  }
  fd.kids.push(ps);
  if (md.series) { const st = N("seriesStmt"); st.kids.push(N("title", md.series.title)); idnos(st, md.series.idnos); fd.kids.push(st); }
  if (md.notes && md.notes.length) fd.kids.push(N("notesStmt", null, {}, ...md.notes.map((n) => N("note", n))));
  const sd = N("sourceDesc");
  (md.sources || []).forEach((s) => sd.kids.push(bibl(s)));
  if (md.msDesc) {
    const m = md.msDesc, ms = N("msDesc"), ident = N("msIdentifier");
    for (const k of ["country", "settlement", "institution", "repository", "collection"]) if (m[k]) ident.kids.push(N(k, m[k]));
    ident.kids.push(N("idno", m.idno || "[청구기호 미상]")); ms.kids.push(ident);
    if (m.material || m.dimensions || m.condition || m.objectType) {
      const sdesc = N("supportDesc", null, { material: m.material }), sup = N("support");
      paras(sup, [m.material, m.dimensions].filter(Boolean).join(" ")); sdesc.kids.push(sup);
      if (m.condition) { const c = N("condition"); paras(c, m.condition); sdesc.kids.push(c); }
      ms.kids.push(N("physDesc", null, {}, N("objectDesc", null, { form: m.objectType }, sdesc)));
    }
    if (m.origDate || m.origPlace || m.provenance) {
      const hist = N("history"), orig = N("origin");
      if (m.origPlace) orig.kids.push(N("origPlace", m.origPlace));
      if (m.origDate) orig.kids.push(N("origDate", m.origDate, { when: m.origWhen, notBefore: m.notBefore, notAfter: m.notAfter }));
      hist.kids.push(orig); if (m.provenance) { const pv = N("provenance"); paras(pv, m.provenance); hist.kids.push(pv); }
      ms.kids.push(hist);
    }
    sd.kids.push(ms);
  }
  if (md.recording) {
    const r = md.recording, rec = N("recording", null, { type: r.type || "audio", dur: r.dur });
    const t = [r.date, r.place, r.equipment].filter(Boolean).join(" "); if (t) rec.kids.push(N("p", t));
    sd.kids.push(N("recordingStmt", null, {}, rec));
  }
  if (!sd.kids.length) sd.kids.push(N("p", md.source_note || "Born-digital transcription supplied by the user; source not yet described."));
  fd.kids.push(sd); h.kids.push(fd);
  const ed = N("encodingDesc"), pd = N("projectDesc");
  paras(pd, md.project_desc || `Encoded according to the TEI P5 Guidelines ${TEI_VERSION} (tei_all) with LLM-assisted tagging and interactive human refinement.`);
  ed.kids.push(pd);
  if (md.sampling) { const sm = N("samplingDecl"); paras(sm, md.sampling); ed.kids.push(sm); }
  const edl = Object.assign({ normalization: "Original orthography and punctuation preserved; no silent normalisation.",
    quotation: "Quotation marks retained in the text, outside <said>/<q>." }, md.editorial || {});
  const edEl = N("editorialDecl");
  for (const k of ["correction", "normalization", "quotation", "hyphenation", "segmentation", "interpretation"]) if (edl[k]) { const s = N(k); paras(s, edl[k]); edEl.kids.push(s); }
  ed.kids.push(edEl);
  if (tagCounts) ed.kids.push(N("tagsDecl", null, {}, N("namespace", null, { name: TEI_NS }, ...Object.entries(tagCounts).map(([gi, n]) => N("tagUsage", null, { gi, occurs: n })))));
  if (md.taxonomies) ed.kids.push(N("classDecl", null, {}, ...md.taxonomies.map((tx) => N("taxonomy", null, { "xml:id": tx.id }, ...(tx.categories || []).map((c) => N("category", null, { "xml:id": c.id }, N("catDesc", c.desc)))))));
  ed.kids.push(N("appInfo", null, {}, N("application", null, { ident: APP_NAME, version: APP_VERSION, when: d, "xml:id": "app-teiagent" },
    N("label", `${APP_NAME} browser edition (LLM: ${mname}; schema: tei_all ${TEI_VERSION})`))));
  h.kids.push(ed);
  const pr = N("profileDesc");
  if (md.abstract) { const ab = N("abstract"); paras(ab, md.abstract); pr.kids.push(ab); }
  const cr = md.creation || {};
  if (Object.keys(cr).length) {
    const c = N("creation");
    if (cr.date || cr.when) c.kids.push(N("date", cr.date || cr.when, { when: cr.when, notBefore: cr.notBefore, notAfter: cr.notAfter }));
    if (cr.place) c.kids.push(N("placeName", cr.place));
    if (c.kids.length) pr.kids.push(c);
  }
  if ((md.languages || []).length) pr.kids.push(N("langUsage", null, {}, ...md.languages.map((l) => N("language", l.label || l.ident, { ident: l.ident, usage: l.usage }))));
  if ((md.keywords || []).length || md.genre_label) {
    const tc = N("textClass");
    if (md.genre_label) tc.kids.push(N("keywords", null, { scheme: "#teiagent-genre" }, N("term", md.genre_label)));
    (md.keywords || []).forEach((k) => tc.kids.push(N("keywords", null, { scheme: k.scheme }, ...(k.terms || []).map((t) => { t = typeof t === "string" ? { text: t } : t; return N("term", t.text, { ref: t.ref, "xml:lang": t.lang }); }))));
    pr.kids.push(tc);
  }
  if (md.corresp) pr.kids.push(N("correspDesc", null, {}, ...md.corresp.map((a) => { const ca = N("correspAction", null, { type: a.type });
    if (a.person) ca.kids.push(N("persName", a.person, { ref: a.person_ref })); if (a.place) ca.kids.push(N("placeName", a.place, { ref: a.place_ref }));
    if (a.date || a.when) ca.kids.push(N("date", a.date, { when: a.when })); return ca; })));
  if (md.calendars) pr.kids.push(N("calendarDesc", null, {}, ...md.calendars.map((c) => { const ce = N("calendar", null, { "xml:id": c.id }); paras(ce, c.desc); return ce; })));
  const persons = md.persons || [];
  if (registryLocation === "particDesc" && persons.length) pr.kids.push(N("particDesc", null, {}, N("listPerson", null, {}, ...persons.map(person))));
  if (md.setting) { const sdsc = N("settingDesc"); paras(sdsc, typeof md.setting === "string" ? md.setting : Object.values(md.setting).join(" ")); pr.kids.push(sdsc); }
  if (pr.kids.length) h.kids.push(pr);
  const rv = N("revisionDesc");
  (md.revisions || []).forEach((c) => rv.kids.push(N("change", c.text, { when: c.when, who: c.who })));
  if (!rv.kids.length) rv.kids.push(N("change", "Automatic TEI encoding generated; awaiting human review.", { when: d, who: "#teiagent" }));
  h.kids.push(rv);
  const so = N("standOff");
  if (registryLocation !== "particDesc" && persons.length) so.kids.push(N("listPerson", null, {}, ...persons.map(person)));
  if ((md.places || []).length) so.kids.push(N("listPlace", null, {}, ...md.places.map(placeEl)));
  if ((md.orgs || []).length) so.kids.push(N("listOrg", null, {}, ...md.orgs.map(orgEl)));
  if ((md.relations || []).length) so.kids.push(N("listRelation", null, {}, ...md.relations.map((r) => N("relation", null, { name: r.name, active: r.active, passive: r.passive, mutual: r.mutual }))));
  return [ser(h), so.kids.length ? ser(so) : null];
}

/* ------------------------------------------------------------------ session (mirror of pipeline.py) */
const METADATA_KEYS = new Set(["titles", "authors", "editors", "resp", "funder", "edition", "publication", "licence", "series", "notes", "sources", "msDesc",
  "recording", "project_desc", "sampling", "editorial", "taxonomies", "abstract", "creation", "languages", "keywords", "corresp", "calendars", "setting",
  "persons", "places", "orgs", "relations", "source_note"]);
const FACTUAL_KEYS = new Set(["titles", "authors", "editors", "creation", "sources", "publication", "series", "msDesc", "recording", "corresp", "funder", "edition"]);
const INTERPRETIVE_KEYS = new Set(["abstract", "keywords", "setting", "project_desc", "editorial"]);
const GROUNDED_OK = new Set(["languages", "persons", "places", "orgs"]);
const CJ = /[぀-ヿ㐀-鿿]/;
function unwrapLines(u) {
  if (!u.includes("\n")) return u;
  const parts = u.split("\n").map((l) => l.trim()).filter(Boolean);
  let out = parts[0] || "";
  for (const l of parts.slice(1)) out += (out && CJ.test(out.slice(-1)) && CJ.test(l[0]) ? "" : " ") + l;
  return out;
}
function unwrapDiv(xml) {
  let f; try { f = parseFragment(xml); } catch (e) { return [xml, null]; }
  const kids = [...f.children];
  if (kids.length === 1 && lname(kids[0]) === "div" && !sourceTextOutside(f, kids[0]).trim())
    return [innerXml(kids[0]).trim(), { type: kids[0].getAttribute("type") || "section", n: kids[0].getAttribute("n"), level: 1 }];
  return [xml, null];
}
const sourceTextOutside = (f, el) => [...f.childNodes].filter((n) => n !== el && n.nodeType === 3).map((n) => n.nodeValue).join("");
function deepMerge(base, patch) {
  const out = clone(base || {});
  for (const [k, v] of Object.entries(patch || {})) {
    if (v === null) delete out[k];
    else if (v && typeof v === "object" && !Array.isArray(v) && out[k] && typeof out[k] === "object" && !Array.isArray(out[k])) out[k] = deepMerge(out[k], v);
    else out[k] = clone(v);
  }
  return out;
}
const tagsFor = (keys) => uniq(keys.flatMap((k) => (TAGS[k] ? TAGS[k].elements : []))).sort();

const STATE_KEYS = ["id", "created", "raw_text", "project_rules", "analysis", "genre", "langs", "tagset", "registry", "metadata", "blocks", "header_override",
  "standoff_override", "extra_ids", "recommendations", "meta_recommendations", "questions", "history", "chat", "validation", "status", "usage"];

const nospace = (t) => String(t || "").replace(/\s+/g, "");
const stripParen = (t) => String(t || "").replace(/\s*[(（][^)）]*[)）]/g, "");
function registryLines(reg) {
  const out = [];
  for (const [k, lab] of [["persons", "PERSON"], ["places", "PLACE"], ["orgs", "ORG"]])
    for (const e of reg[k] || []) out.push(`${lab} #${e.id} = ${e.name}` + ((e.variants || []).length ? ` (also: ${(e.variants || []).slice(0, 6).join(", ")})` : ""));
  return out.join("\n");
}
const GENERIC_FORMS = new Set(D.GENERIC_FORMS || []); // kinship terms/titles by language (profiles.GENERIC_FORMS_BY_LANG)
function projectRulesBlock(rules, forRegistry = false) {
  // the encoders' own conventions; never override text preservation or schema validity (both also enforced by code)
  rules = String(rules || "").replace(/<!--[\s\S]*?-->/g, "").trim();
  if (!rules) return "";
  if (forRegistry) return "PROJECT RULES (the encoders' conventions; follow them when building ids/recommendations):\n" + rules + "\n\n";
  return "9. PROJECT RULES — conventions decided by this project's encoders. Where they conflict with the general rules above (3 and 8), follow the PROJECT RULES; they never override 1 (text preservation) or 4 (valid attributes).\n" + rules + "\n";
}
const isFatal = (e) => /\((401|402)\)/.test(String(e && e.message));
class Session {
  constructor(raw = "", settings = Settings.load(), sid = null) {
    this.s = settings; this.llm = new LLM(settings);
    this.id = sid || uid(); this.created = nowIso();
    this.raw_text = raw.replace(/\r\n?/g, "\n");
    this.analysis = {}; this.genre = "generic"; this.langs = []; this.tagset = [];
    this.registry = { persons: [], places: [], orgs: [] }; this.metadata = {}; this.blocks = [];
    this.extra_ids = []; this.header_override = null; this.standoff_override = null; this.project_rules = "";
    this.recommendations = {}; this.meta_recommendations = {}; this.questions = []; this.history = []; this.chat = [];
    this.snapshots = []; this.validation = {}; this.status = "new"; this.usage = null;
  }
  state() { const d = {}; for (const k of STATE_KEYS) d[k] = this[k]; d.usage = this.llm.usageDict(); return d; }
  static fromState(d, settings = Settings.load()) {
    const s = new Session(d.raw_text || "", settings, d.id);
    for (const k of STATE_KEYS) if (k in d && k !== "usage") s[k] = d[k];
    s.snapshots = d.snapshots || [];
    if (d.usage) Object.assign(s.llm.usage, { calls: d.usage.calls || 0, prompt_tokens: d.usage.prompt_tokens || 0, completion_tokens: d.usage.completion_tokens || 0, cached_tokens: d.usage.cached_tokens || 0 });
    return s;
  }
  snapshot(label) { this.snapshots.push(JSON.stringify({ label, blocks: this.blocks, registry: this.registry, metadata: this.metadata, tagset: this.tagset })); this.snapshots = this.snapshots.slice(-15); }
  undo() {
    if (!this.snapshots.length) return "되돌릴 작업이 없습니다";
    const d = JSON.parse(this.snapshots.pop());
    Object.assign(this, { blocks: d.blocks, registry: d.registry, metadata: d.metadata, tagset: d.tagset });
    this.log("undo", d.label); return d.label;
  }
  log(action, detail) { this.history.push({ when: nowIso(), action, detail }); }
  pageNumbers() { return !!((this.analysis.structure || {}).page_numbers); }

  async analyze(hints = {}) {
    const h = guess(this.raw_text);
    const sample = this.raw_text.slice(0, 7000) + (this.raw_text.length > 9000 ? "\n…\n" + this.raw_text.slice(-1500) : "");
    let a;
    try { a = await this.llm.json(P.analyze(this.s.uiLang), `Script profile (%): ${J(h.scripts)}\nUser hints: ${J(hints)}\n\nTEXT:\n${sample}`, 2000); }
    catch (e) { a = h; a.notes = `LLM 분석 불가 (${e.message}); 휴리스틱 추정 사용.`; }
    a.scripts = h.scripts; a.signals = signals(this.raw_text);
    if (hints.genre && GENRES[hints.genre]) a.genre = hints.genre;
    if (hints.lang) a.main_lang = hints.lang;
    this.analysis = a;
    this.genre = GENRES[a.genre] ? a.genre : "generic";
    this.langs = (a.languages || []).map((l) => l.ident).filter(Boolean);
    if (!this.langs.length) this.langs = [a.main_lang || "en"];
    this.tagset = [...GENRES[this.genre].core];
    const md = this.metadata;
    if (a.title && !md.titles) md.titles = [{ text: a.title, type: "main", lang: a.main_lang }];
    if (a.author && !md.authors) md.authors = [{ name: a.author, lang: a.main_lang }];
    if (a.languages && !md.languages) md.languages = a.languages;
    if (a.period && !md.creation) md.creation = { date: a.period };
    if (!md.genre_label) md.genre_label = GENRES[this.genre].en;
    this.blocks = this.segment(); this.status = "analyzed";
    this.log("analyze", { genre: this.genre, langs: this.langs, blocks: this.blocks.length });
    return a;
  }
  segment() {
    const text = this.raw_text.replace(/^\n+|\n+$/g, "");
    const paras_ = text.split(/\n\s*\n/).filter((p) => p.trim()), lines = text.split("\n").filter((l) => l.trim());
    const verse = ["poetry", "drama"].includes(this.genre);
    let units;
    if (verse) units = paras_.length >= 2 ? paras_ : lines;
    else if (["speech_transcript", "dictionary"].includes(this.genre) || paras_.length < Math.max(2, lines.length / 8)) units = lines;
    else units = paras_;
    return units.map((u, i) => { u = u.replace(/^\n+|\n+$/g, ""); if (!verse) u = unwrapLines(u);
      return { i, raw: u.trim(), xml: plainP(u), div: null, status: "raw", warnings: [] }; });
  }
  async buildRegistry() {
    // whole text in consecutive windows; each window sees the ids already registered (one cast list per work)
    const text = this.raw_text, W = 60000, windows = [];
    for (let k = 0; k < Math.max(text.length, 1); k += W) windows.push(text.slice(k, k + W));
    const merged = { persons: [], places: [], orgs: [] }, seen = new Set();
    for (let w = 0; w < windows.length; w++) {
      const known = registryLines(merged);
      const user = projectRulesBlock(this.project_rules, true) + (known ? "ALREADY REGISTERED (reuse these ids; list only entities NOT yet registered, or an existing id with new variants):\n" + known + "\n\n" : "") + "TEXT:\n" + windows[w];
      let reg = {};
      try { reg = await this.llm.json(P.registry(this.s.uiLang, this.genre), user, 12000); } catch (e) { if (isFatal(e)) throw e; this.log("registry_failed", `window ${w}: ${e.message}`); continue; }
      for (const kind of ["persons", "places", "orgs"]) for (const e of reg[kind] || []) {
        if (!e || typeof e !== "object") continue;
        let id = String(e.id || "").replace(/[^A-Za-z0-9_.-]/g, "");
        const ex = merged[kind].find((x) => x.id === id);
        if (ex) { ex.variants = uniq([...(ex.variants || []), ...(e.variants || [])]); continue; }
        if (!id || !/^[A-Za-z]/.test(id)) id = (kind === "persons" ? "P" : kind === "places" ? "L" : "O") + (seen.size + 1);
        while (seen.has(id)) id += "_";
        seen.add(id); e.id = id; merged[kind].push(e);
      }
    }
    // grounding: drop entities whose name and variants never occur in the text
    const T = nospace(text), dropped = [];
    for (const kind of Object.keys(merged)) merged[kind] = merged[kind].filter((e) => {
      const forms = [e.name || "", ...(e.variants || [])].filter((f) => typeof f === "string");
      e.variants = (e.variants || []).filter((v) => typeof v === "string" && nospace(v) && T.includes(nospace(v)));
      const ok = forms.some((f) => nospace(stripParen(f)) && T.includes(nospace(stripParen(f))));
      if (!ok) dropped.push(e.name); return ok;
    });
    this.registry = merged;
    this.mergeDuplicateNames(false);
    this.log("registry", { ...Object.fromEntries(Object.entries(this.registry).map(([k, v]) => [k, v.length])), windows: windows.length, dropped_ungrounded: dropped.slice(0, 50) });
    return this.registry;
  }
  fixNameRefs() {
    // proper-name text that is exactly the name/variant of ONE entity, but whose @ref points elsewhere -> re-point
    const owners = new Map();
    for (const kind of ["persons", "places", "orgs"]) for (const e of this.registry[kind] || [])
      for (const f of [e.name, ...(e.variants || [])]) {
        const k = nospace(stripParen(f || ""));
        if (k.length >= 2 && !GENERIC_FORMS.has(k) && !GENERIC_FORMS.has(k.toLowerCase())) { if (!owners.has(k)) owners.set(k, new Set()); owners.get(k).add(e.id); }
      }
    const fixes = [], pat = /<(persName|placeName|orgName)\b([^>]*?)\bref="#([^"\s]+)"([^>]*)>([^<]+)<\/\1>/g;
    for (const b of this.blocks) b.xml = b.xml.replace(pat, (m, el, pre, id, post, txt) => {
      const c = owners.get(nospace(txt));
      if (c && c.size === 1 && !c.has(id)) { const nid = [...c][0]; fixes.push({ block: b.i, text: txt, from: id, to: nid }); return `<${el}${pre}ref="#${nid}"${post}>${txt}</${el}>`; }
      return m;
    });
    if (fixes.length) this.log("ref_fixes", { count: fixes.length, sample: fixes.slice(0, 20) });
    return fixes;
  }
  mergeDuplicateNames(rewrite = true) {
    // same canonical name (ignoring spaces/parentheses), or a name that is exactly one other entity's variant -> one id
    const alias = {};
    for (const kind of ["persons", "places", "orgs"]) {
      const ents = this.registry[kind] || [], byName = new Map(), owner = new Map(), keep = [];
      for (const e of ents) for (const v of e.variants || []) { const k = nospace(v); if (!owner.has(k)) owner.set(k, new Set()); owner.get(k).add(e.id); }
      for (const e of ents) {
        const key = nospace(stripParen(e.name || ""));
        let t = byName.get(key);
        if (!t && key.length >= 2) {
          const o = new Set([...(owner.get(key) || [])]); o.delete(e.id);
          if (o.size === 1) { const oid = [...o][0]; t = keep.find((x) => x.id === oid); }
        }
        if (t && t.id !== e.id) { alias[e.id] = t.id; t.variants = uniq([...(t.variants || []), e.name, ...(e.variants || [])].filter(Boolean)); continue; }
        if (key) byName.set(key, e);
        keep.push(e);
      }
      this.registry[kind] = keep;
    }
    if (Object.keys(alias).length && rewrite)
      for (const b of this.blocks) b.xml = b.xml.replace(/\b(ref|who)="([^"]*)"/g, (m, a, v) =>
        `${a}="${uniq(v.split(/\s+/).filter(Boolean).map((t) => (t.startsWith("#") && alias[t.slice(1)] ? "#" + alias[t.slice(1)] : t))).join(" ")}"`);
    if (Object.keys(alias).length) this.log("registry_merge", alias);
    return alias;
  }
  registryText(max = 300) {
    const lines = [];
    for (const [k, lab] of [["persons", "PERSON"], ["places", "PLACE"], ["orgs", "ORG"]])
      for (const e of (this.registry[k] || []).slice(0, max)) {
        const v = (e.variants || []).slice(0, 8).join(", ");
        lines.push(`${lab} #${e.id} = ${e.name}` + (v ? ` (also: ${v})` : "") + (e.note ? ` — ${e.note}` : ""));
      }
    return lines.join("\n") || "(empty — create ids as needed and report them in new_entities)";
  }
  allIds() { return new Set([...["persons", "places", "orgs"].flatMap((k) => (this.registry[k] || []).map((e) => e.id)), ...this.extra_ids]); }
  tagSystem(keys = null) {
    keys = keys || this.tagset;
    const els = [...tagsFor(keys), "p", "head", "div", "pb", "lb", "note"];
    const langRules = uniq(this.langs.map((l) => l.split("-")[0])).filter((l) => LANG_RULES[l]).map((l) => LANG_RULES[l]).join(" ");
    const ex = selectExemplars(this.genre, this.langs.map((l) => l.split("-")[0]), GENRES[this.genre].exemplars || [], 2);
    return P.tag({ genre: this.genre, tagKeys: keys, langRules: langRules || "Preserve the source orthography.", cheatsheet: attributeCheatsheet(els),
      exemplars: ex.map((e) => formatExemplar(e)).join("\n\n"), registry: this.registryText(), u: this.s.uiLang, pageNumbers: this.pageNumbers(), extra: projectRulesBlock(this.project_rules), langs: this.langs });
  }
  chunks(blocks = null) {
    blocks = blocks || this.blocks; const out = []; let cur = [], size = 0;
    for (const b of blocks) {
      const n = (b.raw || "").length + Math.floor((b.xml || "").length / 3);
      if (cur.length && size + n > this.s.chunkChars) { out.push(cur); cur = []; size = 0; }
      cur.push(b); size += n;
    }
    if (cur.length) out.push(cur);
    return out;
  }
  problemsFor(block, xml) {
    const pres = checkPreservation(block.raw, xml, this.pageNumbers());
    return pres.ok ? quickCheck(xml) : pres.problems;
  }
  async runChunk(system, chunk, user, mode) {
    const res = { new_entities: [], uncertain: [], errors: [] }, byI = new Map(chunk.map((b) => [b.i, b]));
    let data;
    try { data = await this.llm.json(system, user, Math.min(this.s.maxTokens, 8000 + 6 * chunk.reduce((s, b) => s + b.raw.length, 0))); }
    catch (e) { if (isFatal(e)) throw e; res.errors.push(e.message); return res; }
    res.new_entities.push(...(data.new_entities || [])); res.uncertain.push(...(data.uncertain || []));
    const props = new Map();
    for (const it of data.blocks || []) { const i = parseInt(it.i, 10); if (byI.has(i) && typeof it.xml === "string") props.set(i, it); }
    const failing = [];
    for (const [i, it] of props) { const pr = this.problemsFor(byI.get(i), it.xml); if (pr.length) failing.push({ i, your_xml: it.xml, source_text: byI.get(i).raw, problems: pr }); }
    if (failing.length) {
      try {
        const fix = await this.llm.json(system, user + "\n\n" + P.repairUser(failing), 12000);
        for (const it of fix.blocks || []) { const i = parseInt(it.i, 10); if (props.has(i) && typeof it.xml === "string") { props.get(i).xml = it.xml; props.get(i)._repaired = true; } }
      } catch (e) { res.errors.push("repair failed: " + e.message); }
    }
    for (const [i, it] of props) {
      const b = byI.get(i); let xml = it.xml.trim();
      if (mode === "tag") { const [x2, inner] = unwrapDiv(xml); xml = x2; if (inner && !(it.div && it.div.type)) it.div = inner; }
      const pres = checkPreservation(b.raw, xml, this.pageNumbers());
      if (!pres.ok) { b.warnings = [`모델이 원문을 바꿔 이전 마크업 유지: ${pres.problems.slice(0, 2).join(" / ")}`]; b.status = "fallback"; continue; }
      if (quickCheck(xml).length) {
        try { const [x3, log] = stripDisallowed(xml); xml = x3; b.warnings = [`자동 수정: ${log.slice(0, 5).join(", ")}`]; }
        catch (e) { b.status = "fallback"; continue; }
      } else b.warnings = [];
      if (pres.removed.length) b.warnings.push(`쪽번호로 보이는 텍스트 제거: ${pres.removed.join(", ")}`);
      b.xml = xml; b.status = it._repaired ? "repaired" : "tagged";
      if (mode === "tag") b.div = it.div && it.div.type ? it.div : null;
    }
    const missing = [...byI.keys()].filter((i) => !props.has(i));
    if (missing.length) res.errors.push(`model returned no output for blocks ${missing.join(",")}`);
    return res;
  }
  mergeEntities(list) {
    const ids = this.allIds();
    for (const e of list) {
      const kind = { person: "persons", place: "places", org: "orgs" }[e.kind] || "persons";
      const id = String(e.id || "").replace(/[^A-Za-z0-9_.-]/g, "");
      if (id && /^[A-Za-z]/.test(id) && !ids.has(id)) { this.registry[kind].push({ id, name: e.name, variants: [], note: e.note || "" }); ids.add(id); }
    }
  }
  async parallel(system, chunks, makeUser, mode, progress) {
    const unc = [], errs = [], nw = [];
    const results = await pool(chunks, this.s.maxWorkers, (ch) => {
      const ctx = ch[0].i > 0 && mode === "tag" ? this.blocks[ch[0].i - 1].raw : "";
      return this.runChunk(system, ch, makeUser(ch, ctx), mode);
    }, (done, total) => progress && progress(`${done}/${total} 청크`, done / total));
    for (const r of results) { nw.push(...r.new_entities); unc.push(...r.uncertain); errs.push(...r.errors); }
    this.mergeEntities(nw);
    return [unc, errs];
  }
  async tagAll(progress) {
    if (!this.blocks.length) this.blocks = this.segment();
    this.snapshot("자동 태깅 이전"); this.status = "tagging";
    const [unc, errs] = await this.parallel(this.tagSystem(), this.chunks(), (ch, ctx) => P.tagUser(ch, ctx), "tag", progress);
    this.reconcileRegistry(); this.mergeDuplicateNames(); this.fixNameRefs(); this.addQuestions(unc); this.status = "tagged";
    const summary = this.summary(); this.log("tag_all", { tagset: this.tagset, errors: errs.slice(0, 5), counts: summary.tag_counts });
    return { summary, errors: errs, uncertain: unc };
  }
  addQuestions(unc) {
    for (const u of unc.slice(0, 30)) {
      if (!u || !u.question || this.questions.some((q) => q.question === u.question)) continue;
      this.questions.push({ id: `u${this.questions.length + 1}`, question: u.question, about: u.text || "", block: u.i ?? null, options: [], source: "tagging", answered: false });
    }
  }
  reconcileRegistry() {
    const ids = this.allIds(), added = [];
    for (const b of this.blocks) {
      let f; try { f = parseFragment(b.xml); } catch (e) { continue; }
      for (const el of f.getElementsByTagName("*")) for (const att of ["ref", "who"]) for (const tok of (el.getAttribute(att) || "").split(/\s+/)) {
        if (!tok.startsWith("#") || ids.has(tok.slice(1))) continue;
        const n = lname(el), ty = el.getAttribute("type");
        const kind = ["placeName", "geogName"].includes(n) || ty === "place" ? "places" : n === "orgName" || ty === "org" ? "orgs" : "persons";
        const txt = att === "ref" ? sourceText(el).replace(/\s+/g, " ").trim().slice(0, 40) : tok.slice(1);
        this.registry[kind].push({ id: tok.slice(1), name: txt || tok.slice(1), variants: [], note: "auto-added from text" });
        ids.add(tok.slice(1)); added.push(tok.slice(1));
      }
    }
    return added;
  }
  summary() {
    const st = {}; for (const b of this.blocks) st[b.status] = (st[b.status] || 0) + 1;
    return { genre: this.genre, genre_label: GENRES[this.genre].ko, langs: this.langs, blocks: this.blocks.length, block_status: st,
      tag_counts: elementCounts(this.blocks.map((b) => b.xml)), tagset: this.tagset,
      registry: Object.fromEntries(Object.entries(this.registry).map(([k, v]) => [k, v.length])),
      open_questions: this.questions.filter((q) => !q.answered).length };
  }
  async recommendTags() {
    const sig = signals(this.raw_text);
    const cands = uniq([...GENRES[this.genre].optional, ...GENRES.generic.optional].filter((k) => !this.tagset.includes(k)));
    const ev = {};
    for (const [s, v] of Object.entries(sig)) { const k = D.SIGNAL_TO_TAG[s]; if (k && cands.includes(k)) { ev[k] = ev[k] || { count: 0, examples: [] }; ev[k].count += v.count; ev[k].examples.push(...v.examples.slice(0, 2)); } }
    let rec;
    try { rec = await this.llm.json(P.recTags(this.s.uiLang, this.genre, cands, this.langs), projectRulesBlock(this.project_rules, true) + `Current tag counts: ${J(this.summary().tag_counts)}\nRegex evidence: ${J(ev)}\n\nTEXT SAMPLE:\n${this.raw_text.slice(0, 6000)}`, 4000); }
    catch (e) { rec = { tags: Object.entries(ev).map(([k, v]) => ({ key: k, why: `텍스트에서 관련 패턴 ${v.count}건 발견`, examples: v.examples.slice(0, 3), estimated_count: v.count, priority: 2 })), questions: [], note: e.message }; }
    const tags = [];
    for (const t of rec.tags || []) if (TAGS[t.key] && !this.tagset.includes(t.key)) tags.push({ ...t, label: TAGS[t.key].ko, elements: TAGS[t.key].elements, regex_evidence: ev[t.key] });
    for (const [k, v] of Object.entries(ev)) if (v.count >= 3 && !tags.some((t) => t.key === k))
      tags.push({ key: k, label: TAGS[k].ko, elements: TAGS[k].elements, why: "정규식 탐지 결과 해당 패턴이 반복됩니다.", examples: v.examples.slice(0, 3), estimated_count: v.count, priority: 3, regex_evidence: v });
    tags.sort((a, b) => (a.priority || 3) - (b.priority || 3) || (b.estimated_count || 0) - (a.estimated_count || 0));
    this.recommendations = { tags, generated: nowIso() };
    for (const q of rec.questions || []) { if (!q || !q.question || this.questions.some((x) => x.question === q.question)) continue; this.questions.push({ ...q, id: `t${this.questions.length + 1}`, source: "recommend_tags", answered: false }); }
    this.log("recommend_tags", tags.map((t) => t.key));
    return { tags, questions: this.questions.filter((q) => !q.answered) };
  }
  ungrounded(patch) {
    const text = norm(this.raw_text), skip = new Set(["type", "level", "lang", "ident", "label", "unit", "role", "scheme", "status", "target", "usage", "kind"]), out = [];
    (function walk(o) {
      if (Array.isArray(o)) o.forEach(walk);
      else if (o && typeof o === "object") { for (const [k, v] of Object.entries(o)) if (!skip.has(k)) walk(v); }
      else if (typeof o === "string" && o.trim().length >= 2 && !o.startsWith("http") && !text.includes(norm(o))) out.push(o);
    })(Object.fromEntries(Object.entries(patch).filter(([k]) => FACTUAL_KEYS.has(k))));
    return out;
  }
  async recommendMetadata() {
    const fields = METADATA_FIELDS.filter((f) => f.genres === "*" || f.genres.includes(this.genre));
    const present = new Set(Object.entries(this.metadata).filter(([, v]) => v && (!Array.isArray(v) || v.length)).map(([k]) => k));
    for (const k of ["persons", "places", "orgs"]) if ((this.registry[k] || []).length) present.add(k);
    if (((this.metadata.publication || {}).idnos || []).length) present.add("pid");
    const FIELD_TO_MD = { title: "titles", source: "sources", msdesc: "msDesc", project: "project_desc", classDecl: "taxonomies", calendar: "calendars" };
    const missing = fields.filter((f) => !present.has(FIELD_TO_MD[f.key] || f.key) && !["tagsDecl", "appInfo", "extent", "revisions"].includes(f.key));
    const excerpt = this.raw_text.slice(0, 4000) + (this.raw_text.length > 6000 ? "\n…\n" + this.raw_text.slice(-1500) : "");
    let rec;
    try {
      const an = Object.fromEntries(["languages", "genre", "period", "title", "author", "notes"].map((k) => [k, this.analysis[k] ?? null]));
      rec = await this.llm.json(P.recMeta(this.s.uiLang, this.genre), `Current metadata JSON: ${J(this.metadata)}\nAnalysis: ${J(an)}\nRegistry sizes: ${J(this.summary().registry)}\n\nTEXT EXCERPTS:\n${excerpt}`, 5000);
    } catch (e) { rec = { suggestions: [], to_lookup: [], questions: [], note: e.message }; }
    const sugg = [], lookups = [...(rec.to_lookup || [])];
    for (const sg of rec.suggestions || []) {
      if (!sg || typeof sg.patch !== "object" || !sg.patch) continue;
      const removed = []; sg.patch = stripIdentifiers(sg.patch, removed);
      if (removed.length) { sg.identifiers_removed = removed.map(([n, v]) => `${n}: ${v}`); removed.forEach(([n]) => n && lookups.push({ kind: sg.key || "", name: n, lang: this.langs[0] || "en" })); }
      sg.patch = Object.fromEntries(Object.entries(sg.patch).filter(([k]) => METADATA_KEYS.has(k)));
      if (!Object.keys(sg.patch).length) continue;
      const ung = Object.keys(sg.patch).some((k) => FACTUAL_KEYS.has(k)) ? this.ungrounded(sg.patch) : [];
      if (ung.length) { sg.needs_verification = true; sg.not_in_text = ung.slice(0, 6); }
      else if (Object.keys(sg.patch).some((k) => INTERPRETIVE_KEYS.has(k))) { sg.needs_verification = true; sg.model_written = true; }
      else sg.needs_verification = sg.basis !== "text" && !Object.keys(sg.patch).some((k) => GROUNDED_OK.has(k));
      sugg.push(sg);
    }
    const seen = new Set();
    const toLookup = lookups.filter((l) => l && l.name && !seen.has(l.name) && seen.add(l.name));
    this.meta_recommendations = { suggestions: sugg, to_lookup: toLookup, generated: nowIso(),
      missing_fields: missing.map((f) => ({ key: f.key, level: f.level, label: f.ko, path: f.path, why: f.why })) };
    for (const q of rec.questions || []) { if (!q || !q.question || this.questions.some((x) => x.question === q.question)) continue; this.questions.push({ ...q, id: `m${this.questions.length + 1}`, source: "recommend_metadata", answered: false }); }
    this.log("recommend_metadata", sugg.length);
    return this.meta_recommendations;
  }
  async acceptTags(keys, extra = "", progress) {
    keys = keys.filter((k) => TAGS[k]); if (!keys.length) return { changed: 0 };
    if (this.recommendations.tags) this.recommendations.tags = this.recommendations.tags.filter((t) => !keys.includes(t.key));
    let instr = "Add the following markup wherever it applies: " + keys.map((k) => tagRule(k, this.langs)).join("; ");
    if (extra) instr += " Additional guidance from the user: " + extra;
    return this.retag(instr, { addKeys: keys, progress });
  }
  async retag(instruction, { addKeys = [], removeKeys = [], blockIds = null, search = null, progress = null } = {}) {
    this.snapshot("이전: " + instruction.slice(0, 60));
    for (const k of addKeys) if (!this.tagset.includes(k)) this.tagset.push(k);
    this.tagset = this.tagset.filter((k) => !removeKeys.includes(k));
    let targets = this.blocks;
    if (blockIds && blockIds.length) { const ids = new Set(blockIds.map(Number)); targets = this.blocks.filter((b) => ids.has(b.i)); }
    else if (search && search.length) targets = this.blocks.filter((b) => search.some((s) => s && b.raw.includes(s)));
    const before = new Map(targets.map((b) => [b.i, b.xml]));
    const [unc, errs] = await this.parallel(P.retag(this.tagSystem(), instruction), this.chunks(targets), (ch) => P.retagUser(ch), "retag", progress);
    this.reconcileRegistry(); this.mergeDuplicateNames(); this.fixNameRefs(); this.addQuestions(unc);
    const changed = targets.filter((b) => b.xml !== before.get(b.i)).length;
    this.log("retag", { instruction, targets: targets.length, changed, errors: errs.slice(0, 3) });
    return { changed, targets: targets.length, errors: errs, summary: this.summary() };
  }
  findMarkup({ element = "", text_regex = "", attr = "", value = "", missing_attr = "" } = {}, maxEx = 8) {
    let rx = null; try { rx = text_regex ? new RegExp(text_regex) : null; } catch (e) { return { error: "bad regex: " + e.message }; }
    let n = 0; const texts = new Map(), ex = [];
    for (const b of this.blocks) {
      let f; try { f = parseFragment(b.xml); } catch (e) { continue; }
      for (const el of [f, ...f.getElementsByTagName("*")]) {
        if (element && lname(el) !== element) continue;
        const txt = sourceText(el).replace(/\s+/g, " ").trim();
        if (rx && !rx.test(txt)) continue;
        if (attr && (!el.hasAttribute(attr) || (value && el.getAttribute(attr) !== value))) continue;
        if (missing_attr && el.hasAttribute(missing_attr)) continue;
        n++; const k = txt.slice(0, 30); texts.set(k, (texts.get(k) || 0) + 1);
        if (ex.length < maxEx) ex.push({ block: b.i, xml: xmlSer.serializeToString(el).replace(/ xmlns="[^"]*"/g, "").slice(0, 200) });
      }
    }
    return { count: n, top_texts: [...texts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10), examples: ex };
  }
  setProjectRules(text) { this.project_rules = String(text || "").trim().slice(0, 8000); this.log("project_rules", { chars: this.project_rules.length }); return { chars: this.project_rules.length }; }
  async reapplyProjectRules(progress) { return this.retag("Re-check every block against the PROJECT RULES and change only the markup that violates them.", { progress }); }
  async applyInstruction(text, progress) {
    const ctx = { genre: this.genre, tagset: this.tagset, summary: this.summary(), registry: this.registryText(80), metadata_keys: Object.keys(this.metadata) };
    const plan = await this.llm.json(P.plan(this.s.uiLang), `State: ${J(ctx)}\n\nUSER INSTRUCTION: ${text}`, 3000);
    const out = { plan, reply: plan.reply || "" };
    if (plan.metadata_patch && Object.keys(plan.metadata_patch).length) { this.updateMetadata(plan.metadata_patch); out.metadata_updated = true; }
    for (const op of plan.entity_ops || []) this.editEntity(op.op, op.kind, op.id, op.data, op.into);
    if (plan.retag_instruction || (plan.tag_keys || []).length || (plan.remove_tag_keys || []).length) {
      let instr = plan.retag_instruction || "Add: " + (plan.tag_keys || []).filter((k) => TAGS[k]).map((k) => tagRule(k, this.langs)).join("; ");
      if ((plan.remove_tag_keys || []).length) instr += " Remove markup of these kinds (unwrap, keep text): " + plan.remove_tag_keys.filter((k) => TAGS[k]).flatMap((k) => TAGS[k].elements).join(", ");
      const scope = plan.scope || "all";
      out.retag = await this.retag(instr, { addKeys: (plan.tag_keys || []).filter((k) => TAGS[k]), removeKeys: (plan.remove_tag_keys || []).filter((k) => TAGS[k]),
        blockIds: scope === "blocks" ? plan.block_ids : null, search: scope === "search" ? plan.search : null, progress });
    }
    this.log("instruction", { text, kind: plan.kind });
    return out;
  }
  async answerQuestion(qid, answer, progress) {
    const q = this.questions.find((x) => x.id === qid); if (!q) return { error: "unknown question " + qid };
    q.answered = true; q.answer = answer;
    const about = q.about ? ` (concerning: ${q.about})` : "", blk = q.block !== null && q.block !== undefined ? ` Only block ${q.block} is affected.` : "";
    return this.applyInstruction(`Question asked to me: ${q.question}${about}. My answer: ${answer}.${blk}`, progress);
  }
  setUiLang(l) {
    this.s.uiLang = l;
    if (this.chat.length && this.chat[0].role === "system") this.chat[0].content = P.agent(l); // agent replies follow the UI language
  }
  /* ---- direct (manual) edits from the reading view: same safeguards as model output */
  checkBlockXml(i, xml) {
    const b = this.blocks.find((x) => x.i === i); if (!b) return { ok: false, problems: [`no block ${i}`] };
    const pres = checkPreservation(b.raw, xml, this.pageNumbers());
    if (!pres.ok) return { ok: false, problems: pres.problems, fatal: true };
    const qc = quickCheck(xml);
    return { ok: !qc.length, problems: qc, fatal: false };
  }
  setBlockXml(i, xml, label = "manual edit", { force = false } = {}) {
    xml = String(xml).trim();
    const chk = this.checkBlockXml(i, xml);
    if (chk.fatal || (!chk.ok && !force)) return chk;
    const b = this.blocks.find((x) => x.i === i);
    if (b.xml === xml) return { ok: true, problems: [], unchanged: true };
    this.snapshot(`이전: ${label} (블록 ${i})`);
    b.xml = xml; b.status = "edited"; b.warnings = chk.problems.length ? [`schema: ${chk.problems.slice(0, 3).join(" / ")}`] : [];
    this.reconcileRegistry(); this.log("manual_edit", { block: i, label });
    return { ok: true, problems: chk.problems };
  }
  editElement(i, elIdx, { name = null, attrs = null, unwrap = false } = {}, opts = {}) {
    const b = this.blocks.find((x) => x.i === i); if (!b) return { ok: false, problems: [`no block ${i}`] };
    const root = parseFragment(b.xml), el = root.getElementsByTagName("*")[elIdx];
    if (!el) return { ok: false, problems: ["element not found"] };
    const old = lname(el);
    if (unwrap) { while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el); el.remove(); return this.setBlockXml(i, innerXml(root), `<${old}> 태그 제거`, opts); }
    let target = el;
    if (name && name !== old) {
      target = root.ownerDocument.createElementNS(TEI_NS, name);
      for (const a of el.attributes) target.setAttributeNS(a.namespaceURI, a.name, a.value);
      while (el.firstChild) target.appendChild(el.firstChild);
      el.parentNode.replaceChild(target, el);
    }
    if (attrs) {
      for (const a of [...target.attributes]) if (!/^xmlns/.test(a.name)) target.removeAttributeNode(a);
      for (const [k, v] of Object.entries(attrs)) { if (!k) continue; if (k.startsWith("xml:")) target.setAttributeNS(XML_NS, k, v); else target.setAttribute(k, v); }
    }
    return this.setBlockXml(i, innerXml(root), `<${old}>${name && name !== old ? " → <" + name + ">" : ""} 수정`, opts);
  }
  wrapText(i, textIdx, start, end, name, attrs = {}, opts = {}) {
    const b = this.blocks.find((x) => x.i === i); if (!b) return { ok: false, problems: [`no block ${i}`] };
    const root = parseFragment(b.xml), texts = [];
    (function walk(n) { for (const c of n.childNodes) { if (c.nodeType === 3) texts.push(c); else if (c.nodeType === 1) walk(c); } })(root);
    const tn = texts[textIdx]; if (!tn || start >= end || end > tn.nodeValue.length) return { ok: false, problems: ["selection not found"] };
    const doc = root.ownerDocument, mid = tn.splitText(start); mid.splitText(end - start);
    const el = doc.createElementNS(TEI_NS, name);
    for (const [k, v] of Object.entries(attrs || {})) { if (!k) continue; if (k.startsWith("xml:")) el.setAttributeNS(XML_NS, k, v); else el.setAttribute(k, v); }
    mid.parentNode.replaceChild(el, mid); el.appendChild(mid);
    return this.setBlockXml(i, innerXml(root), `<${name}> 추가`, opts);
  }
  updateMetadata(patch) {
    this.snapshot("메타데이터 수정 이전"); patch = clone(patch);
    for (const kind of ["persons", "places", "orgs"]) if (patch[kind]) {
      for (const e of patch[kind] || []) this.editEntity((this.registry[kind] || []).some((x) => x.id === e.id) ? "update" : "add", kind.slice(0, -1), e.id, e);
      delete patch[kind];
    }
    this.metadata = deepMerge(this.metadata, patch); this.log("metadata", Object.keys(patch));
    return this.metadata;
  }
  editEntity(op, kind, id = null, data = null, into = null) {
    kind = { person: "persons", place: "places", org: "orgs" }[kind] || kind;
    const lst = (this.registry[kind] = this.registry[kind] || []); data = data || {};
    if (op === "add") { const eid = id || data.id; if (eid && !this.allIds().has(eid)) { const { id: _, ...rest } = data; lst.push({ id: eid, ...rest }); } }
    else if (op === "update") for (const e of lst) { if (e.id === id) { const { id: _, ...rest } = data; Object.assign(e, rest); } }
    else if (op === "delete") this.registry[kind] = lst.filter((e) => e.id !== id);
    else if (op === "merge" && id && into) {
      this.registry[kind] = lst.filter((e) => e.id !== id);
      const rx = new RegExp(`#${id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?=["\\s])`, "g");
      for (const b of this.blocks) b.xml = b.xml.replace(rx, "#" + into);
    }
    this.log("entity", { op, kind, id });
    return { registry: Object.fromEntries(Object.entries(this.registry).map(([k, v]) => [k, v.length])) };
  }
  registryToMetadata() {
    const used = refsIn(this.blocks.map((b) => b.xml)), keep = (e) => used.has(e.id) || e.keep;
    const pick = (e, ks) => Object.fromEntries(ks.filter((k) => e[k]).map((k) => [k, e[k]]));
    const person_ = (e) => {
      const d = { id: e.id, names: [{ text: e.name, lang: this.langs[0] || null }] };
      for (const v of (e.variants || []).slice(0, 6)) if (v && v !== e.name && v.length < 40) d.names.push({ text: v, type: "variant" });
      if (["M", "F", "U"].includes(e.sex)) d.sex = e.sex; if (e.role) d.role = e.role;
      if (e.wikidata) d.idnos = [{ type: "wikidata", value: e.wikidata }];
      return Object.assign(d, pick(e, ["note", "birth", "death", "occupation", "gender", "age", "idnos"]));
    };
    const simple = (e) => { const d = { id: e.id, names: [{ text: e.name }], type: e.type }; if (e.wikidata) d.idnos = [{ type: "wikidata", value: e.wikidata }]; return Object.assign(d, pick(e, ["note", "geo", "idnos"])); };
    return { persons: (this.registry.persons || []).filter(keep).map(person_), places: (this.registry.places || []).filter(keep).map(simple), orgs: (this.registry.orgs || []).filter(keep).map(simple) };
  }
  bodyLines() {
    const lines = ["<body>"], start = {}, stack = [], ind = () => "  ".repeat(stack.length + 1);
    let last = {};
    for (const b of this.blocks) {
      let d = b.div; const xml = b.xml.trim();
      if (!d && xml.startsWith("<head") && xml.endsWith("</head>") && xml.split("<head").length === 2) {
        // a heading the model did not mark as a division start: open a sibling division (deterministic)
        const n = xml.replace(/<[^>]+>/g, "").trim();
        d = { type: last.type || "section", level: last.level || 1, n: /^\d{1,4}$/.test(n) ? n : null };
      }
      if (b.part) { // outer division opened before the block's own division (merged documents)
        while (stack.length) { stack.pop(); lines.push(ind() + "</div>"); }
        lines.push(ind() + `<div type="${escAttr(b.part.type)}"` + (b.part.n ? ` n="${escAttr(b.part.n)}"` : "") + ">"); stack.push(1);
      }
      if (d) last = d;
      if (d) {
        const lvl = parseInt(d.level || 1, 10);
        while (stack.length && stack[stack.length - 1] >= lvl) { stack.pop(); lines.push(ind() + "</div>"); }
        lines.push(ind() + `<div type="${escAttr(d.type)}"` + (d.n !== null && d.n !== undefined && d.n !== "" ? ` n="${escAttr(d.n)}"` : "") + ">");
        stack.push(lvl);
      }
      start[b.i] = lines.length;
      for (const l of xml.split("\n")) lines.push(ind() + l);
    }
    while (stack.length) { stack.pop(); lines.push(ind() + "</div>"); }
    lines.push("</body>");
    return [lines, start];
  }
  normalizeStructure() {
    // deterministic: a bare-number block in a text without page numbers is a chapter/section number -> <head>
    if (this.pageNumbers()) return 0;
    let changed = 0;
    for (const b of this.blocks) {
      const raw = (b.raw || "").trim();
      if (/^\d{1,4}$/.test(raw) && !b.xml.trim().startsWith("<head")) {
        b.xml = `<head>${raw}</head>`;
        if (!b.div) {
          const prev = this.blocks.slice(0, b.i).reverse().find((x) => x.div);
          const pd = prev ? prev.div : {};
          b.div = { type: pd.type || "chapter", n: raw, level: pd.level || 1 };
        }
        changed++;
      }
    }
    return changed;
  }
  toXml() {
    this.normalizeStructure();
    let md = deepMerge(this.metadata, this.registryToMetadata());
    if ((this.project_rules || "").trim() && !((md.editorial || {}).interpretation))
      md = deepMerge(md, { editorial: { interpretation: "Project encoding rules supplied by the encoders were added to every model instruction: " +
        this.project_rules.replace(/<!--[\s\S]*?-->/g, "").split("\n").map((l) => l.replace(/^[\s\-*#]+/, "").trim()).filter(Boolean).join(" | ").slice(0, 3000) } });
    const [body, start] = this.bodyLines();
    const counts = elementCounts(this.blocks.map((b) => b.xml)); counts.body = 1; counts.text = 1;
    let headerS, standoffS;
    if (this.header_override) { headerS = this.header_override; standoffS = this.standoff_override || ""; }
    else {
      [headerS, standoffS] = buildHeader(md, { tagCounts: counts, registryLocation: GENRES[this.genre].registry_location, model: this.s.model,
        stats: { chars: norm(this.raw_text).length, words: this.raw_text.split(/\s+/).filter(Boolean).length } });
      standoffS = standoffS || "";
    }
    const head = ['<?xml version="1.0" encoding="UTF-8"?>',
      `<?xml-model href="https://www.tei-c.org/Vault/P5/${TEI_VERSION}/xml/tei/custom/schema/relaxng/tei_all.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>`,
      `<TEI xmlns="${TEI_NS}" xml:lang="${escAttr(this.langs[0] || "und")}">`];
    head.push(...headerS.trim().split("\n").map((l) => "  " + l));
    if (standoffS) head.push(...standoffS.trim().split("\n").map((l) => "  " + l));
    head.push("  <text>");
    const offset = head.length;
    const lines = [...head, ...body.map((l) => "    " + l), "  </text>", "</TEI>"];
    const lineOf = Object.fromEntries(Object.entries(start).map(([i, s]) => [i, offset + s + 1]));
    return [lines.join("\n") + "\n", lineOf];
  }
  async validate() {
    const [xml, lineOf] = this.toXml();
    let res;
    try { res = await rngValidate(xml); } catch (e) { res = { wellformed: false, valid: false, errors: [{ line: 0, message: e.message }] }; }
    const starts = Object.entries(lineOf).map(([i, ln]) => [ln, Number(i)]).sort((a, b) => a[0] - b[0]);
    for (const e of res.errors) { e.block = null; for (const [ln, i] of starts) { if (ln <= (e.line || 0)) e.block = i; else break; } }
    const used = refsIn(this.blocks.map((b) => b.xml)), ids = this.allIds();
    res.dangling_refs = [...used].filter((x) => !ids.has(x)).sort();
    res.fallback_blocks = this.blocks.filter((b) => b.status === "fallback").map((b) => b.i);
    this.validation = res; return res;
  }
  async repair(progress) {
    const v = await this.validate(), by = new Map();
    for (const e of v.errors) if (e.block !== null) { if (!by.has(e.block)) by.set(e.block, []); by.get(e.block).push(e.message); }
    if (!by.size) return { repaired: 0, valid: v.valid, remaining: v.errors };
    const msgs = [...by].slice(0, 40).map(([i, m]) => `block ${i}: ${m.slice(0, 3).join(" | ")}`).join("; ");
    const r = await this.retag(`Fix these TEI ${TEI_VERSION} schema validation errors without changing correct markup: ${msgs}`, { blockIds: [...by.keys()], progress });
    // deterministic last resort for attribute-level errors
    for (const b of this.blocks) if (by.has(b.i) && quickCheck(b.xml).length) { try { const [x, log] = stripDisallowed(b.xml); b.xml = x; b.warnings.push("자동 수정: " + log.slice(0, 3).join(", ")); } catch (e) { /* keep */ } }
    const v2 = await this.validate();
    return { repaired: r.changed, valid: v2.valid, remaining: v2.errors.slice(0, 30) };
  }
  static fromTei(xmlText, settings = Settings.load()) {
    const doc = domParser.parseFromString(xmlText, "application/xml");
    if (doc.getElementsByTagName("parsererror")[0]) throw new Error("TEI XML을 읽을 수 없습니다 (well-formed 아님).");
    const root = doc.documentElement, s = new Session("", settings);
    const T = (el, n) => [...el.children].find((c) => c.localName === n && c.namespaceURI === TEI_NS);
    const hdr = T(root, "teiHeader"), so = T(root, "standOff");
    if (hdr) s.header_override = stripNs(xmlSer.serializeToString(hdr));
    if (so) s.standoff_override = stripNs(xmlSer.serializeToString(so));
    for (const [kind, tag, nameTag] of [["persons", "person", "persName"], ["places", "place", "placeName"], ["orgs", "org", "orgName"]])
      for (const el of root.getElementsByTagNameNS(TEI_NS, tag)) {
        const xid = el.getAttributeNS(XML_NS, "id");
        if (xid) {
          const n = [...el.children].find((c) => c.localName === nameTag), e = { id: xid, name: n ? n.textContent.replace(/\s+/g, " ").trim() : xid, variants: [], keep: true };
          for (const a of ["sex", "role", "type"]) if (el.getAttribute(a)) e[a] = el.getAttribute(a);
          const wd = [...el.children].find((c) => c.localName === "idno" && /wikidata/i.test(c.getAttribute("type") || ""));
          if (wd) e.wikidata = wd.textContent.trim();
          s.registry[kind].push(e);
        }
      }
    const known = s.allIds();
    for (const part of [hdr, so]) if (part) for (const x of part.getElementsByTagName("*")) { const id = x.getAttributeNS(XML_NS, "id"); if (id && !known.has(id)) s.extra_ids.push(id); }
    const lang = root.getAttributeNS(XML_NS, "lang");
    s.langs = [...root.getElementsByTagNameNS(TEI_NS, "language")].map((l) => l.getAttribute("ident")).filter(Boolean);
    if (!s.langs.length) s.langs = [lang || "und"];
    const text = T(root, "text"), body = text ? T(text, "body") : null, blocks = [];
    (function walk(el, level, pending) {
      for (const ch of el.children) {
        if (ch.localName === "div") { walk(ch, level + 1, { type: ch.getAttribute("type") || "section", n: ch.getAttribute("n"), level: level + 1 }); pending = null; continue; }
        blocks.push({ i: blocks.length, raw: sourceText(ch).replace(/\s+/g, " ").trim(), xml: stripNs(xmlSer.serializeToString(ch)), div: pending, status: "imported", warnings: [] });
        pending = null;
      }
    })(body || root, 0, null);
    s.blocks = blocks; s.raw_text = blocks.map((b) => b.raw).join("\n\n");
    const a = guess(s.raw_text);
    s.genre = root.getElementsByTagNameNS(TEI_NS, "particDesc").length && root.getElementsByTagNameNS(TEI_NS, "said").length ? "prose_fiction" : a.genre;
    s.analysis = { ...a, imported: true }; s.tagset = [...GENRES[s.genre].core]; s.status = "tagged";
    s.log("import_tei", { blocks: blocks.length });
    return s;
  }
}

/* ------------------------------------------------------------------ agent (tool calling), mirror of tools.py */
const tool = (name, description, properties = {}, required = []) => ({ type: "function", function: { name, description, parameters: { type: "object", properties, required } } });
const TOOLS = [
  tool("get_status", "Summary of the current document: genre, languages, tag counts, registry sizes, validation, open questions."),
  tool("show_blocks", "Show the current TEI xml of some blocks (by index or by a search string).", { block_ids: { type: "array", items: { type: "integer" } }, search: { type: "string" }, max: { type: "integer" } }),
  tool("show_registry", "List registered persons/places/orgs with their xml:ids."),
  tool("recommend_tags", "Recommend additional TEI elements for this text, with evidence and questions for the user."),
  tool("accept_tags", "Apply recommended tag categories (catalog keys) to the whole document.", { keys: { type: "array", items: { type: "string", enum: Object.keys(TAGS) } }, guidance: { type: "string" } }, ["keys"]),
  tool("apply_instruction", "Apply a free-form encoding instruction from the user (add/remove/modify markup, scope by blocks or search).", { instruction: { type: "string" } }, ["instruction"]),
  tool("answer_question", "Record the user's answer to an open question and apply it.", { question_id: { type: "string" }, answer: { type: "string" } }, ["question_id", "answer"]),
  tool("recommend_metadata", "Propose header metadata values and further header fields worth adding."),
  tool("update_metadata", "Merge a patch into the header metadata JSON (titles, authors, sources, licence, creation, keywords, …).", { patch: { type: "object" } }, ["patch"]),
  tool("edit_entity", "Add/update/delete/merge a registry entity (person/place/org).", { op: { type: "string", enum: ["add", "update", "delete", "merge"] }, kind: { type: "string", enum: ["person", "place", "org"] }, id: { type: "string" }, data: { type: "object" }, into: { type: "string" } }, ["op", "kind"]),
  tool("lookup_authority", "Search Wikidata for candidate identifiers of a person/place/org/work.", { name: { type: "string" }, lang: { type: "string" }, kind: { type: "string" } }, ["name"]),
  tool("set_genre", "Change the genre profile (affects structure rules and recommendations).", { genre: { type: "string", enum: Object.keys(GENRES) } }, ["genre"]),
  tool("validate", "Validate the whole document against tei_all 4.12.0 and report errors."),
  tool("repair", "Ask the model to fix blocks that have schema errors, then re-validate."),
  tool("undo", "Undo the last change."),
  tool("find_markup", "Count and show current markup matching a filter (measure before/after a correction). All filters optional.", { element: { type: "string" }, text_regex: { type: "string", description: "regex on the element's text, e.g. '장로$'" }, attr: { type: "string" }, value: { type: "string" }, missing_attr: { type: "string" } }),
  tool("get_project_rules", "Show the project rules (the encoders' own conventions added to every tagging instruction)."),
  tool("set_project_rules", "Replace or extend the project rules with conventions the user states (e.g. 'title-based references like 김장로 are rs'). Ask before replacing existing rules.", { text: { type: "string" }, mode: { type: "string", enum: ["append", "replace"] } }, ["text"]),
  tool("reapply_project_rules", "Re-check all blocks against the current project rules (costs one pass over the text)."),
];
async function dispatch(s, name, args, progress) {
  switch (name) {
    case "get_status": return { ...s.summary(), validation: s.validation && "valid" in s.validation ? { valid: s.validation.valid, dangling_refs: s.validation.dangling_refs } : null };
    case "show_blocks": { const ids = args.block_ids, q = args.search;
      const bl = ids || q ? s.blocks.filter((b) => (ids && ids.includes(b.i)) || (q && b.raw.includes(q))) : s.blocks;
      return bl.slice(0, args.max || 5).map((b) => ({ i: b.i, xml: b.xml, status: b.status, warnings: b.warnings })); }
    case "show_registry": return s.registry;
    case "recommend_tags": return s.recommendTags();
    case "accept_tags": return s.acceptTags(args.keys || [], args.guidance || "", progress);
    case "apply_instruction": return s.applyInstruction(args.instruction, progress);
    case "answer_question": return s.answerQuestion(args.question_id, args.answer, progress);
    case "recommend_metadata": return s.recommendMetadata();
    case "update_metadata": return s.updateMetadata(args.patch || {});
    case "edit_entity": return s.editEntity(args.op, args.kind, args.id, args.data, args.into);
    case "lookup_authority": return lookupAuthority(args.name, args.lang || s.langs[0] || "en", args.kind || "");
    case "set_genre": if (GENRES[args.genre]) { s.genre = args.genre; s.tagset = uniq([...s.tagset, ...GENRES[s.genre].core]); } return s.summary();
    case "validate": { const v = await s.validate(); return { valid: v.valid, errors: v.errors.slice(0, 20), dangling_refs: v.dangling_refs, fallback_blocks: v.fallback_blocks }; }
    case "repair": return s.repair(progress);
    case "undo": return { undone: s.undo() };
    case "find_markup": return s.findMarkup(args);
    case "get_project_rules": return { rules: s.project_rules };
    case "set_project_rules": return s.setProjectRules(args.mode === "replace" ? args.text : ((s.project_rules || "") + "\n" + (args.text || "")).trim());
    case "reapply_project_rules": return s.reapplyProjectRules(progress);
    default: return { error: "unknown tool " + name };
  }
}
const short = (x, n = 6000) => { const t = JSON.stringify(x); return t.length <= n ? t : t.slice(0, n) + "…(truncated)"; };
async function agentChat(s, message, progress, maxSteps = 14) {
  if (!s.chat.length) s.chat.push({ role: "system", content: P.agent(s.s.uiLang) });
  s.chat.push({ role: "user", content: message });
  const actions = [];
  for (let step = 0; step < maxSteps; step++) {
    const msg = await s.llm.chat(s.chat, { tools: TOOLS, maxTokens: 4000 });
    s.chat.push(msg); // full message incl. reasoning_content (DeepSeek thinking + tools requirement)
    const calls = msg.tool_calls || [];
    if (!calls.length) return { reply: msg.content || "", actions };
    for (const c of calls) {
      let args = {}; try { args = JSON.parse(c.function.arguments || "{}"); } catch (e) { /* ignore */ }
      let res; try { res = await dispatch(s, c.function.name, args, progress); } catch (e) { res = { error: e.message }; }
      actions.push({ tool: c.function.name, args });
      s.chat.push({ role: "tool", tool_call_id: c.id, content: short(res) });
    }
  }
  return { reply: "(작업 단계가 많아 여기서 멈췄습니다. 이어서 지시해 주세요.)", actions };
}

/* ------------------------------------------------------------------ gold (reference) TEI data: few-shot exemplars + evaluation */
const teiTitle = (root) => { const t = root.getElementsByTagNameNS(TEI_NS, "titleStmt")[0]; const x = t && t.getElementsByTagNameNS(TEI_NS, "title")[0]; return x ? x.textContent.replace(/\s+/g, " ").trim() : ""; };
const Gold = {
  key: "teiagent.gold",
  list() { try { return JSON.parse(localStorage.getItem(this.key) || "[]"); } catch (e) { return []; } },
  saveAll(l) { try { localStorage.setItem(this.key, JSON.stringify(l)); return true; } catch (e) { return false; } },
  /** Build a gold entry from a TEI document (string) or from a Session (e.g. a corrected work). */
  fromTei(xmlText, fileName = "") {
    const s = Session.fromTei(xmlText);
    const root = domParser.parseFromString(xmlText, "application/xml").documentElement;
    const lic = root.getElementsByTagNameNS(TEI_NS, "licence")[0];
    const t = teiTitle(root), stem = fileName.replace(/\.xml$/i, "");
    return this.fromSession(s, { title: !t || /제목\s*미상|untitled/i.test(t) ? stem || t : t, file: fileName, licence: lic ? (lic.getAttribute("target") || lic.textContent.trim()).slice(0, 80) : "" });
  },
  fromSession(s, { title = "", file = "", licence = "" } = {}) {
    const blocks = s.blocks.map((b) => b.xml).filter((x) => x && x.trim());
    if (!blocks.length) throw new Error("본문(body)에 블록이 없습니다.");
    const t = title || ((s.metadata.titles || [{}])[0] || {}).text || s.raw_text.slice(0, 30);
    return { id: "gold-" + uid(), title: t, file, lang: (s.langs[0] || "und").split("-")[0], genre: s.genre, licence: licence || "user-supplied",
      blocks, raw: s.blocks.map((b) => b.raw).join("\n\n"), registry: s.registry, counts: elementCounts(blocks), use: true, added: nowIso() };
  },
  add(entry) {
    const l = this.list().filter((g) => !(g.title === entry.title && g.raw === entry.raw)); l.unshift(entry);
    if (!this.saveAll(l)) throw new Error("브라우저 저장 공간이 부족해 정답 데이터를 저장할 수 없습니다. 오래된 항목을 지워 주세요.");
    return entry;
  },
  remove(id) { return this.saveAll(this.list().filter((g) => g.id !== id)); },
  setUse(id, use) { return this.saveAll(this.list().map((g) => (g.id === id ? { ...g, use: !!use } : g))); },
  get(id) { return this.list().find((g) => g.id === id) || null; },
  asExemplar(g) {
    // start the excerpt at the first block that carries inline markup, so the model sees the conventions
    let k = g.blocks.findIndex((x) => /<(?!p[\s>]|head[\s>]|\/)[a-zA-Z]/.test(x.replace(/^<[^>]+>/, ""))); if (k < 0) k = 0;
    const part = g.blocks.slice(k, k + 40);
    return { id: g.id, user: true, lang: g.lang, genre: g.genre, licence: g.licence, citation: g.title,
      raw_input: part.map((x) => { try { return sourceText(parseFragment(x)).replace(/\s+/g, " ").trim(); } catch (e) { return ""; } }).join("\n\n"),
      tei_body: "<body>" + part.join("") + "</body>" };
  },
};
const EVAL_TAGS = ["persName", "placeName", "orgName", "rs", "said", "q", "date", "time", "measure", "foreign", "term", "title", "roleName", "name", "head", "l", "sp", "speaker", "stage"];
/** Element spans in whitespace-free source-text offsets (mirror of scripts/eval_knote.py). */
function evalSpans(xmlBlocks) {
  const out = []; let pos = 0;
  for (const x of xmlBlocks) {
    let root; try { root = parseFragment(x); } catch (e) { continue; }
    (function visit(node, skip) {
      for (const ch of node.childNodes) {
        if (ch.nodeType === 3 || ch.nodeType === 4) { if (!skip) pos += norm(ch.nodeValue).length; continue; }
        if (ch.nodeType !== 1) continue;
        const n = lname(ch), s = skip || EDITORIAL.has(n) || (n === "expan" && lname(ch.parentNode) === "choice"), start = pos;
        visit(ch, s);
        if (!s) out.push({ n, s: start, e: pos, who: (ch.getAttribute("who") || "").replace(/^#/, ""), ref: (ch.getAttribute("ref") || "").replace(/^#/, "") });
      }
    })(root, false);
  }
  return out;
}
const evalText = (xmlBlocks) => xmlBlocks.map((x) => { try { return norm(sourceText(parseFragment(x))); } catch (e) { return ""; } }).join("");
/** Map offsets of text a onto text b when they differ slightly (greedy resync, linear time). */
function offsetMap(a, b) {
  if (a === b) return (i) => i;
  const m = new Int32Array(a.length + 1).fill(-1); let i = 0, j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { m[i++] = j++; continue; }
    let found = false;
    for (let d = 1; d < 400 && !found; d++) {
      const ka = a.slice(i, i + 6);
      if (j + d < b.length && b.startsWith(ka, j + d)) { j += d; found = true; }
      else if (i + d < a.length && a.startsWith(b.slice(j, j + 6), i + d)) { i += d; found = true; }
    }
    if (!found) { i++; j++; }
  }
  if (i === a.length) m[i] = j;
  return (x) => (m[x] >= 0 ? m[x] : -1);
}
const prf = (tp, np, ng) => { const p = np ? tp / np : 0, r = ng ? tp / ng : 0, f = p + r ? (2 * p * r) / (p + r) : 0; return [+p.toFixed(3), +r.toFixed(3), +f.toFixed(3)]; };
/** Compare predicted blocks with a gold entry: exact / overlap P-R-F per element, speaker (@who) agreement. */
function evaluateAgainstGold(predBlocks, gold, predRegistry = null) {
  const gt = evalText(gold.blocks), pt = evalText(predBlocks), map = offsetMap(pt, gt);
  const gold_ = evalSpans(gold.blocks), pred = evalSpans(predBlocks).map((x) => ({ ...x, s: map(x.s), e: map(x.e) })).filter((x) => x.s >= 0 && x.e >= 0);
  const tags = EVAL_TAGS.filter((t) => gold_.some((x) => x.n === t) || pred.some((x) => x.n === t));
  const rows = tags.map((t) => {
    const g = gold_.filter((x) => x.n === t && x.e > x.s), p = pred.filter((x) => x.n === t && x.e > x.s);
    const gk = new Map(); for (const x of g) gk.set(`${x.s}:${x.e}`, (gk.get(`${x.s}:${x.e}`) || 0) + 1);
    let exact = 0; for (const x of p) { const k = `${x.s}:${x.e}`; if (gk.get(k) > 0) { exact++; gk.set(k, gk.get(k) - 1); } }
    const used = new Set(); let ov = 0;
    for (const x of p) { const j = g.findIndex((y, jj) => !used.has(jj) && x.s < y.e && y.s < x.e); if (j >= 0) { used.add(j); ov++; } }
    return { tag: t, gold: g.length, pred: p.length, exact: prf(exact, p.length, g.length), overlap: prf(ov, p.length, g.length) };
  });
  // speaker agreement: same said span, names of @who targets agree (ids may differ between encodings)
  const names = (reg, id) => { for (const k of ["persons", "places", "orgs"]) for (const e of (reg || {})[k] || []) if (e.id === id) return [e.name, ...(e.variants || [])].filter(Boolean); return [id]; };
  const gw = new Map(gold_.filter((x) => x.n === "said" && x.who).map((x) => [`${x.s}:${x.e}`, x.who]));
  let tot = 0, ok = 0;
  for (const x of pred) if (x.n === "said" && gw.has(`${x.s}:${x.e}`)) {
    tot++; const a = names(gold.registry, gw.get(`${x.s}:${x.e}`)), b = names(predRegistry, x.who);
    if (x.who && a.some((u) => b.some((v) => u === v || u.includes(v) || v.includes(u)))) ok++;
  }
  const micro = (k) => { const G = rows.reduce((a, r) => a + r.gold, 0), Pn = rows.reduce((a, r) => a + r.pred, 0), T = rows.reduce((a, r) => a + Math.round(r[k][1] * r.gold), 0); return prf(T, Pn, G); };
  return { gold_title: gold.title, text_identical: gt === pt, text_chars: { gold: gt.length, pred: pt.length }, rows,
    micro: { exact: micro("exact"), overlap: micro("overlap") }, who: { compared: tot, match: ok, acc: tot ? +(ok / tot).toFixed(3) : null } };
}

/* ------------------------------------------------------------------ merging several TEI documents */
const TEI_XMLNS_RX = new RegExp(`\\s+xmlns="${TEI_NS.replace(/[.]/g, "\\.")}"`, "g");
function parseTeiDoc(text, name) {
  const doc = domParser.parseFromString(text, "application/xml");
  if (doc.getElementsByTagName("parsererror")[0]) throw new Error(`${name}: well-formed XML이 아닙니다`);
  const r = doc.documentElement;
  if (r.namespaceURI !== TEI_NS || !["TEI", "teiCorpus"].includes(r.localName)) throw new Error(`${name}: TEI 또는 teiCorpus 문서가 아닙니다`);
  return r;
}
/** Rename xml:ids that already occur in earlier documents, and rewrite local #references to them. */
function dedupeIds(roots) {
  const seen = new Set(), renamed = [];
  roots.forEach((root, k) => {
    const all = [root, ...root.getElementsByTagName("*")], map = new Map();
    for (const el of all) { const id = el.getAttributeNS(XML_NS, "id"); if (id && seen.has(id)) { let nid = `${id}_${k + 1}`, c = 2; while (seen.has(nid)) nid = `${id}_${k + 1}_${c++}`; map.set(id, nid); } }
    for (const el of all) {
      const id = el.getAttributeNS(XML_NS, "id");
      if (id && map.has(id)) el.setAttributeNS(XML_NS, "xml:id", map.get(id));
      if (map.size) for (const a of [...el.attributes]) if (a.namespaceURI !== XML_NS && a.value.includes("#"))
        a.value = a.value.split(/(\s+)/).map((t) => (t.startsWith("#") && map.has(t.slice(1)) ? "#" + map.get(t.slice(1)) : t)).join("");
    }
    for (const el of all) { const id = el.getAttributeNS(XML_NS, "id"); if (id) seen.add(id); }
    for (const [a, b] of map) renamed.push(`${a} → ${b}`);
  });
  return renamed;
}
/** docs: [{name, xml}] → teiCorpus: every document keeps its own teiHeader; a corpus header lists the sources. */
function mergeAsCorpus(docs, { title = "", lang = "" } = {}) {
  if (docs.length < 2) throw new Error("합칠 문서를 2개 이상 고르세요.");
  const roots = docs.map((d) => parseTeiDoc(d.xml, d.name)), renamed = dedupeIds(roots);
  const titles = roots.map((r, k) => teiTitle(r) || docs[k].name);
  const L_ = lang || roots[0].getAttributeNS(XML_NS, "lang") || "";
  const hdr = ser(N("teiHeader", null, {},
    N("fileDesc", null, {},
      N("titleStmt", null, {}, N("title", title || titles.join(" · ").slice(0, 200)), N("respStmt", null, {}, N("resp", "Corpus assembled with"), N("name", `${APP_NAME} ${APP_VERSION}`))),
      N("publicationStmt", null, {}, N("p", "Unpublished corpus assembled from the documents listed in the source description.")),
      N("sourceDesc", null, {}, N("listBibl", null, {}, ...titles.map((t, k) => N("bibl", null, {}, N("title", t), N("note", docs[k].name)))))),
    N("revisionDesc", null, {}, N("change", `Merged ${docs.length} TEI documents into a teiCorpus (${renamed.length} duplicate xml:id renamed).`, { when: today() })))).trimEnd();
  const parts = roots.map((r) => xmlSer.serializeToString(r).replace(TEI_XMLNS_RX, "").replace(/^<\?xml[^>]*>\s*/, ""));
  const xml = ['<?xml version="1.0" encoding="UTF-8"?>',
    `<?xml-model href="https://www.tei-c.org/Vault/P5/${TEI_VERSION}/xml/tei/custom/schema/relaxng/tei_all.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>`,
    `<teiCorpus xmlns="${TEI_NS}"${L_ ? ` xml:lang="${escAttr(L_)}"` : ""}>`, hdr.split("\n").map((l) => "  " + l).join("\n"), ...parts, "</teiCorpus>", ""].join("\n");
  return { xml, renamed, titles };
}
/** docs → one TEI Session: each document becomes a top-level <div>; registries are merged (same id + same name = same entity). */
function mergeAsSession(docs, { title = "", divType = "chapter", settings = Settings.load() } = {}) {
  if (docs.length < 2) throw new Error("합칠 문서를 2개 이상 고르세요.");
  const sessions = [], titles = [], authors = [];
  for (const d of docs) {
    const r = parseTeiDoc(d.xml, d.name);
    const tei = r.localName === "TEI" ? [r] : [...r.getElementsByTagNameNS(TEI_NS, "TEI")];
    for (const t of tei) {
      const x = xmlSer.serializeToString(t); sessions.push(Session.fromTei(x, settings)); titles.push(teiTitle(t) || d.name);
      const st = t.getElementsByTagNameNS(TEI_NS, "titleStmt")[0];
      for (const a of st ? st.getElementsByTagNameNS(TEI_NS, "author") : []) { const n = a.textContent.replace(/\s+/g, " ").trim(); if (n && !authors.includes(n)) authors.push(n); }
    }
  }
  const m = new Session("", settings), renamed = [];
  m.genre = sessions[0].genre; m.langs = uniq(sessions.flatMap((s) => s.langs)); m.tagset = uniq(sessions.flatMap((s) => s.tagset));
  sessions.forEach((s, k) => {
    const map = new Map();
    for (const kind of ["persons", "places", "orgs"]) for (const e of s.registry[kind] || []) {
      const hit = ["persons", "places", "orgs"].flatMap((kk) => m.registry[kk]).find((x) => x.id === e.id);
      if (!hit) { m.registry[kind].push({ ...e }); continue; }
      if (hit.name === e.name) continue; // the same entity in two parts of one work
      let nid = `${e.id}_${k + 1}`, c = 2; const ids = m.allIds(); while (ids.has(nid)) nid = `${e.id}_${k + 1}_${c++}`;
      map.set(e.id, nid); m.registry[kind].push({ ...e, id: nid }); renamed.push(`${e.id} → ${nid}`);
    }
    const rx = map.size ? new RegExp(`#(${[...map.keys()].map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})(?=["\\s])`, "g") : null;
    // a document without divisions of its own is wrapped in one <div type=divType n=k>; one that has divisions keeps them as they are
    const wrap = !s.blocks.some((b) => b.div);
    s.blocks.forEach((b, j) => m.blocks.push({ ...b, i: m.blocks.length, xml: rx ? b.xml.replace(rx, (_, id) => "#" + map.get(id)) : b.xml,
      part: wrap && j === 0 ? { type: divType || "chapter", n: String(k + 1), level: 1 } : null }));
  });
  m.raw_text = m.blocks.map((b) => b.raw).join("\n\n");
  m.metadata = { titles: [{ text: title || titles.join(" · ").slice(0, 200), type: "main" }], ...(authors.length ? { authors: authors.map((a) => ({ name: a })) } : {}),
    sources: titles.map((t) => ({ type: "originalSource", title: t })), genre_label: GENRES[m.genre].en };
  m.analysis = { imported: true, notes: `Merged from ${sessions.length} TEI documents.` }; m.status = "tagged";
  m.log("merge_tei", { documents: titles, renamed: renamed.length });
  return { session: m, renamed, titles };
}

/* ------------------------------------------------------------------ storage of sessions (browser-local) */
const Store = {
  list() { try { return JSON.parse(localStorage.getItem("teiagent.index") || "[]"); } catch (e) { return []; } },
  save(s) {
    const d = s.state(); d.snapshots = s.snapshots.slice(-5);
    const t = (s.metadata.titles || [{}])[0]?.text || s.raw_text.slice(0, 30);
    try {
      localStorage.setItem("teiagent.s." + s.id, JSON.stringify(d));
      const idx = this.list().filter((x) => x.id !== s.id); idx.unshift({ id: s.id, title: t, genre: s.genre, saved: nowIso() });
      localStorage.setItem("teiagent.index", JSON.stringify(idx.slice(0, 30)));
      return true;
    } catch (e) {
      try { d.snapshots = []; localStorage.setItem("teiagent.s." + s.id, JSON.stringify(d)); return true; } catch (e2) { return false; }
    }
  },
  load(id) { try { const d = JSON.parse(localStorage.getItem("teiagent.s." + id) || "null"); return d ? Session.fromState(d) : null; } catch (e) { return null; } },
  remove(id) { try { localStorage.removeItem("teiagent.s." + id); localStorage.setItem("teiagent.index", JSON.stringify(this.list().filter((x) => x.id !== id))); } catch (e) { /* ignore */ } },
};

window.TEIAgent = { Session, Settings, Store, agentChat, dispatch, lookupAuthority, rngValidate, checkPreservation, quickCheck, stripDisallowed, toArabic,
  buildHeader, elementCounts, signals, guess, TAGS, GENRES, METADATA_FIELDS, TEI_VERSION, APP_VERSION, LLM, PRESETS: D.PRESETS || {},
  elementNames: () => Object.keys(INDEX.elements).sort(), allowedAttrs: (el) => (INDEX.elements[el] || []).slice(), elementExists,
  Gold, evaluateAgainstGold, mergeAsCorpus, mergeAsSession, selectExemplars, tagRule };
