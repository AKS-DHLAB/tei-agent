"""Local web app: FastAPI JSON API + single-page UI (tei_agent/web/index.html).

Run:  tei-agent serve   (http://127.0.0.1:8765)
"""
from __future__ import annotations

import threading
import traceback
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from . import tools
from .authority import lookup
from .config import APP_VERSION, TEI_VERSION, Settings
from .llm import LLM
from .pipeline import Session
from .profiles import GENRES, METADATA_FIELDS, TAGS
from .schema import rng

WEB = Path(__file__).resolve().parent / "web"


class Store:
    def __init__(self, settings: Settings, llm_factory: Callable[[], LLM] | None = None):
        self.s = settings
        self.llm_factory = llm_factory or (lambda: LLM(self.s))
        self.sessions: dict[str, Session] = {}
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()

    def get(self, sid: str) -> Session:
        if sid not in self.sessions:
            p = self.s.sessions_dir / f"{sid}.json"
            if not p.exists():
                raise HTTPException(404, "session not found")
            self.sessions[sid] = Session.load(p, self.s, self.llm_factory())
        return self.sessions[sid]

    def add(self, s: Session) -> Session:
        self.sessions[s.id] = s
        s.save(self.s.sessions_dir)
        return s

    def run(self, sid: str, label: str, fn: Callable[[Session, Callable], Any]) -> dict:
        s = self.get(sid)
        with self.lock:
            j = self.jobs.get(sid)
            if j and j["running"]:
                raise HTTPException(409, f"job already running: {j['label']}")
            job = {"label": label, "running": True, "message": "started", "progress": 0.0, "result": None, "error": None}
            self.jobs[sid] = job

        def progress(msg, frac):
            job["message"], job["progress"] = msg, frac

        def target():
            try:
                job["result"] = fn(s, progress)
            except Exception as e:
                job["error"] = f"{type(e).__name__}: {e}"
                traceback.print_exc()
            finally:
                job["running"] = False
                job["progress"] = 1.0
                s.save(self.s.sessions_dir)

        threading.Thread(target=target, daemon=True).start()
        return {"job": label, "running": True}


class NewSession(BaseModel):
    text: str
    genre: str | None = None
    lang: str | None = None
    title: str | None = None
    author: str | None = None
    auto_tag: bool = True


class ImportTEI(BaseModel):
    xml: str


class Keys(BaseModel):
    keys: list[str]
    guidance: str = ""


class Text(BaseModel):
    text: str


class Answer(BaseModel):
    qid: str
    answer: str


class Patch(BaseModel):
    patch: dict


class Entity(BaseModel):
    op: str
    kind: str
    id: str | None = None
    data: dict | None = None
    into: str | None = None


class Genre(BaseModel):
    genre: str


