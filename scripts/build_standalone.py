"""Build the single-file browser version: dist/TEI_Agent.html

Everything the Python package knows (tag catalog, genre profiles, language rules, metadata catalog,
heuristic patterns, TEI 4.12.0 attribute allow-list, few-shot exemplars) is exported as JSON so the
browser version applies exactly the same rules. The tei_all.rng grammar and xmllint (libxml2 → wasm,
MIT) are embedded, so full RELAX NG validation runs locally in the browser. The only network calls
are to the DeepSeek API (and, on request, Wikidata).

  python scripts/build_standalone.py
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tei_agent.config import APP_VERSION, TEI_VERSION  # noqa: E402
from tei_agent.header import MODEL_NAMES  # noqa: E402
from tei_agent.heuristics import PATTERNS, SIGNAL_TO_TAG  # noqa: E402
from tei_agent.profiles import GENERIC_FORMS, GENRES, LANG_RULES, METADATA_FIELDS, TAGS  # noqa: E402
from tei_agent.schema import GLOBAL_ATTRS, index  # noqa: E402

SRC = ROOT / "standalone"
DATA = ROOT / "tei_agent" / "data"
OUT = ROOT / "dist" / "TEI_Agent.html"


def js_patterns() -> dict:
    out = {}
    for k, p in PATTERNS.items():
        flags = "g"
        m = re.match(r"^\(\?([a-z]+)\)", p)
        if m:
            flags += m.group(1)
            p = p[m.end():]
        out[k] = [p, flags]
    return out


def slim_index() -> dict:
    idx = index()
    sets = [set(v["attributes"]) for v in idx.values()]
    common = set.intersection(*sets)
    els, vals = {}, {}
    for name, v in idx.items():
        els[name] = sorted(set(v["attributes"]) - common)
        for a in ("type", "unit", "aloud", "direct", "calendar", "reason", "place", "level"):
            vv = v["attributes"].get(a, {}).get("values")
            if vv:
                vals.setdefault(name, {})[a] = vv[:12]
    return {"common": sorted(common), "elements": els, "values": vals, "cheatsheet_globals": sorted(GLOBAL_ATTRS)}


def exemplars() -> list:
    out = []
    for p in sorted((DATA / "exemplars").glob("*.json")):
        if p.name == "index.json":
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        out.append({k: d[k] for k in ("id", "lang", "genre", "licence", "citation", "raw_input", "tei_body")})
    return out


def worker_source() -> str:
    src = (DATA / "vendor" / "xmllint-wasm" / "xmllint-browser.mjs").read_text(encoding="utf-8")
    old = """			wasmMemory,
			locateFile(path) {
				if (path !== 'xmllint.wasm') {
					return path;
				}
				// Fix wasm file path to be relative to the worker file path.
				// This also makes bundlers automatically pick up the wasm file.
				return new URL('./xmllint.wasm', import.meta.url).href;
			}"""
    new = """			wasmMemory,
			wasmBinary: data.wasmBinary, // patched for TEI Agent: wasm bytes are passed in (works from file://)
			locateFile(path) { return path; }"""
    assert old in src, "xmllint-browser.mjs changed; update the patch"
    src = src.replace(old, new)
    assert "import.meta" not in src
    return src


def main():
    data = {
        "APP_VERSION": APP_VERSION, "TEI_VERSION": TEI_VERSION, "MODEL_NAMES": MODEL_NAMES,
        "TAGS": TAGS, "GENRES": GENRES, "LANG_RULES": LANG_RULES, "METADATA_FIELDS": METADATA_FIELDS,
        "PATTERNS": js_patterns(), "SIGNAL_TO_TAG": SIGNAL_TO_TAG, "INDEX": slim_index(), "EXEMPLARS": exemplars(),
        "PRESETS": {p.stem: p.read_text(encoding="utf-8") for p in sorted((DATA / "presets").glob("*.md"))},
        "GENERIC_FORMS": sorted(GENERIC_FORMS),
    }
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    rng = (DATA / "schema" / "tei_all.rng").read_text(encoding="utf-8")
    assert "</script" not in rng
    wasm_b64 = base64.b64encode((DATA / "vendor" / "xmllint-wasm" / "xmllint.wasm").read_bytes()).decode()
    worker = worker_source()
    assert "</script" not in worker
    web = (ROOT / "tei_agent" / "web" / "index.html").read_text(encoding="utf-8")
    style = web[web.index("<style>"):web.index("</style>") + len("</style>")]
    extra_css = "<style>" + (SRC / "ui.css").read_text(encoding="utf-8") + "</style>"
    body = (SRC / "ui_body.html").read_text(encoding="utf-8")
    app = (SRC / "app.js").read_text(encoding="utf-8")
    ui = (SRC / "ui.js").read_text(encoding="utf-8")
    for name, part in (("app.js", app), ("ui.js", ui)):
        assert "</script" not in part, name
    html = "\n".join([
        "<!doctype html>", '<html lang="ko">', "<head>", '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>TEI Agent {APP_VERSION}</title>",
        '<meta name="description" content="Interactive multilingual TEI P5 tagging with DeepSeek (browser edition)">',
        style, extra_css, "</head>", "<body>", body,
        f'<script type="application/json" id="tei-data">{data_json}</script>',
        f'<script type="text/plain" id="tei-all-rng">{rng}</script>',
        f'<script type="text/plain" id="xmllint-wasm">{wasm_b64}</script>',
        f'<script type="text/plain" id="xmllint-worker">{worker}</script>',
        f"<script>{app}</script>", f"<script>{ui}</script>",
        "</body>", "</html>", ""])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT}  {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
