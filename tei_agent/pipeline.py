"""The tagging workflow as a stateful, serialisable Session.

    analyze()  -> build_registry() -> tag_all()            # automatic first pass
    recommend_tags() / recommend_metadata()                 # suggestions + questions for the user
    apply_instruction("장소명과 화폐 단위도 태깅해줘")         # interactive refinement
    update_metadata({...}) / edit_entity(...)
    validate() -> repair() -> to_xml()
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
from collections import Counter
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from lxml import etree

from . import exemplars as EX
from . import prompts as P
from .config import TEI_NS, TEI_VERSION, Settings
from .header import build_header
from .heuristics import SIGNAL_TO_TAG, guess, script_profile, signals
from .llm import LLM, LLMError
from .profiles import GENERIC_FORMS, GENRES, LANG_RULES, TAGS, metadata_fields_for, tag_rule, tags_for
from .schema import attribute_cheatsheet, quick_check, strip_disallowed, validate_document
from .xmlutils import (check_preservation, element_counts, local, parse_fragment, plain_p, refs_in, source_text,
                       strip_ns, to_string)

Progress = Callable[[str, float], None]


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


_CJ = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def _unwrap_lines(u: str) -> str:
    """Join hard-wrapped lines: no space between Chinese/Japanese characters, a space otherwise."""
    if "\n" not in u:
        return u
    parts = [l.strip() for l in u.split("\n") if l.strip()]
    out = parts[0] if parts else ""
    for l in parts[1:]:
        out += ("" if out and _CJ.match(out[-1]) and _CJ.match(l[0]) else " ") + l
    return out


METADATA_KEYS = {"titles", "authors", "editors", "resp", "funder", "edition", "publication", "licence", "series", "notes",
                 "sources", "msDesc", "recording", "project_desc", "sampling", "editorial", "taxonomies", "abstract",
                 "creation", "languages", "keywords", "corresp", "calendars", "setting", "persons", "places", "orgs",
                 "relations", "source_note"}
FACTUAL_KEYS = {"titles", "authors", "editors", "creation", "sources", "publication", "series", "msDesc", "recording",
                "corresp", "funder", "edition"}
INTERPRETIVE_KEYS = {"abstract", "keywords", "setting", "project_desc", "editorial"}
GROUNDED_OK = {"languages", "persons", "places", "orgs"}
# metadata-catalog field key → key in the metadata JSON model
FIELD_TO_MD = {"title": "titles", "source": "sources", "msdesc": "msDesc", "project": "project_desc", "classDecl": "taxonomies",
               "calendar": "calendars", "pid": "pid"}


def _unwrap_div(xml: str) -> tuple[str, dict | None]:
    """If the model wrapped a block in its own <div>, lift the div into the block's `div` field."""
    try:
        frag = parse_fragment(xml)
    except etree.XMLSyntaxError:
        return xml, None
    kids = [k for k in frag if isinstance(k.tag, str)]
    if len(kids) == 1 and local(kids[0].tag) == "div" and not (frag.text or "").strip() and not (kids[0].tail or "").strip():
        d = kids[0]
        from .schema import inner_xml
        return inner_xml(d).strip(), {"type": d.get("type") or "section", "n": d.get("n"), "level": 1}
    return xml, None


def deep_merge(base: dict, patch: dict) -> dict:
    """Merge dicts recursively; lists are replaced unless the patch list items carry ids that match."""
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


# kinship terms, titles and address forms that many characters share: never used to re-point a reference
# GENERIC_FORMS: kinship terms/titles by language, defined in profiles.py


PROJECT_RULES_MAX = 8000


def _fatal(e: Exception) -> bool:
    return "(401)" in str(e) or "(402)" in str(e)


def _nospace(t: str) -> str:
    return re.sub(r"\s+", "", t or "")


def _strip_paren(t: str) -> str:
    return re.sub(r"\s*[\(（][^)）]*[\)）]", "", t or "")