def create_app(settings: Settings | None = None, llm_factory: Callable[[], LLM] | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings, llm_factory)
    app = FastAPI(title="TEI Agent", version=APP_VERSION)
    threading.Thread(target=rng, daemon=True).start()  # warm the 1 MB tei_all grammar (≈10 s)

    def public_state(s: Session) -> dict:
        d = s.state()
        d["chat"] = [m for m in d["chat"] if m["role"] in ("user", "assistant") and m.get("content")]
        d["summary"] = s.summary()
        d["job"] = store.jobs.get(s.id)
        return d

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    @app.get("/api/config")
    def config():
        return {"version": APP_VERSION, "tei_version": TEI_VERSION, "model": settings.model, "has_key": bool(settings.api_key),
                "thinking": settings.thinking, "ui_lang": settings.ui_lang,
                "genres": {k: {"ko": v["ko"], "en": v["en"]} for k, v in GENRES.items()},
                "tags": {k: {"ko": v["ko"], "elements": v["elements"], "cat": v["cat"], "rule": v["rule"]} for k, v in TAGS.items()},
                "metadata_fields": METADATA_FIELDS}

    @app.get("/api/sessions")
    def list_sessions():
        out = []
        settings.sessions_dir.mkdir(parents=True, exist_ok=True)
        import json
        for p in sorted(settings.sessions_dir.glob("*.json"), key=lambda p: -p.stat().st_mtime)[:50]:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                t = (d.get("metadata", {}).get("titles") or [{}])[0].get("text") or d.get("raw_text", "")[:30]
                out.append({"id": d["id"], "title": t, "created": d.get("created"), "genre": d.get("genre"), "status": d.get("status")})
            except Exception:
                continue
        return out

    @app.post("/api/sessions")
    def new_session(req: NewSession):
        if not req.text.strip():
            raise HTTPException(400, "empty text")
        s = store.add(Session(req.text, settings, store.llm_factory()))
        hints = {"genre": req.genre, "lang": req.lang}

        def work(s: Session, progress):
            progress("텍스트 분석 중", 0.05)
            s.analyze(hints)
            if req.title:
                s.metadata["titles"] = [{"text": req.title, "type": "main", "lang": s.langs[0] if s.langs else None}]
            if req.author:
                s.metadata["authors"] = [{"name": req.author}]
            if req.auto_tag:
                progress("인물·장소 레지스트리 구축 중", 0.1)
                s.build_registry()
                progress("자동 태깅 중", 0.15)
                s.tag_all(progress)
                progress("추천 생성 중", 0.95)
                s.recommend_tags()
            return s.summary()

        store.run(s.id, "analyze+tag", work)
        return {"id": s.id}

    @app.post("/api/sessions/import")
    def import_tei(req: ImportTEI):
        try:
            s = Session.from_tei(req.xml, settings, store.llm_factory())
        except Exception as e:
            raise HTTPException(400, f"could not parse TEI: {e}")
        store.add(s)
        return {"id": s.id}

    @app.get("/api/sessions/{sid}")
    def get_session(sid: str):
        return public_state(store.get(sid))

    @app.get("/api/sessions/{sid}/xml", response_class=PlainTextResponse)
    def get_xml(sid: str):
        return store.get(sid).to_xml()[0]

    @app.get("/api/sessions/{sid}/job")
    def job(sid: str):
        return store.jobs.get(sid) or {"running": False}

    @app.post("/api/sessions/{sid}/tag")
    def tag(sid: str):
        def work(s, progress):
            if not any(s.registry.values()):
                s.build_registry()
            return s.tag_all(progress)
        return store.run(sid, "tag", work)

    @app.post("/api/sessions/{sid}/recommend/tags")
    def rec_tags(sid: str):
        return store.run(sid, "recommend_tags", lambda s, p: s.recommend_tags())

    @app.post("/api/sessions/{sid}/recommend/metadata")
    def rec_meta(sid: str):
        return store.run(sid, "recommend_metadata", lambda s, p: s.recommend_metadata())

    @app.post("/api/sessions/{sid}/accept")
    def accept(sid: str, req: Keys):
        return store.run(sid, "accept_tags", lambda s, p: s.accept_tags(req.keys, req.guidance, p))

    @app.post("/api/sessions/{sid}/instruct")
    def instruct(sid: str, req: Text):
        return store.run(sid, "instruction", lambda s, p: s.apply_instruction(req.text, p))

    @app.post("/api/sessions/{sid}/answer")
    def answer(sid: str, req: Answer):
        return store.run(sid, "answer", lambda s, p: s.answer_question(req.qid, req.answer, p))

    @app.post("/api/sessions/{sid}/chat")
    def chat(sid: str, req: Text):
        return store.run(sid, "chat", lambda s, p: tools.chat(s, req.text, p))

    @app.post("/api/sessions/{sid}/validate")
    def validate(sid: str):
        return store.run(sid, "validate", lambda s, p: s.validate())

    @app.post("/api/sessions/{sid}/repair")
    def repair(sid: str):
        return store.run(sid, "repair", lambda s, p: s.repair(p))

    @app.post("/api/sessions/{sid}/metadata")
    def metadata(sid: str, req: Patch):
        s = store.get(sid)
        s.update_metadata(req.patch)
        s.save(settings.sessions_dir)
        return public_state(s)

    @app.post("/api/sessions/{sid}/entity")
    def entity(sid: str, req: Entity):
        s = store.get(sid)
        s.edit_entity(req.op, req.kind, req.id, req.data, req.into)
        s.save(settings.sessions_dir)
        return public_state(s)

    @app.post("/api/sessions/{sid}/genre")
    def genre(sid: str, req: Genre):
        s = store.get(sid)
        if req.genre not in GENRES:
            raise HTTPException(400, "unknown genre")
        tools.dispatch(s, "set_genre", {"genre": req.genre})
        s.save(settings.sessions_dir)
        return public_state(s)

    @app.post("/api/sessions/{sid}/undo")
    def undo(sid: str):
        s = store.get(sid)
        label = s.undo()
        s.save(settings.sessions_dir)
        return {"undone": label}

    @app.get("/api/lookup")
    def do_lookup(name: str, lang: str = "en", kind: str = ""):
        return lookup(name, lang, kind)

    @app.get("/api/tools")
    def tool_schemas():
        return tools.TOOLS

    return app
