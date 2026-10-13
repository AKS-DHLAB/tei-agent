"""Tool registry (OpenAI/DeepSeek function-calling schemas) + a conversational agent loop.

The same schemas are exported by `tei-agent tools` so a DeepSeek Harness (dsh) plugin can later
wrap the local HTTP API one-to-one.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from . import prompts as P
from .authority import lookup
from .pipeline import Session
from .profiles import GENRES, TAGS


def _schema(name: str, desc: str, props: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}


TOOLS = [
    _schema("get_status", "Summary of the current document: genre, languages, tag counts, registry sizes, validation, open questions."),
    _schema("show_blocks", "Show the current TEI xml of some blocks (by index or by a search string).",
            {"block_ids": {"type": "array", "items": {"type": "integer"}}, "search": {"type": "string"},
             "max": {"type": "integer", "default": 5}}),
    _schema("show_registry", "List registered persons/places/orgs with their xml:ids."),
    _schema("recommend_tags", "Recommend additional TEI elements for this text, with evidence and questions for the user."),
    _schema("accept_tags", "Apply recommended tag categories (catalog keys) to the whole document.",
            {"keys": {"type": "array", "items": {"type": "string", "enum": list(TAGS)}},
             "guidance": {"type": "string", "description": "optional extra guidance from the user"}}, ["keys"]),
    _schema("apply_instruction", "Apply a free-form encoding instruction from the user (add/remove/modify markup, scope by blocks or search).",
            {"instruction": {"type": "string"}}, ["instruction"]),
    _schema("answer_question", "Record the user's answer to an open question and apply it.",
            {"question_id": {"type": "string"}, "answer": {"type": "string"}}, ["question_id", "answer"]),
    _schema("recommend_metadata", "Propose header metadata values and further header fields worth adding."),
    _schema("update_metadata", "Merge a patch into the header metadata JSON (titles, authors, sources, licence, creation, keywords, …).",
            {"patch": {"type": "object"}}, ["patch"]),
    _schema("edit_entity", "Add/update/delete/merge a registry entity (person/place/org).",
            {"op": {"type": "string", "enum": ["add", "update", "delete", "merge"]},
             "kind": {"type": "string", "enum": ["person", "place", "org"]}, "id": {"type": "string"},
             "data": {"type": "object"}, "into": {"type": "string"}}, ["op", "kind"]),
    _schema("lookup_authority", "Search Wikidata for candidate identifiers of a person/place/org/work.",
            {"name": {"type": "string"}, "lang": {"type": "string"}, "kind": {"type": "string"}}, ["name"]),
    _schema("set_genre", "Change the genre profile (affects structure rules and recommendations).",
            {"genre": {"type": "string", "enum": list(GENRES)}}, ["genre"]),
    _schema("validate", "Validate the whole document against tei_all 4.12.0 and report errors."),
    _schema("repair", "Ask the model to fix blocks that have schema errors, then re-validate."),
    _schema("undo", "Undo the last change."),
    _schema("find_markup", "Count and show current markup matching a filter (measure before/after a correction). All filters optional.",
            {"element": {"type": "string"}, "text_regex": {"type": "string", "description": "regex on the element's text, e.g. '장로$'"},
             "attr": {"type": "string"}, "value": {"type": "string"}, "missing_attr": {"type": "string"}}),
    _schema("get_project_rules", "Show the project rules (the encoders' own conventions added to every tagging instruction)."),
    _schema("set_project_rules", "Replace or extend the project rules with conventions the user states (e.g. 'title-based references like 김장로 are rs'). Ask before replacing existing rules.",
            {"text": {"type": "string"}, "mode": {"type": "string", "enum": ["append", "replace"]}}, ["text"]),
    _schema("reapply_project_rules", "Re-check all blocks against the current project rules (costs one pass over the text)."),
]


def dispatch(s: Session, name: str, args: dict, progress: Callable | None = None) -> Any:
    if name == "get_status":
        return {**s.summary(), "validation": {k: s.validation.get(k) for k in ("valid", "dangling_refs")} if s.validation else None}
    if name == "show_blocks":
        ids = args.get("block_ids")
        q = args.get("search")
        bl = [b for b in s.blocks if (ids and b["i"] in ids) or (q and q in b["raw"])] if (ids or q) else s.blocks
        return [{"i": b["i"], "xml": b["xml"], "status": b["status"], "warnings": b["warnings"]} for b in bl[: int(args.get("max") or 5)]]
    if name == "show_registry":
        return s.registry
    if name == "recommend_tags":
        return s.recommend_tags()
    if name == "accept_tags":
        return s.accept_tags(args.get("keys", []), args.get("guidance", ""), progress)
    if name == "apply_instruction":
        return s.apply_instruction(args["instruction"], progress)
    if name == "answer_question":
        return s.answer_question(args["question_id"], args["answer"], progress)
    if name == "recommend_metadata":
        return s.recommend_metadata()
    if name == "update_metadata":
        return s.update_metadata(args.get("patch") or {})
    if name == "edit_entity":
        return s.edit_entity(args["op"], args["kind"], args.get("id"), args.get("data"), args.get("into"))
    if name == "lookup_authority":
        return lookup(args["name"], args.get("lang") or (s.langs[0] if s.langs else "en"), args.get("kind", ""))
    if name == "set_genre":
        s.genre = args["genre"]
        s.tagset = list(dict.fromkeys(s.tagset + GENRES[s.genre]["core"]))
        return s.summary()
    if name == "validate":
        v = s.validate()
        return {"valid": v["valid"], "errors": v.get("errors", [])[:20], "dangling_refs": v.get("dangling_refs"),
                "fallback_blocks": v.get("fallback_blocks")}
    if name == "repair":
        return s.repair(progress)
    if name == "undo":
        return {"undone": s.undo()}
    if name == "find_markup":
        return s.find_markup(args.get("element", ""), args.get("text_regex", ""), args.get("attr", ""), args.get("value", ""),
                             args.get("missing_attr", ""))
    if name == "get_project_rules":
        return {"rules": s.project_rules}
    if name == "set_project_rules":
        txt = args.get("text", "")
        return s.set_project_rules(txt if args.get("mode") == "replace" else (s.project_rules + "\n" + txt).strip())
    if name == "reapply_project_rules":
        return s.reapply_project_rules(progress)
    return {"error": f"unknown tool {name}"}


def _short(x: Any, n: int = 6000) -> str:
    t = json.dumps(x, ensure_ascii=False, default=str)
    return t if len(t) <= n else t[:n] + "…(truncated)"


def chat(s: Session, user_message: str, progress: Callable | None = None, max_steps: int = 14) -> dict:
    """One user turn of the conversational agent. History (incl. reasoning_content) lives in s.chat."""
    if not s.chat:
        s.chat.append({"role": "system", "content": P.agent_system(s.s.ui_lang)})
    s.chat.append({"role": "user", "content": user_message})
    actions = []
    for _ in range(max_steps):
        msg = s.llm.chat(s.chat, tools=TOOLS, max_tokens=4000)
        s.chat.append(msg)  # full message, incl. reasoning_content (required by DeepSeek in thinking mode)
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"reply": msg.get("content", ""), "actions": actions}
        for c in calls:
            fn = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                res = dispatch(s, fn, args, progress)
            except Exception as e:  # report tool errors back to the model
                res = {"error": str(e)}
            actions.append({"tool": fn, "args": args})
            s.chat.append({"role": "tool", "tool_call_id": c["id"], "content": _short(res)})
    return {"reply": "(작업 단계가 많아 여기서 멈췄습니다. 이어서 지시해 주세요.)", "actions": actions}
