"""MCP server (stdio) exposing the TEI Agent to any MCP host — including DeepSeek Harness (dsh),
whose `@deepseek-ai/dsh-mcp-client` plugin mounts external MCP servers (see harness/README.md).

Run:  tei-agent mcp        (or: python -m tei_agent.mcp_server)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import tools as T
from .config import Settings
from .pipeline import Session

try:  # mcp >= 2
    from mcp.server import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore

SETTINGS = Settings.from_env()
_SESSIONS: dict[str, Session] = {}

server = _Server(
    name="tei_agent",
    instructions=("Interactive TEI P5 4.12.0 tagging. Typical flow: tei_new_session(text) → tei_tag(session_id) → "
                  "tei_recommend_tags → ask the user which to add → tei_accept_tags / tei_instruct → tei_recommend_metadata → "
                  "tei_update_metadata → tei_validate → tei_export. Never invent identifiers; use tei_lookup_authority."),
)


def _get(sid: str) -> Session:
    if sid not in _SESSIONS:
        p = SETTINGS.sessions_dir / f"{sid}.json"
        if not p.exists():
            raise ValueError(f"unknown session {sid}")
        _SESSIONS[sid] = Session.load(p, SETTINGS)
    return _SESSIONS[sid]


def _done(s: Session, result) -> str:
    s.save()
    return json.dumps(result, ensure_ascii=False, default=str)[:20000]


@server.tool()
def tei_new_session(text: str, genre: str = "", lang: str = "", title: str = "", author: str = "") -> str:
    """Create a session from raw text and analyse it (language, genre, structure). Returns session_id and analysis."""
    s = Session(text, SETTINGS)
    a = s.analyze({"genre": genre or None, "lang": lang or None})
    if title:
        s.metadata["titles"] = [{"text": title, "type": "main"}]
    if author:
        s.metadata["authors"] = [{"name": author}]
    _SESSIONS[s.id] = s
    return _done(s, {"session_id": s.id, "genre": s.genre, "langs": s.langs, "blocks": len(s.blocks), "notes": a.get("notes")})


@server.tool()
def tei_import(path: str) -> str:
    """Import an existing TEI XML file (header is kept) for validation, repair and further tagging."""
    s = Session.from_tei(Path(path).read_text(encoding="utf-8"), SETTINGS)
    _SESSIONS[s.id] = s
    return _done(s, {"session_id": s.id, "blocks": len(s.blocks), "genre": s.genre})


@server.tool()
def tei_tag(session_id: str) -> str:
    """Build the entity registry and run the automatic first tagging pass."""
    s = _get(session_id)
    if not any(s.registry.values()):
        s.build_registry()
    r = s.tag_all()
    return _done(s, {"summary": r["summary"], "errors": r["errors"][:5]})


@server.tool()
def tei_recommend_tags(session_id: str) -> str:
    """Recommend additional TEI elements (with evidence) and questions for the user."""
    s = _get(session_id)
    return _done(s, T.dispatch(s, "recommend_tags", {}))


@server.tool()
def tei_accept_tags(session_id: str, keys: list[str], guidance: str = "") -> str:
    """Apply recommended tag categories (catalog keys from tei_recommend_tags)."""
    s = _get(session_id)
    return _done(s, T.dispatch(s, "accept_tags", {"keys": keys, "guidance": guidance}))


@server.tool()
def tei_instruct(session_id: str, instruction: str) -> str:
    """Apply a free-form encoding instruction (any language), e.g. 'tag currency amounts with measure'."""
    s = _get(session_id)
    return _done(s, T.dispatch(s, "apply_instruction", {"instruction": instruction}))


@server.tool()
def tei_answer(session_id: str, question_id: str, answer: str) -> str:
    """Answer an open question raised by the tagger and apply the consequence."""
    s = _get(session_id)
    return _done(s, T.dispatch(s, "answer_question", {"question_id": question_id, "answer": answer}))


@server.tool()
def tei_recommend_metadata(session_id: str) -> str:
    """Propose teiHeader values and further header elements worth adding."""
    s = _get(session_id)
    return _done(s, T.dispatch(s, "recommend_metadata", {}))


@server.tool()
def tei_update_metadata(session_id: str, patch: dict) -> str:
    """Merge a patch into the header metadata JSON (titles, authors, sources, licence, creation, keywords, …)."""
    s = _get(session_id)
    return _done(s, T.dispatch(s, "update_metadata", {"patch": patch}))


@server.tool()
def tei_status(session_id: str) -> str:
    """Summary: genre, languages, tag counts, registry sizes, open questions."""
    s = _get(session_id)
    return _done(s, T.dispatch(s, "get_status", {}))


@server.tool()
def tei_show_blocks(session_id: str, block_ids: list[int] | None = None, search: str = "", max: int = 5) -> str:
    """Show encoded blocks by index or search string."""
    s = _get(session_id)
    return _done(s, T.dispatch(s, "show_blocks", {"block_ids": block_ids, "search": search or None, "max": max}))


@server.tool()
def tei_lookup_authority(name: str, lang: str = "en", kind: str = "") -> str:
    """Search Wikidata for candidate identifiers (never add an ID without confirming it)."""
    from .authority import lookup
    return json.dumps(lookup(name, lang, kind), ensure_ascii=False)


@server.tool()
def tei_validate(session_id: str, repair: bool = False) -> str:
    """Validate against tei_all 4.12.0; with repair=true let the model fix failing blocks first."""
    s = _get(session_id)
    if repair:
        s.repair()
    return _done(s, T.dispatch(s, "validate", {}))


@server.tool()
def tei_export(session_id: str, path: str) -> str:
    """Write the TEI XML document to a file path and return a short report."""
    s = _get(session_id)
    xml = s.to_xml()[0]
    Path(path).write_text(xml, encoding="utf-8")
    return _done(s, {"written": path, "bytes": len(xml.encode("utf-8"))})


def main():
    server.run("stdio")


if __name__ == "__main__":
    main()
