"""Command line interface.

  tei-agent serve [--port 8765]                 local web UI
  tei-agent tag input.txt -o out.xml [--genre G] [--lang L] [--accept-recommended] [--interactive]
  tei-agent validate file.xml                   tei_all 4.12.0 validation
  tei-agent fix file.xml -o fixed.xml           import existing TEI, LLM-repair schema errors
  tei-agent tools                               print tool schemas (OpenAI/DeepSeek function format)
  tei-agent mcp                                 MCP stdio server (DeepSeek Harness via dsh-mcp-client)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import DATA_DIR, Settings


def _progress(msg, frac):
    print(f"\r  [{int(frac * 100):3d}%] {msg}        ", end="", file=sys.stderr, flush=True)


def cmd_serve(a):
    import uvicorn

    from .server import create_app
    print(f"TEI Agent → http://{a.host}:{a.port}")
    uvicorn.run(create_app(), host=a.host, port=a.port, log_level="warning")


def cmd_tag(a):
    from . import tools
    from .pipeline import Session
    s = Session(Path(a.input).read_text(encoding="utf-8"), Settings.from_env())
    rules = []
    for name in a.preset or []:
        f = DATA_DIR / "presets" / f"{name}.md"
        if not f.exists():
            sys.exit(f"unknown preset {name!r}; available: {', '.join(p.stem for p in sorted((DATA_DIR / 'presets').glob('*.md')))}")
        rules.append(f.read_text(encoding="utf-8"))
    if a.rules:
        rules.append(Path(a.rules).read_text(encoding="utf-8"))
    if rules:
        s.set_project_rules("\n\n".join(rules))
        print(f"   project rules: {', '.join((a.preset or []) + ([a.rules] if a.rules else []))} ({len(s.project_rules)} chars)", file=sys.stderr)
    print("1) analyse …", file=sys.stderr)
    an = s.analyze({"genre": a.genre, "lang": a.lang})
    print(f"   genre={s.genre} langs={s.langs} blocks={len(s.blocks)}\n   {an.get('notes', '')}", file=sys.stderr)
    print("2) entity registry …", file=sys.stderr)
    s.build_registry()
    print("3) tagging …", file=sys.stderr)
    r = s.tag_all(_progress)
    print("\n   ", r["summary"]["tag_counts"], file=sys.stderr)
    rec = s.recommend_tags()
    print("4) recommended additional tags:", file=sys.stderr)
    for t in rec["tags"]:
        print(f"   - [{t['key']}] {t['label']} (~{t.get('estimated_count')}) {t.get('why', '')}", file=sys.stderr)
    if a.accept_recommended:
        keys = [t["key"] for t in rec["tags"] if t.get("priority", 3) <= 2]
        if keys:
            print(f"   applying {keys} …", file=sys.stderr)
            s.accept_tags(keys, progress=_progress)
            print(file=sys.stderr)
    if a.interactive:
        print("\n대화 모드 — 지시를 입력하세요 (빈 줄/exit 로 종료, 'validate', 'meta' 가능)", file=sys.stderr)
        while True:
            try:
                msg = input("> ").strip()
            except EOFError:
                break
            if not msg or msg in ("exit", "quit"):
                break
            out = tools.chat(s, msg, _progress)
            print("\n" + out["reply"])
    print("5) metadata suggestions …", file=sys.stderr)
    m = s.recommend_metadata()
    for sug in m.get("suggestions", [])[:10]:
        flag = " [검증 필요]" if sug.get("needs_verification") else ""
        print(f"   - {sug.get('key')}: {json.dumps(sug.get('patch'), ensure_ascii=False)[:120]} ({sug.get('confidence')}){flag}", file=sys.stderr)
        # auto-apply only values grounded in the text itself; knowledge-based facts need human verification
        if a.accept_recommended and sug.get("confidence") == "high" and not sug.get("needs_verification") and isinstance(sug.get("patch"), dict):
            s.update_metadata(sug["patch"])
    print("6) validate …", file=sys.stderr)
    v = s.validate()
    if not v["valid"] and a.repair:
        s.repair(_progress)
        v = s.validate()
    print(f"   valid={v['valid']} errors={len(v.get('errors', []))} dangling={v.get('dangling_refs')}", file=sys.stderr)
    xml = s.to_xml()[0]
    Path(a.output).write_text(xml, encoding="utf-8")
    path = s.save()
    print(f"→ {a.output}  (session {path}; usage {s.llm.usage.as_dict()})", file=sys.stderr)


def cmd_validate(a):
    from .schema import validate_document
    v = validate_document(Path(a.file).read_text(encoding="utf-8"))
    print(json.dumps(v, ensure_ascii=False, indent=1))
    sys.exit(0 if v["valid"] else 1)


def cmd_fix(a):
    from .pipeline import Session
    s = Session.from_tei(Path(a.file).read_text(encoding="utf-8"), Settings.from_env())
    v = s.validate()
    print(f"before: valid={v['valid']} errors={len(v['errors'])}", file=sys.stderr)
    r = s.repair(_progress)
    print(f"\nafter: valid={r['valid']} remaining={len(r['remaining'])}", file=sys.stderr)
    Path(a.output).write_text(s.to_xml()[0], encoding="utf-8")


def cmd_mcp(a):
    from .mcp_server import main as mcp_main
    mcp_main()


def cmd_tools(a):
    from .tools import TOOLS
    print(json.dumps(TOOLS, ensure_ascii=False, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tei-agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("serve"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8765); p.set_defaults(f=cmd_serve)
    p = sub.add_parser("tag"); p.add_argument("input"); p.add_argument("-o", "--output", required=True)
    p.add_argument("--genre"); p.add_argument("--lang"); p.add_argument("--accept-recommended", action="store_true")
    p.add_argument("--interactive", action="store_true"); p.add_argument("--repair", action="store_true")
    p.add_argument("--rules", help="project rules file (.md/.txt) added to every tagging instruction")
    p.add_argument("--preset", action="append", help="bundled convention preset(s), e.g. knote_conventions, mujeong_class"); p.set_defaults(f=cmd_tag)
    p = sub.add_parser("validate"); p.add_argument("file"); p.set_defaults(f=cmd_validate)
    p = sub.add_parser("fix"); p.add_argument("file"); p.add_argument("-o", "--output", required=True); p.set_defaults(f=cmd_fix)
    p = sub.add_parser("tools"); p.set_defaults(f=cmd_tools)
    p = sub.add_parser("mcp", help="run as an MCP stdio server (for DeepSeek Harness or other MCP hosts)"); p.set_defaults(f=cmd_mcp)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