class Session:
    def __init__(self, raw_text: str = "", settings: Settings | None = None, llm: LLM | None = None, sid: str | None = None):
        self.s = settings or Settings.from_env()
        self.llm = llm or LLM(self.s)
        self.id = sid or uuid.uuid4().hex[:10]
        self.created = _now()
        self.raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        self.analysis: dict = {}
        self.genre = "generic"
        self.langs: list[str] = []
        self.tagset: list[str] = []
        self.registry: dict = {"persons": [], "places": [], "orgs": []}
        self.metadata: dict = {}
        self.blocks: list[dict] = []
        self.extra_ids: list[str] = []  # xml:ids declared elsewhere (imported header/standOff)
        self.project_rules: str = ""  # encoders' own conventions (e.g. a class style sheet), added to every tagging prompt
        self.header_override: str | None = None  # raw <teiHeader> kept when importing existing TEI
        self.standoff_override: str | None = None
        self.recommendations: dict = {}
        self.meta_recommendations: dict = {}
        self.questions: list[dict] = []
        self.history: list[dict] = []
        self.chat: list[dict] = []
        self.snapshots: list[str] = []
        self.validation: dict = {}
        self.status = "new"
        self.progress = 0.0

    # ------------------------------------------------------------------ persistence
    STATE_KEYS = ("id", "created", "raw_text", "project_rules", "analysis", "genre", "langs", "tagset", "registry", "metadata", "blocks",
                  "header_override", "standoff_override", "extra_ids", "recommendations", "meta_recommendations", "questions",
                  "history", "chat", "validation", "status")

    def state(self) -> dict:
        d = {k: getattr(self, k) for k in self.STATE_KEYS}
        d["usage"] = self.llm.usage.as_dict()
        return d

    def save(self, directory: Path | None = None) -> Path:
        directory = Path(directory or self.s.sessions_dir)
        directory.mkdir(parents=True, exist_ok=True)
        p = directory / f"{self.id}.json"
        d = self.state()
        d["snapshots"] = self.snapshots[-10:]
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: Path, settings: Settings | None = None, llm: LLM | None = None) -> "Session":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        s = cls(d.get("raw_text", ""), settings, llm, sid=d["id"])
        for k in cls.STATE_KEYS:
            if k in d:
                setattr(s, k, d[k])
        s.snapshots = d.get("snapshots", [])
        return s

    def _snapshot(self, label: str):
        self.snapshots.append(json.dumps({"label": label, "blocks": self.blocks, "registry": self.registry,
                                          "metadata": self.metadata, "tagset": self.tagset}, ensure_ascii=False))
        self.snapshots = self.snapshots[-15:]

    def undo(self) -> str:
        if not self.snapshots:
            return "nothing to undo"
        d = json.loads(self.snapshots.pop())
        self.blocks, self.registry, self.metadata, self.tagset = d["blocks"], d["registry"], d["metadata"], d["tagset"]
        self._log("undo", d["label"])
        return d["label"]

    def _log(self, action: str, detail) -> None:
        self.history.append({"when": _now(), "action": action, "detail": detail})

    # ------------------------------------------------------------------ 1. analysis
    def analyze(self, hints: dict | None = None) -> dict:
        hints = hints or {}
        h = guess(self.raw_text)
        sample = self.raw_text[:7000] + ("\n…\n" + self.raw_text[-1500:] if len(self.raw_text) > 9000 else "")
        try:
            a = self.llm.json(P.analyze_system(self.s.ui_lang),
                              f"Script profile (%): {h['scripts']}\nUser hints: {json.dumps(hints, ensure_ascii=False)}\n\nTEXT:\n{sample}",
                              max_tokens=2000)
        except LLMError as e:
            a = h
            a["notes"] = f"LLM analysis unavailable ({e}); heuristic guess used."
        a["scripts"] = h["scripts"]
        a["signals"] = {k: v for k, v in signals(self.raw_text).items()}
        if hints.get("genre") in GENRES:
            a["genre"] = hints["genre"]
        if hints.get("lang"):
            a["main_lang"] = hints["lang"]
        self.analysis = a
        self.genre = a.get("genre") if a.get("genre") in GENRES else "generic"
        self.langs = [l.get("ident") for l in a.get("languages", []) if l.get("ident")] or [a.get("main_lang", "en")]
        self.tagset = list(GENRES[self.genre]["core"])
        # seed metadata from analysis
        md = self.metadata
        if a.get("title") and not md.get("titles"):
            md["titles"] = [{"text": a["title"], "type": "main", "lang": a.get("main_lang")}]
        if a.get("author") and not md.get("authors"):
            md["authors"] = [{"name": a["author"], "lang": a.get("main_lang")}]
        if a.get("languages") and not md.get("languages"):
            md["languages"] = a["languages"]
        if a.get("period") and not md.get("creation"):
            md["creation"] = {"date": a["period"]}
        md.setdefault("genre_label", GENRES[self.genre]["en"])
        self.blocks = self.segment()
        self.status = "analyzed"
        self._log("analyze", {"genre": self.genre, "langs": self.langs, "blocks": len(self.blocks)})
        return a

    def segment(self) -> list[dict]:
        text = self.raw_text.strip("\n")
        paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        lines = [l for l in text.split("\n") if l.strip()]
        verse_like = self.genre in ("poetry", "drama")
        if verse_like:
            units = paras if len(paras) >= 2 else lines
        elif self.genre in ("speech_transcript", "dictionary") or len(paras) < max(2, len(lines) / 8):
            units = lines
        else:
            units = paras
        out = []
        for u in units:
            u = u.strip("\n")
            if not verse_like:
                u = _unwrap_lines(u)
            out.append({"i": len(out), "raw": u.strip(), "xml": plain_p(u), "div": None, "status": "raw", "warnings": []})
        return out

    # ------------------------------------------------------------------ 2. registry
    REGISTRY_WINDOW = 60_000

    def build_registry(self) -> dict:
        """Registry over the WHOLE text: consecutive windows, each told which ids already exist (one cast list for a
        novel, not one per chapter). Entities whose name/variants never occur in the text are dropped (grounding)."""
        text = self.raw_text
        windows = [text[k:k + self.REGISTRY_WINDOW] for k in range(0, max(len(text), 1), self.REGISTRY_WINDOW)] or [""]
        merged: dict[str, list[dict]] = {"persons": [], "places": [], "orgs": []}
        seen: set[str] = set()
        for w_i, window in enumerate(windows):
            known = self._registry_lines(merged)
            user = (P.project_rules_block(self.project_rules, for_registry=True)) + ("ALREADY REGISTERED (reuse these ids; list only entities NOT yet registered, or an existing id with new variants):\n"
                    + known + "\n\n" if known else "") + "TEXT:\n" + window
            try:
                reg = self.llm.json(P.registry_system(self.s.ui_lang, self.genre), user, max_tokens=12000)
            except LLMError as e:
                if _fatal(e):
                    raise
                self._log("registry_failed", f"window {w_i}: {e}")
                continue
            for kind in ("persons", "places", "orgs"):
                for e in reg.get(kind, []) or []:
                    if not isinstance(e, dict):
                        continue
                    eid = re.sub(r"[^A-Za-z0-9_.-]", "", str(e.get("id") or ""))
                    existing = next((x for x in merged[kind] if x["id"] == eid), None)
                    if existing is not None:  # new variants for a known entity
                        existing["variants"] = list(dict.fromkeys((existing.get("variants") or []) + (e.get("variants") or [])))
                        continue
                    if not eid or not eid[0].isalpha():
                        eid = ("P" if kind == "persons" else "L" if kind == "places" else "O") + str(len(seen) + 1)
                    while eid in seen:
                        eid += "_"
                    seen.add(eid)
                    e["id"] = eid
                    merged[kind].append(e)
        dropped = []
        for kind in merged:
            keep = []
            for e in merged[kind]:
                forms = [e.get("name") or ""] + list(e.get("variants") or [])
                e["variants"] = [v for v in (e.get("variants") or []) if isinstance(v, str) and _nospace(v) and _nospace(v) in _nospace(text)]
                if any(f and _nospace(_strip_paren(f)) and _nospace(_strip_paren(f)) in _nospace(text) for f in forms if isinstance(f, str)):
                    keep.append(e)
                else:
                    dropped.append(e.get("name"))
            merged[kind] = keep
        self.registry = merged
        self._merge_duplicate_names(rewrite=False)
        self._log("registry", {**{k: len(v) for k, v in self.registry.items()}, "windows": len(windows), "dropped_ungrounded": dropped[:50]})
        return self.registry

    def _registry_lines(self, reg: dict) -> str:
        out = []
        for kind, label in (("persons", "PERSON"), ("places", "PLACE"), ("orgs", "ORG")):
            for e in reg.get(kind, []):
                out.append(f"{label} #{e['id']} = {e.get('name')}" + (f" (also: {', '.join((e.get('variants') or [])[:6])})" if e.get("variants") else ""))
        return "\n".join(out)

    def fix_name_refs(self) -> list[dict]:
        """Deterministic check on proper names: if the text of a <persName>/<placeName>/<orgName> is exactly the
        name or a variant of ONE registered entity and the @ref points elsewhere, re-point it (e.g. 월향 -> 박영채,
        not 계월화). Returns the list of fixes (logged)."""
        owners: dict[str, set] = {}
        for kind in ("persons", "places", "orgs"):
            for e in self.registry.get(kind, []):
                for f in [e.get("name")] + list(e.get("variants") or []):
                    k = _nospace(_strip_paren(f or ""))
                    if len(k) >= 2 and k not in GENERIC_FORMS and not k.lower() in GENERIC_FORMS:
                        owners.setdefault(k, set()).add(e["id"])
        fixes: list[dict] = []
        pat = re.compile(r'<(persName|placeName|orgName)\b([^>]*?)\bref="#([^"\s]+)"([^>]*)>([^<]+)</\1>')
        for b in self.blocks:
            def sub(m):
                text = _nospace(m.group(5))
                cand = owners.get(text, set())
                if len(cand) == 1 and m.group(3) not in cand:
                    new_id = next(iter(cand))
                    fixes.append({"block": b["i"], "text": m.group(5), "from": m.group(3), "to": new_id})
                    return f'<{m.group(1)}{m.group(2)}ref="#{new_id}"{m.group(4)}>{m.group(5)}</{m.group(1)}>'
                return m.group(0)
            b["xml"] = pat.sub(sub, b["xml"])
        if fixes:
            self._log("ref_fixes", {"count": len(fixes), "sample": fixes[:20]})
        return fixes

    def _merge_duplicate_names(self, rewrite: bool = True) -> dict[str, str]:
        """Deterministic consolidation: entities of the same kind with the same canonical name (ignoring spaces and
        parentheses), or a later entity whose name is exactly an earlier entity's multi-character variant used by no
        other entity, become one id. @ref/@who in the blocks are rewritten. Returns {old_id: kept_id}."""
        alias: dict[str, str] = {}
        for kind in ("persons", "places", "orgs"):
            ents = self.registry.get(kind, [])
            by_name: dict[str, dict] = {}
            variant_owner: dict[str, set] = {}
            for e in ents:
                for v in (e.get("variants") or []):
                    variant_owner.setdefault(_nospace(v), set()).add(e["id"])
            keep = []
            for e in ents:
                key = _nospace(_strip_paren(e.get("name") or ""))
                target = by_name.get(key)
                if target is None and key and len(key) >= 2:
                    owners = variant_owner.get(key, set()) - {e["id"]}
                    if len(owners) == 1:
                        target = next((x for x in keep if x["id"] in owners), None)
                if target is not None and target["id"] != e["id"]:
                    alias[e["id"]] = target["id"]
                    target["variants"] = list(dict.fromkeys((target.get("variants") or []) + [e.get("name")] + (e.get("variants") or [])))
                    continue
                if key:
                    by_name[key] = e
                keep.append(e)
            self.registry[kind] = keep
        if alias and rewrite:
            def fix(m):
                toks = [("#" + alias.get(t[1:], t[1:])) if t.startswith("#") else t for t in m.group(2).split()]
                return f'{m.group(1)}="{" ".join(dict.fromkeys(toks))}"'
            for b in self.blocks:
                b["xml"] = re.sub(r'\b(ref|who)="([^"]*)"', fix, b["xml"])
        if alias:
            self._log("registry_merge", alias)
        return alias

    def registry_text(self, max_items: int = 300) -> str:
        lines = []
        for kind, label in (("persons", "PERSON"), ("places", "PLACE"), ("orgs", "ORG")):
            for e in self.registry.get(kind, [])[:max_items]:
                v = ", ".join(e.get("variants", [])[:8])
                lines.append(f"{label} #{e['id']} = {e.get('name')}" + (f" (also: {v})" if v else "") + (f" — {e['note']}" if e.get("note") else ""))
        return "\n".join(lines) or "(empty — create ids as needed and report them in new_entities)"

    def all_ids(self) -> set[str]:
        return {e["id"] for k in ("persons", "places", "orgs") for e in self.registry.get(k, [])} | set(self.extra_ids)

    # ------------------------------------------------------------------ 3. tagging
    def _tag_system(self, tag_keys: list[str] | None = None) -> str:
        keys = tag_keys or self.tagset
        els = tags_for(self.genre, keys) + ["p", "head", "div", "pb", "lb", "note"]
        lang_rules = " ".join(LANG_RULES[l.split("-")[0]] for l in dict.fromkeys(self.langs) if l.split("-")[0] in LANG_RULES)
        ex = EX.select(self.genre, [l.split("-")[0] for l in self.langs], GENRES[self.genre].get("exemplars", []), k=2)
        return P.tag_system(genre=self.genre, tag_keys=keys, lang_rules=lang_rules or "Preserve the source orthography.",
                            cheatsheet=attribute_cheatsheet(els), exemplars="\n\n".join(EX.format_exemplar(e) for e in ex),
                            registry=self.registry_text(), ui_lang=self.s.ui_lang, page_numbers=self.page_numbers(),
                            extra=P.project_rules_block(self.project_rules), langs=self.langs)

    def chunks(self, blocks: list[dict] | None = None) -> list[list[dict]]:
        blocks = self.blocks if blocks is None else blocks
        out, cur, size = [], [], 0
        for b in blocks:
            n = len(b.get("raw", "")) + len(b.get("xml", "")) // 3
            if cur and size + n > self.s.chunk_chars:
                out.append(cur)
                cur, size = [], 0
            cur.append(b)
            size += n
        if cur:
            out.append(cur)
        return out

    def _accept(self, block: dict, xml: str, mode: str) -> list[str]:
        """Validate one block's proposed xml. Returns list of problems (empty if accepted)."""
        problems = []
        pres = check_preservation(block["raw"], xml, self.page_numbers())
        if not pres["ok"]:
            problems += pres["problems"]
        else:
            q = quick_check(xml)
            problems += q
        return problems

    def _run_chunk(self, system: str, chunk: list[dict], user_msg: str, mode: str) -> dict:
        """One LLM request for a chunk + one repair round + deterministic fallbacks."""
        result = {"new_entities": [], "uncertain": [], "errors": []}
        by_i = {b["i"]: b for b in chunk}
        try:
            data = self.llm.json(system, user_msg, max_tokens=min(self.s.max_tokens, 8000 + 6 * sum(len(b["raw"]) for b in chunk)))
        except LLMError as e:
            if _fatal(e):
                raise
            result["errors"].append(str(e))
            return result
        result["new_entities"] += data.get("new_entities", []) or []
        result["uncertain"] += data.get("uncertain", []) or []
        proposals = {}
        for item in data.get("blocks", []) or []:
            try:
                i = int(item.get("i"))
            except (TypeError, ValueError):
                continue
            if i in by_i and isinstance(item.get("xml"), str):
                proposals[i] = item
        failing = []
        for i, item in proposals.items():
            probs = self._accept(by_i[i], item["xml"], mode)
            if probs:
                failing.append({"i": i, "your_xml": item["xml"], "source_text": by_i[i]["raw"], "problems": probs})
        if failing:
            try:
                fix = self.llm.json(system, user_msg + "\n\n" + P.repair_user(failing), max_tokens=12000)
                for item in fix.get("blocks", []) or []:
                    try:
                        i = int(item.get("i"))
                    except (TypeError, ValueError):
                        continue
                    if i in proposals and isinstance(item.get("xml"), str):
                        proposals[i]["xml"] = item["xml"]
                        proposals[i]["_repaired"] = True
            except LLMError as e:
                result["errors"].append(f"repair failed: {e}")
        for i, item in proposals.items():
            b = by_i[i]
            xml = item["xml"].strip()
            if mode == "tag":
                xml, inner_div = _unwrap_div(xml)
                if inner_div and not (isinstance(item.get("div"), dict) and item["div"].get("type")):
                    item["div"] = inner_div
            pres = check_preservation(b["raw"], xml, self.page_numbers())
            if not pres["ok"]:
                b["warnings"] = [f"text changed by model → kept previous markup: {pres['problems'][:2]}"]
                b["status"] = "fallback"
                continue
            if quick_check(xml):
                try:
                    xml, log = strip_disallowed(xml)
                    b["warnings"] = [f"auto-fixed: {', '.join(log[:5])}"]
                except etree.XMLSyntaxError:
                    b["status"] = "fallback"
                    continue
            else:
                b["warnings"] = []
            if pres["removed"]:
                b["warnings"].append(f"removed page-number-like text: {pres['removed']}")
            b["xml"] = xml
            b["status"] = "repaired" if item.get("_repaired") else "tagged"
            if mode == "tag":
                d = item.get("div")
                b["div"] = d if isinstance(d, dict) and d.get("type") else None
        missing = [i for i in by_i if i not in proposals]
        if missing:
            result["errors"].append(f"model returned no output for blocks {missing}")
        return result

    def page_numbers(self) -> bool:
        """Dropping page-number text (→ <pb n/>) is tolerated only if the analysis found page numbers."""
        return bool((self.analysis.get("structure") or {}).get("page_numbers"))

    def _merge_entities(self, new: list[dict]) -> None:
        ids = self.all_ids()
        for e in new:
            kind = {"person": "persons", "place": "places", "org": "orgs"}.get(e.get("kind"), "persons")
            eid = re.sub(r"[^A-Za-z0-9_.-]", "", str(e.get("id") or ""))
            if eid and eid[0].isalpha() and eid not in ids:
                self.registry[kind].append({"id": eid, "name": e.get("name"), "variants": [], "note": e.get("note", "")})
                ids.add(eid)

    def _parallel(self, system: str, chunks: list[list[dict]], make_user: Callable, mode: str, progress: Progress | None):
        uncertain, errors, new = [], [], []
        done = 0

        def work(idx_chunk):
            idx, ch = idx_chunk
            ctx = self.blocks[ch[0]["i"] - 1]["raw"] if ch[0]["i"] > 0 and mode == "tag" else ""
            return self._run_chunk(system, ch, make_user(ch, ctx), mode)

        with ThreadPoolExecutor(max_workers=max(1, self.s.max_workers)) as pool:
            for r in pool.map(work, list(enumerate(chunks))):
                done += 1
                new += r["new_entities"]
                uncertain += r["uncertain"]
                errors += r["errors"]
                self.progress = done / max(1, len(chunks))
                if progress:
                    progress(f"{done}/{len(chunks)} chunks", self.progress)
        self._merge_entities(new)
        return uncertain, errors

    def tag_all(self, progress: Progress | None = None) -> dict:
        if not self.blocks:
            self.blocks = self.segment()
        self._snapshot("before automatic tagging")
        self.status = "tagging"
        system = self._tag_system()
        uncertain, errors = self._parallel(system, self.chunks(), lambda ch, ctx: P.tag_user(ch, ctx), "tag", progress)
        self.reconcile_registry()
        self._merge_duplicate_names()
        self.fix_name_refs()
        self._add_questions_from_uncertain(uncertain)
        self.status = "tagged"
        summary = self.summary()
        self._log("tag_all", {"tagset": self.tagset, "errors": errors[:5], "counts": summary["tag_counts"]})
        return {"summary": summary, "errors": errors, "uncertain": uncertain}

    def _add_questions_from_uncertain(self, uncertain: list[dict]):
        for u in uncertain[:30]:
            if not isinstance(u, dict) or not u.get("question"):
                continue
            if any(q["question"] == u["question"] for q in self.questions):
                continue
            self.questions.append({"id": f"u{len(self.questions) + 1}", "question": u["question"], "about": u.get("text", ""),
                                   "block": u.get("i"), "options": [], "source": "tagging", "answered": False})

    def reconcile_registry(self) -> list[str]:
        """Add registry entries for dangling @ref/@who targets (named from the first tagged mention)."""
        ids = self.all_ids()
        added = []
        for b in self.blocks:
            try:
                frag = parse_fragment(b["xml"])
            except etree.XMLSyntaxError:
                continue
            for el in frag.iter():
                if not isinstance(el.tag, str):
                    continue
                for att in ("ref", "who"):
                    for tok in (el.get(att) or "").split():
                        if tok.startswith("#") and tok[1:] not in ids:
                            name = local(el.tag)
                            kind = "places" if name in ("placeName", "geogName") or el.get("type") == "place" else \
                                "orgs" if name == "orgName" or el.get("type") == "org" else "persons"
                            txt = re.sub(r"\s+", " ", source_text(el)).strip()[:40] if att == "ref" else tok[1:]
                            self.registry[kind].append({"id": tok[1:], "name": txt or tok[1:], "variants": [], "note": "auto-added from text"})
                            ids.add(tok[1:])
                            added.append(tok[1:])
        return added

    # ------------------------------------------------------------------ 4. recommendations
    def summary(self) -> dict:
        counts = element_counts([b["xml"] for b in self.blocks])
        st = {}
        for b in self.blocks:
            st[b["status"]] = st.get(b["status"], 0) + 1
        return {"genre": self.genre, "genre_label": GENRES[self.genre]["ko"], "langs": self.langs, "blocks": len(self.blocks),
                "block_status": st, "tag_counts": counts, "tagset": self.tagset,
                "registry": {k: len(v) for k, v in self.registry.items()},
                "open_questions": sum(1 for q in self.questions if not q.get("answered"))}

    def recommend_tags(self) -> dict:
        sig = signals(self.raw_text)
        candidates = [k for k in GENRES[self.genre]["optional"] + GENRES["generic"]["optional"] if k not in self.tagset]
        candidates = list(dict.fromkeys(candidates))
        evidence = {}
        for s, v in sig.items():
            k = SIGNAL_TO_TAG.get(s)
            if k and k in candidates:
                evidence.setdefault(k, {"count": 0, "examples": []})
                evidence[k]["count"] += v["count"]
                evidence[k]["examples"] += v["examples"][:2]
        sample = self.raw_text[:6000]
        try:
            rec = self.llm.json(P.recommend_tags_system(self.s.ui_lang, self.genre, candidates, self.langs),
                                P.project_rules_block(self.project_rules, for_registry=True) + f"Current tag counts: {self.summary()['tag_counts']}\nRegex evidence: {json.dumps(evidence, ensure_ascii=False)}\n\nTEXT SAMPLE:\n{sample}",
                                max_tokens=4000)
        except LLMError as e:
            rec = {"tags": [{"key": k, "why": f"텍스트에서 관련 패턴 {v['count']}건 발견", "examples": v["examples"][:3],
                             "estimated_count": v["count"], "priority": 2} for k, v in evidence.items()],
                   "questions": [], "note": f"LLM unavailable: {e}"}
        tags = []
        for t in rec.get("tags", []):
            if t.get("key") in TAGS and t["key"] not in self.tagset:
                t["label"] = TAGS[t["key"]]["ko"]
                t["elements"] = TAGS[t["key"]]["elements"]
                t["regex_evidence"] = evidence.get(t["key"])
                tags.append(t)
        # make sure strong regex evidence is not lost
        for k, v in evidence.items():
            if v["count"] >= 3 and all(t["key"] != k for t in tags):
                tags.append({"key": k, "label": TAGS[k]["ko"], "elements": TAGS[k]["elements"], "why": "정규식 탐지 결과 해당 패턴이 반복됩니다.",
                             "examples": v["examples"][:3], "estimated_count": v["count"], "priority": 3, "regex_evidence": v})
        tags.sort(key=lambda t: (t.get("priority", 3), -int(t.get("estimated_count") or 0)))
        self.recommendations = {"tags": tags, "generated": _now()}
        for q in rec.get("questions", []) or []:
            if not isinstance(q, dict) or not q.get("question") or any(x["question"] == q["question"] for x in self.questions):
                continue
            q.update({"id": f"t{len(self.questions) + 1}", "source": "recommend_tags", "answered": False})
            self.questions.append(q)
        self._log("recommend_tags", [t["key"] for t in tags])
        return {"tags": tags, "questions": [q for q in self.questions if not q.get("answered")]}

    def _ungrounded(self, patch: dict) -> list[str]:
        """Factual string values in a metadata patch that do not occur in the source text."""
        text = re.sub(r"\s+", "", self.raw_text)
        skip_keys = {"type", "level", "lang", "ident", "label", "unit", "role", "scheme", "status", "target", "usage", "kind"}
        out = []

        def walk(o, key=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k not in skip_keys:
                        walk(v, k)
            elif isinstance(o, list):
                for x in o:
                    walk(x, key)
            elif isinstance(o, str) and len(o.strip()) >= 2 and not o.startswith("http"):
                if re.sub(r"\s+", "", o) not in text:
                    out.append(o)

        walk({k: v for k, v in patch.items() if k in FACTUAL_KEYS})
        return out

    def recommend_metadata(self) -> dict:
        fields = metadata_fields_for(self.genre)
        present = {k for k, v in self.metadata.items() if v}
        present |= {k for k in ("persons", "places", "orgs") if self.registry.get(k)}
        if (self.metadata.get("publication") or {}).get("idnos"):
            present.add("pid")
        missing = [f for f in fields if FIELD_TO_MD.get(f["key"], f["key"]) not in present
                   and f["key"] not in ("tagsDecl", "appInfo", "extent", "revisions")]
        excerpt = self.raw_text[:4000] + ("\n…\n" + self.raw_text[-1500:] if len(self.raw_text) > 6000 else "")
        try:
            rec = self.llm.json(P.recommend_meta_system(self.s.ui_lang, self.genre),
                                f"Current metadata JSON: {json.dumps(self.metadata, ensure_ascii=False)}\n"
                                f"Analysis: {json.dumps({k: self.analysis.get(k) for k in ('languages', 'genre', 'period', 'title', 'author', 'notes')}, ensure_ascii=False)}\n"
                                f"Registry sizes: {self.summary()['registry']}\n\nTEXT EXCERPTS:\n{excerpt}", max_tokens=5000)
        except LLMError as e:
            rec = {"suggestions": [], "to_lookup": [], "questions": [], "note": f"LLM unavailable: {e}"}
        from .authority import strip_identifiers
        sugg, lookups = [], list(rec.get("to_lookup", []) or [])
        for sg in rec.get("suggestions", []) or []:
            if not isinstance(sg, dict) or not isinstance(sg.get("patch"), dict):
                continue
            removed: list = []
            sg["patch"] = strip_identifiers(sg["patch"], removed)
            if removed:
                sg["identifiers_removed"] = [f"{n}: {v}" for n, v in removed]
                lookups += [{"kind": sg.get("key", ""), "name": n, "lang": (self.langs or ["en"])[0]} for n, _ in removed if n]
            sg["patch"] = {k: v for k, v in sg["patch"].items() if k in METADATA_KEYS}
            if not sg["patch"]:
                continue
            ungrounded = self._ungrounded(sg["patch"]) if any(k in FACTUAL_KEYS for k in sg["patch"]) else []
            if ungrounded:
                sg["needs_verification"] = True
                sg["not_in_text"] = ungrounded[:6]
            elif any(k in INTERPRETIVE_KEYS for k in sg["patch"]):
                sg["needs_verification"] = True
                sg["model_written"] = True
            else:
                sg["needs_verification"] = sg.get("basis") != "text" and not any(k in GROUNDED_OK for k in sg["patch"])
            sugg.append(sg)
        seen = set()
        rec["to_lookup"] = [l for l in lookups if isinstance(l, dict) and l.get("name") and not (l["name"] in seen or seen.add(l["name"]))]
        self.meta_recommendations = {
            "suggestions": sugg,
            "to_lookup": rec.get("to_lookup", []),
            "missing_fields": [{"key": f["key"], "level": f["level"], "label": f["ko"], "path": f["path"], "why": f["why"]} for f in missing],
            "generated": _now()}
        for q in rec.get("questions", []) or []:
            if not isinstance(q, dict) or not q.get("question") or any(x["question"] == q["question"] for x in self.questions):
                continue
            q.update({"id": f"m{len(self.questions) + 1}", "source": "recommend_metadata", "answered": False})
            self.questions.append(q)
        self._log("recommend_metadata", len(self.meta_recommendations["suggestions"]))
        return self.meta_recommendations

    # ------------------------------------------------------------------ 5. refinement
    def accept_tags(self, keys: list[str], extra_instruction: str = "", progress: Progress | None = None) -> dict:
        keys = [k for k in keys if k in TAGS]
        if not keys:
            return {"changed": 0}
        if self.recommendations.get("tags"):
            self.recommendations["tags"] = [t for t in self.recommendations["tags"] if t["key"] not in keys]
        instr = "Add the following markup wherever it applies: " + "; ".join(tag_rule(k, self.langs) for k in keys)
        if extra_instruction:
            instr += " Additional guidance from the user: " + extra_instruction
        return self.retag(instr, add_keys=keys, progress=progress)

    def retag(self, instruction: str, *, add_keys: list[str] | None = None, remove_keys: list[str] | None = None,
              block_ids: list[int] | None = None, search: list[str] | None = None, progress: Progress | None = None) -> dict:
        self._snapshot(f"before: {instruction[:60]}")
        for k in add_keys or []:
            if k not in self.tagset:
                self.tagset.append(k)
        for k in remove_keys or []:
            if k in self.tagset:
                self.tagset.remove(k)
        targets = self.blocks
        if block_ids:
            ids = set(int(i) for i in block_ids)
            targets = [b for b in self.blocks if b["i"] in ids]
        elif search:
            targets = [b for b in self.blocks if any(s and s in b["raw"] for s in search)]
        before = {b["i"]: b["xml"] for b in targets}
        system = P.retag_system(self._tag_system(), instruction)
        uncertain, errors = self._parallel(system, self.chunks(targets), lambda ch, ctx: P.retag_user(ch), "retag", progress)
        self.reconcile_registry()
        self._merge_duplicate_names()
        self.fix_name_refs()
        self._add_questions_from_uncertain(uncertain)
        changed = sum(1 for b in targets if b["xml"] != before[b["i"]])
        self._log("retag", {"instruction": instruction, "targets": len(targets), "changed": changed, "errors": errors[:3]})
        return {"changed": changed, "targets": len(targets), "errors": errors, "summary": self.summary()}

    def find_markup(self, element: str = "", text_regex: str = "", attr: str = "", value: str = "",
                    missing_attr: str = "", max_examples: int = 8) -> dict:
        """Deterministic search over the current markup (for measuring before/after a correction)."""
        try:
            rx = re.compile(text_regex) if text_regex else None
        except re.error as e:
            return {"error": f"bad regex: {e}"}
        n, texts, ex = 0, Counter(), []
        for b in self.blocks:
            try:
                frag = parse_fragment(b["xml"])
            except etree.XMLSyntaxError:
                continue
            for el in frag.iter():
                if not isinstance(el.tag, str) or (element and local(el.tag) != element):
                    continue
                txt = re.sub(r"\s+", " ", source_text(el)).strip()
                if rx and not rx.search(txt):
                    continue
                if attr and (el.get(attr) is None or (value and el.get(attr) != value)):
                    continue
                if missing_attr and el.get(missing_attr) is not None:
                    continue
                n += 1
                texts[txt[:30]] += 1
                if len(ex) < max_examples:
                    ex.append({"block": b["i"], "xml": etree.tostring(el, encoding="unicode", with_tail=False)[:200]})
        return {"count": n, "top_texts": texts.most_common(10), "examples": ex}

    def set_project_rules(self, text: str) -> dict:
        self.project_rules = (text or "").strip()[:PROJECT_RULES_MAX]
        self._log("project_rules", {"chars": len(self.project_rules)})
        return {"chars": len(self.project_rules)}

    def reapply_project_rules(self, progress: Progress | None = None) -> dict:
        """Re-check every block against the (changed) project rules."""
        return self.retag("Re-check every block against the PROJECT RULES and change only the markup that violates them.",
                          progress=progress)

    def apply_instruction(self, text: str, progress: Progress | None = None) -> dict:
        """Natural-language refinement: plan → retag / metadata / entity operations."""
        ctx = {"genre": self.genre, "tagset": self.tagset, "summary": self.summary(), "registry": self.registry_text(80),
               "metadata_keys": list(self.metadata)}
        plan = self.llm.json(P.plan_system(self.s.ui_lang), f"State: {json.dumps(ctx, ensure_ascii=False)}\n\nUSER INSTRUCTION: {text}", max_tokens=3000)
        out = {"plan": plan, "reply": plan.get("reply", "")}
        if plan.get("metadata_patch"):
            self.update_metadata(plan["metadata_patch"])
            out["metadata_updated"] = True
        for op in plan.get("entity_ops", []) or []:
            self.edit_entity(**{k: op.get(k) for k in ("op", "kind", "id", "data", "into")})
        if plan.get("retag_instruction") or plan.get("tag_keys") or plan.get("remove_tag_keys"):
            instr = plan.get("retag_instruction") or ("Add: " + "; ".join(tag_rule(k, self.langs) for k in plan.get("tag_keys", []) if k in TAGS))
            if plan.get("remove_tag_keys"):
                instr += " Remove markup of these kinds (unwrap, keep text): " + ", ".join(
                    e for k in plan["remove_tag_keys"] if k in TAGS for e in TAGS[k]["elements"])
            scope = plan.get("scope", "all")
            out["retag"] = self.retag(instr, add_keys=[k for k in plan.get("tag_keys", []) if k in TAGS],
                                      remove_keys=[k for k in plan.get("remove_tag_keys", []) if k in TAGS],
                                      block_ids=plan.get("block_ids") if scope == "blocks" else None,
                                      search=plan.get("search") if scope == "search" else None, progress=progress)
        self._log("instruction", {"text": text, "kind": plan.get("kind")})
        return out

    def answer_question(self, qid: str, answer: str, progress: Progress | None = None) -> dict:
        q = next((q for q in self.questions if q["id"] == qid), None)
        if not q:
            return {"error": f"unknown question {qid}"}
        q["answered"] = True
        q["answer"] = answer
        about = f" (concerning: {q.get('about')})" if q.get("about") else ""
        blk = f" Only block {q['block']} is affected." if q.get("block") is not None else ""
        return self.apply_instruction(f"Question asked to me: {q['question']}{about}. My answer: {answer}.{blk}", progress)

    def update_metadata(self, patch: dict) -> dict:
        self._snapshot("before metadata update")
        if "persons" in patch or "places" in patch or "orgs" in patch:
            for kind in ("persons", "places", "orgs"):
                for e in patch.pop(kind, []) or []:
                    self.edit_entity("update" if any(x["id"] == e.get("id") for x in self.registry[kind]) else "add",
                                     kind.rstrip("s"), e.get("id"), e)
        self.metadata = deep_merge(self.metadata, patch)
        self._log("metadata", list(patch))
        return self.metadata

    def edit_entity(self, op: str, kind: str, id: str | None = None, data: dict | None = None, into: str | None = None) -> dict:
        kind = {"person": "persons", "place": "places", "org": "orgs"}.get(kind, kind)
        lst = self.registry.setdefault(kind, [])
        data = data or {}
        if op == "add":
            eid = id or data.get("id")
            if eid and eid not in self.all_ids():
                lst.append({"id": eid, **{k: v for k, v in data.items() if k != "id"}})
        elif op == "update":
            for e in lst:
                if e["id"] == id:
                    e.update({k: v for k, v in data.items() if k != "id"})
        elif op == "delete":
            self.registry[kind] = [e for e in lst if e["id"] != id]
        elif op == "merge" and id and into:
            self.registry[kind] = [e for e in lst if e["id"] != id]
            for b in self.blocks:
                b["xml"] = re.sub(rf'#({re.escape(id)})(?=["\s])', f"#{into}", b["xml"])
        self._log("entity", {"op": op, "kind": kind, "id": id})
        return {"registry": {k: len(v) for k, v in self.registry.items()}}

    # ------------------------------------------------------------------ 6. assembly & validation
    def _registry_to_metadata(self) -> dict:
        def person(e):
            d = {"id": e["id"], "names": [{"text": e.get("name"), "lang": self.langs[0] if self.langs else None}]}
            for v in e.get("variants", [])[:6]:
                if v and v != e.get("name") and len(v) < 40:
                    d["names"].append({"text": v, "type": "variant"})
            if e.get("sex") in ("M", "F", "U"):
                d["sex"] = e["sex"]
            if e.get("role"):
                d["role"] = e["role"]
            if e.get("wikidata"):
                d["idnos"] = [{"type": "wikidata", "value": e["wikidata"]}]
            d.update({k: e[k] for k in ("note", "birth", "death", "occupation", "gender", "age", "idnos") if e.get(k)})
            return d

        def simple(e):
            d = {"id": e["id"], "names": [{"text": e.get("name")}], "type": e.get("type")}
            if e.get("wikidata"):
                d["idnos"] = [{"type": "wikidata", "value": e["wikidata"]}]
            d.update({k: e[k] for k in ("note", "geo", "idnos") if e.get(k)})
            return d

        used = refs_in([b["xml"] for b in self.blocks])
        keep = lambda e: e["id"] in used or e.get("keep")
        return {"persons": [person(e) for e in self.registry.get("persons", []) if keep(e)],
                "places": [simple(e) for e in self.registry.get("places", []) if keep(e)],
                "orgs": [simple(e) for e in self.registry.get("orgs", []) if keep(e)]}

    def body_lines(self) -> tuple[list[str], dict[int, int]]:
        """Serialise body; returns (lines, block_index -> line offset within body lines)."""
        lines = ["<body>"]
        start = {}
        stack: list[int] = []
        ind = lambda: "  " * (len(stack) + 1)
        last: dict = {}
        for b in self.blocks:
            d = b.get("div")
            xml = b["xml"].strip()
            if not d and xml.startswith("<head") and xml.endswith("</head>") and xml.count("<head") == 1:
                # a heading the model did not mark as a division start: open a sibling division (deterministic)
                n = re.sub(r"<[^>]+>", "", xml).strip()
                d = {"type": last.get("type") or "section", "level": last.get("level") or 1,
                     "n": n if re.fullmatch(r"\d{1,4}", n) else None}
            if d:
                last = d
            if d:
                lvl = int(d.get("level") or 1)
                while stack and stack[-1] >= lvl:
                    stack.pop()
                    lines.append(ind() + "</div>")
                attrs = f' type="{d.get("type")}"' + (f' n="{d["n"]}"' if d.get("n") not in (None, "") else "")
                lines.append(ind() + f"<div{attrs}>")
                stack.append(lvl)
            start[b["i"]] = len(lines)
            for l in xml.split("\n"):
                lines.append(ind() + l)
        while stack:
            stack.pop()
            lines.append(ind() + "</div>")
        lines.append("</body>")
        return lines, start

    def normalize_structure(self) -> int:
        """Deterministic structure fixes: a block that is only a bare number in a text without page numbers
        is a chapter/section number -> <head>. Returns the number of blocks changed."""
        if self.page_numbers():
            return 0
        changed = 0
        for b in self.blocks:
            raw = (b.get("raw") or "").strip()
            if re.fullmatch(r"\d{1,4}", raw) and not b["xml"].strip().startswith("<head"):
                b["xml"] = f"<head>{raw}</head>"
                if not b.get("div"):
                    prev = next((x.get("div") for x in reversed(self.blocks[:b["i"]]) if x.get("div")), None) or {}
                    b["div"] = {"type": prev.get("type") or "chapter", "n": raw, "level": prev.get("level") or 1}
                changed += 1
        return changed

    def to_xml(self) -> tuple[str, dict[int, int]]:
        self.normalize_structure()
        md = deep_merge(self.metadata, self._registry_to_metadata())
        if self.project_rules.strip() and not (md.get("editorial") or {}).get("interpretation"):
            md = deep_merge(md, {"editorial": {"interpretation": "Project encoding rules supplied by the encoders were added to "
                                               "every model instruction: " + " | ".join(l.strip(" -*#\t") for l in re.sub(r"<!--.*?-->", "", self.project_rules, flags=re.S).splitlines() if l.strip())[:3000]}})
        body, start = self.body_lines()
        counts = element_counts([b["xml"] for b in self.blocks])
        for k in ("body", "text"):
            counts[k] = 1
        chars = len(re.sub(r"\s", "", self.raw_text))
        words = len(self.raw_text.split())
        if self.header_override:
            header_s = self.header_override
            standoff_s = self.standoff_override or ""
        else:
            header, standoff = build_header(md, tag_counts=counts, genre=self.genre,
                                            registry_location=GENRES[self.genre]["registry_location"], model=self.s.model,
                                            stats={"chars": chars, "words": words})
            etree.indent(header, space="  ")
            header_s = strip_ns(to_string(header))
            standoff_s = ""
            if standoff is not None:
                etree.indent(standoff, space="  ")
                standoff_s = strip_ns(to_string(standoff))
        main_lang = (self.langs or ["und"])[0]
        head = ['<?xml version="1.0" encoding="UTF-8"?>',
                f'<?xml-model href="https://www.tei-c.org/Vault/P5/{TEI_VERSION}/xml/tei/custom/schema/relaxng/tei_all.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>',
                f'<TEI xmlns="{TEI_NS}" xml:lang="{main_lang}">']
        head += ["  " + l for l in header_s.strip().split("\n")]
        if standoff_s:
            head += ["  " + l for l in standoff_s.strip().split("\n")]
        head.append("  <text>")
        offset = len(head)
        lines = head + ["    " + l for l in body] + ["  </text>", "</TEI>"]
        line_of_block = {i: offset + s + 1 for i, s in start.items()}  # 1-based line numbers
        return "\n".join(lines) + "\n", line_of_block

    def validate(self) -> dict:
        xml, line_of_block = self.to_xml()
        res = validate_document(xml)
        block_starts = sorted((ln, i) for i, ln in line_of_block.items())
        for e in res.get("errors", []):
            e["block"] = None
            for ln, i in block_starts:
                if ln <= (e.get("line") or 0):
                    e["block"] = i
                else:
                    break
            if e["block"] is not None and block_starts and e["line"] < block_starts[0][0]:
                e["block"] = None
        used = refs_in([b["xml"] for b in self.blocks])
        dangling = sorted(used - self.all_ids())
        res["dangling_refs"] = dangling
        res["fallback_blocks"] = [b["i"] for b in self.blocks if b["status"] == "fallback"]
        self.validation = res
        return res

    def repair(self, progress: Progress | None = None) -> dict:
        v = self.validate()
        by_block: dict[int, list[str]] = {}
        for e in v.get("errors", []):
            if e.get("block") is not None:
                by_block.setdefault(e["block"], []).append(e["message"])
        if not by_block:
            return {"repaired": 0, "valid": v["valid"], "remaining": v.get("errors", [])}
        msgs = "; ".join(f"block {i}: {' | '.join(m[:3])}" for i, m in list(by_block.items())[:40])
        r = self.retag(f"Fix these TEI {TEI_VERSION} schema validation errors without changing correct markup: {msgs}",
                       block_ids=list(by_block), progress=progress)
        v2 = self.validate()
        return {"repaired": r["changed"], "valid": v2["valid"], "remaining": v2.get("errors", [])[:30]}

    # ------------------------------------------------------------------ import existing TEI
    @classmethod
    def from_tei(cls, xml_text: str, settings: Settings | None = None, llm: LLM | None = None) -> "Session":
        root = etree.fromstring(xml_text.encode("utf-8"), etree.XMLParser(remove_blank_text=False, huge_tree=True))
        ns = {"t": TEI_NS}
        s = cls("", settings, llm)
        hdr = root.find("t:teiHeader", ns)
        if hdr is not None:
            s.header_override = strip_ns(etree.tostring(hdr, encoding="unicode", with_tail=False))
        so = root.find("t:standOff", ns)
        if so is not None:
            s.standoff_override = strip_ns(etree.tostring(so, encoding="unicode", with_tail=False))
        for kind, tag, name_tag in (("persons", "person", "persName"), ("places", "place", "placeName"), ("orgs", "org", "orgName")):
            for el in root.iter(f"{{{TEI_NS}}}{tag}"):
                xid = el.get("{http://www.w3.org/XML/1998/namespace}id")
                if xid:
                    n = el.find(f"t:{name_tag}", ns)
                    s.registry[kind].append({"id": xid, "name": "".join(n.itertext()).strip() if n is not None else xid, "variants": [], "keep": True})
        known = {e["id"] for k in s.registry.values() for e in k}
        for part in (hdr, so):
            if part is not None:
                s.extra_ids += [x.get("{http://www.w3.org/XML/1998/namespace}id") for x in part.iter()
                                if isinstance(x.tag, str) and x.get("{http://www.w3.org/XML/1998/namespace}id")
                                and x.get("{http://www.w3.org/XML/1998/namespace}id") not in known]
        lang = root.get("{http://www.w3.org/XML/1998/namespace}lang")
        s.langs = [l.get("ident") for l in root.iter(f"{{{TEI_NS}}}language") if l.get("ident")] or ([lang] if lang else ["und"])
        body = root.find(".//t:text/t:body", ns)
        blocks = []

        def walk(el, level, pending_div):
            for ch in el:
                if not isinstance(ch.tag, str):
                    continue
                if local(ch.tag) == "div":
                    walk(ch, level + 1, {"type": ch.get("type") or "section", "n": ch.get("n"), "level": level + 1})
                    pending_div = None
                    continue
                xml = strip_ns(etree.tostring(ch, encoding="unicode", with_tail=False))
                blocks.append({"i": len(blocks), "raw": re.sub(r"\s+", " ", source_text(ch)).strip(), "xml": xml,
                               "div": pending_div, "status": "imported", "warnings": []})
                pending_div = None

        if body is not None:
            walk(body, 0, None)
        s.blocks = blocks
        s.raw_text = "\n\n".join(b["raw"] for b in blocks)
        a = guess(s.raw_text)
        s.genre = "prose_fiction" if root.find(".//t:particDesc", ns) is not None and root.find(".//t:said", ns) is not None else a["genre"]
        s.analysis = {**a, "imported": True}
        s.tagset = list(GENRES[s.genre]["core"])
        s.status = "tagged"
        s._log("import_tei", {"blocks": len(blocks)})
        return s
