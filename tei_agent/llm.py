"""Thin DeepSeek client (OpenAI-compatible) with JSON helpers, usage accounting and a mock for tests."""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Callable

from .config import Settings


class LLMError(RuntimeError):
    pass


def parse_json_loose(text: str) -> Any:
    """Parse JSON even if wrapped in ``` fences or surrounded by prose."""
    if text is None:
        raise LLMError("empty response")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise LLMError(f"no JSON found in response: {t[:200]}")
    for end in range(len(t), start, -1):
        if t[end - 1] in "}]":
            try:
                return json.loads(t[start:end])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"could not parse JSON: {t[:200]}")


class Usage:
    def __init__(self):
        self.lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_tokens = 0
        self.calls = 0

    def add(self, usage) -> None:
        if usage is None:
            return
        with self.lock:
            self.calls += 1
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
            self.cached_tokens += getattr(usage, "prompt_cache_hit_tokens", 0) or 0

    def as_dict(self) -> dict:
        # Peak-hour list prices for deepseek-flash (USD per 1M tokens, 2026-10-12): hit 0.006, miss 0.30, out 1.20
        miss = max(self.prompt_tokens - self.cached_tokens, 0)
        est = (self.cached_tokens * 0.006 + miss * 0.30 + self.completion_tokens * 1.20) / 1e6
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "cached_tokens": self.cached_tokens, "est_cost_usd_peak": round(est, 4)}


class LLM:
    """Wraps chat.completions. `chat()` returns the assistant message as a plain dict
    (content, reasoning_content, tool_calls) so it can be appended back to history verbatim
    (DeepSeek requires reasoning_content to be passed back when tools are used in thinking mode)."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.usage = Usage()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.s.api_key:
                raise LLMError("DEEPSEEK_API_KEY is not set (put it in .env or the environment)")
            from openai import OpenAI
            self._client = OpenAI(api_key=self.s.api_key, base_url=self.s.base_url, timeout=600)
        return self._client

    def chat(self, messages: list[dict], *, json_mode: bool = False, tools: list | None = None,
             max_tokens: int | None = None, thinking: bool | None = None, retries: int = 3) -> dict:
        thinking = self.s.thinking if thinking is None else thinking
        kw: dict[str, Any] = {
            "model": self.s.model,
            "messages": messages,
            "max_tokens": max_tokens or self.s.max_tokens,
            "extra_body": {"thinking": {"type": "enabled" if thinking else "disabled"}},
        }
        if thinking:
            kw["reasoning_effort"] = self.s.reasoning_effort
        else:
            kw["temperature"] = self.s.temperature
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        if tools:
            kw["tools"] = tools
        client = self.client  # raises immediately if no API key
        last = None
        for attempt in range(retries):
            try:
                r = client.chat.completions.create(**kw)
                self.usage.add(getattr(r, "usage", None))
                m = r.choices[0].message
                out = {"role": "assistant", "content": m.content or ""}
                rc = getattr(m, "reasoning_content", None)
                if rc:
                    out["reasoning_content"] = rc
                if m.tool_calls:
                    out["tool_calls"] = [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in m.tool_calls]
                if json_mode and not out["content"].strip():
                    raise LLMError("empty JSON content")
                return out
            except Exception as e:  # network / rate limit / empty JSON
                status = getattr(e, "status_code", None)
                if status == 401:
                    raise LLMError("API key rejected (401).") from e
                if status == 402:
                    raise LLMError("Insufficient DeepSeek balance (402): top up at platform.deepseek.com.") from e
                last = e
                time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"DeepSeek call failed after {retries} attempts: {last}")

    def json(self, system: str, user: str, *, max_tokens: int | None = None) -> Any:
        last: Exception | None = None
        for _ in range(2):  # one fresh retry when the model returns malformed / truncated JSON
            msg = self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                            json_mode=True, max_tokens=max_tokens)
            try:
                return parse_json_loose(msg["content"])
            except LLMError as e:
                last = e
        raise last  # type: ignore[misc]


class MockLLM(LLM):
    """Offline stand-in. `responder(messages, json_mode, tools)` returns either a str (content)
    or a full message dict."""

    def __init__(self, settings: Settings, responder: Callable[..., Any]):
        super().__init__(settings)
        self.responder = responder
        self.log: list[list[dict]] = []

    def chat(self, messages, *, json_mode=False, tools=None, max_tokens=None, thinking=None, retries=3):
        self.log.append(messages)
        self.usage.calls += 1
        out = self.responder(messages, json_mode, tools)
        if isinstance(out, (dict, list)) and not (isinstance(out, dict) and out.get("role") == "assistant"):
            out = json.dumps(out, ensure_ascii=False)
        if isinstance(out, str):
            return {"role": "assistant", "content": out}
        return out
