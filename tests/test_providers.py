"""0.1.4: one client for DeepSeek, OpenAI (ChatGPT), Anthropic (Claude) and Google (Gemini).
No network: the provider SDK clients are replaced by fakes that answer through the mock responder of test_pipeline."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from test_pipeline import KO_TEXT, responder_factory
from tei_agent import tools
from tei_agent.config import PROVIDERS, Settings
from tei_agent.llm import LLM, to_anthropic_messages
from tei_agent.pipeline import Session


def test_settings_pick_key_model_and_url_per_provider(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env here
    for k in ("TEI_AGENT_MODEL", "TEI_AGENT_BASE_URL", "DEEPSEEK_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-d")
    monkeypatch.setenv("TEI_AGENT_PROVIDER", "anthropic")
    s = Settings.from_env()
    assert (s.provider, s.api_key, s.model) == ("anthropic", "sk-ant-x", PROVIDERS["anthropic"]["model"])
    monkeypatch.setenv("TEI_AGENT_PROVIDER", "gemini")
    s = Settings.from_env()
    assert s.api_key == "" and s.base_url.startswith("https://generativelanguage.googleapis.com")
    monkeypatch.setenv("TEI_AGENT_PROVIDER", "nope")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_openai_style_history_becomes_messages_api_turns():
    hist = [{"role": "system", "content": "S"}, {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "reasoning_content": "x",
             "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "a", "arguments": '{"k": 1}'}},
                            {"id": "t2", "type": "function", "function": {"name": "b", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "t1", "content": "r1"}, {"role": "tool", "tool_call_id": "t2", "content": "r2"},
            {"role": "assistant", "content": "ok", "anthropic_content": [{"type": "thinking", "thinking": "", "signature": "sig"},
                                                                         {"type": "text", "text": "ok"}]}]
    system, msgs = to_anthropic_messages(hist)
    assert system == "S"
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[1]["content"][0] == {"type": "tool_use", "id": "t1", "name": "a", "input": {"k": 1}}
    assert [b["tool_use_id"] for b in msgs[2]["content"]] == ["t1", "t2"]  # all results of one turn in one user message
    assert msgs[3]["content"][0]["signature"] == "sig"  # Claude's own blocks are replayed unchanged


class _FakeAnthropicMessages:
    """Answers Messages API calls with the test_pipeline responder (which speaks OpenAI-style messages)."""

    def __init__(self, responder, log):
        self.responder, self.log = responder, log

    def create(self, **kw):
        self.log.append(kw)
        msgs = [{"role": "system", "content": kw.get("system", "")}]
        for m in kw["messages"]:
            blocks = m["content"]
            if any(b.get("type") == "tool_result" for b in blocks):
                msgs.append({"role": "tool", "content": blocks[-1]["content"]})
            else:
                msgs.append({"role": m["role"], "content": "".join(b.get("text", "") for b in blocks)})
        out = self.responder(msgs, "JSON object only" in kw.get("system", ""), kw.get("tools"))
        if isinstance(out, (dict, list)) and not (isinstance(out, dict) and out.get("role") == "assistant"):
            out = {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)}
        if isinstance(out, str):
            out = {"role": "assistant", "content": out}
        content = [{"type": "thinking", "thinking": "", "signature": "sig"}]
        if out.get("content"):
            content.append({"type": "text", "text": out["content"]})
        for tc in out.get("tool_calls") or []:
            content.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"])})
        blocks = [SimpleNamespace(**b, model_dump=(lambda b=b, **_: dict(b))) for b in content]
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=2, cache_creation_input_tokens=0)
        return SimpleNamespace(content=blocks, usage=usage, stop_reason="tool_use" if out.get("tool_calls") else "end_turn")


def test_claude_adapter_tags_and_runs_the_tool_loop(tmp_path):
    pytest.importorskip("anthropic")
    s = Settings(provider="anthropic", api_key="sk-ant-test", model="claude-opus-5-5", sessions_dir=tmp_path,
                 max_workers=2, chunk_chars=300)
    responder, _ = responder_factory()
    log: list[dict] = []
    llm = LLM(s)
    fake = _FakeAnthropicMessages(responder, log)
    llm._client = SimpleNamespace(messages=fake, beta=SimpleNamespace(messages=fake))
    ses = Session(KO_TEXT, s, llm)
    ses.analyze()
    ses.build_registry()
    ses.tag_all()
    assert ses.summary()["tag_counts"].get("persName", 0) >= 2
    first = log[0]
    assert "response_format" not in first and "temperature" not in first
    assert first["system"].rstrip().endswith("Reply with one JSON object only, no other text.")
    assert first["fallbacks"] == "default" and first["betas"] == ["server-side-fallback-2026-07-01"]
    out = tools.chat(ses, "지금 상태 알려줘")
    assert out["actions"][0]["tool"] == "get_status" and "산문" in out["reply"]
    last = log[-1]["messages"]
    assert last[-1]["content"][0]["type"] == "tool_result"
    assert last[-2]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig"}  # replayed unchanged
    assert llm.usage.as_dict()["est_cost_usd_peak"] is None and llm.usage.cached_tokens > 0


class _BadRequest(Exception):
    status_code = 400


def test_openai_drops_a_rejected_parameter_and_retries():
    s = Settings(provider="openai", api_key="sk-test", model="gpt-5-mini")
    llm = LLM(s)
    seen: list[dict] = []

    def create(**kw):
        seen.append(dict(kw))
        if "response_format" in kw:
            raise _BadRequest("Unsupported parameter: 'response_format'")
        msg = SimpleNamespace(content='{"ok": true}', tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                               usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, prompt_tokens_details=SimpleNamespace(cached_tokens=1)))

    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    hist = [{"role": "system", "content": "json"}, {"role": "assistant", "content": "x", "reasoning_content": "r"},
            {"role": "user", "content": "ping"}]
    assert llm.chat(hist, json_mode=True)["content"] == '{"ok": true}'
    assert len(seen) == 2 and "response_format" not in seen[1]
    assert "max_completion_tokens" in seen[0] and "temperature" not in seen[0] and "extra_body" not in seen[0]
    assert all("reasoning_content" not in m for m in seen[0]["messages"])  # DeepSeek extras are not sent elsewhere
    assert llm.usage.cached_tokens == 1
