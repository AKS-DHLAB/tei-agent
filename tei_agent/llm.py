"""Thin LLM client — DeepSeek, OpenAI and Gemini (OpenAI-style, via the openai SDK) and Claude (Anthropic SDK) —
with JSON helpers, usage accounting and a mock for tests."""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Callable

from .config import PROVIDERS, Settings


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
    def __init__(self, provider: str = "deepseek"):
        self.lock = threading.Lock()
        self.provider = provider
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_tokens = 0
        self.calls = 0

    def add(self, usage) -> None:
        """OpenAI-style usage (DeepSeek, OpenAI, Gemini)."""
        if usage is None:
            return
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(usage, "prompt_cache_hit_tokens", 0) or (getattr(details, "cached_tokens", 0) if details else 0) or 0
        self.add_tokens(getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0, cached)

    def add_tokens(self, prompt: int, completion: int, cached: int = 0) -> None:
        with self.lock:
            self.calls += 1
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.cached_tokens += cached

    def as_dict(self) -> dict:
        # A price estimate only for DeepSeek: peak-hour list prices for deepseek-flash
        # (USD per 1M tokens, 2026-10-12): hit 0.006, miss 0.30, out 1.20
        est = None
        if self.provider == "deepseek":
            miss = max(self.prompt_tokens - self.cached_tokens, 0)
            est = round((self.cached_tokens * 0.006 + miss * 0.30 + self.completion_tokens * 1.20) / 1e6, 4)
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "cached_tokens": self.cached_tokens, "est_cost_usd_peak": est, "provider": self.provider}


def to_anthropic_tools(tools: list[dict]) -> list[dict]:
    return [{"name": t["function"]["name"], "description": t["function"].get("description", ""),
             "input_schema": t["function"].get("parameters") or {"type": "object", "properties": {}}} for t in tools]


def to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """OpenAI-style history -> (system, Messages API messages). Claude's own assistant blocks (thinking included)
    are replayed unchanged from `anthropic_content`; tool results become tool_result blocks in a user turn."""
    system: list[str] = []
    out: list[dict] = []

    def push(role: str, blocks: list[dict]) -> None:
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": list(blocks)})

    for m in messages:
        role = m.get("role")
        if role == "system":
            system.append(m.get("content") or "")
        elif role == "tool":
            push("user", [{"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": str(m.get("content") or "")}])
        elif role == "assistant":
            if m.get("anthropic_content"):
                push("assistant", json.loads(json.dumps(m["anthropic_content"])))
                continue
            blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
            for tc in m.get("tool_calls") or []:
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"], "input": args})
            if blocks:
                push("assistant", blocks)
        else:
            push("user", [{"type": "text", "text": str(m.get("content") or "")}])
    return "\n\n".join(system), out


def _plain(m: dict) -> dict:
    """Fields every OpenAI-style endpoint accepts (history may hold DeepSeek or Claude extras)."""
    o = {"role": m["role"], "content": m.get("content") or ""}
    for k in ("tool_calls", "tool_call_id"):
        if m.get(k):
            o[k] = m[k]
    return o


_FALLBACK_MODELS = re.compile(r"^claude-(opus-5|sonnet-5-5|fable-5)")


class LLM:
    """Wraps the chosen provider. `chat()` returns the assistant message as a plain OpenAI-style dict
    (content, tool_calls, plus reasoning_content for DeepSeek or anthropic_content for Claude) so it can be appended
    back to history verbatim: both providers need those extras sent back when tools are used."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.usage = Usage(getattr(settings, "provider", "deepseek"))
        self._client = None

    @property
    def provider(self) -> str:
        return getattr(self.s, "provider", "deepseek") or "deepseek"

    @property
    def label(self) -> str:
        return PROVIDERS.get(self.provider, PROVIDERS["deepseek"])["label"]

    @property
    def client(self):
        if self._client is None:
            if not self.s.api_key:
                env = PROVIDERS.get(self.provider, PROVIDERS["deepseek"])["key_env"]
                raise LLMError(f"{env} is not set (put it in .env or the environment)")
            if self.provider == "anthropic":
                try:
                    import anthropic
                except ImportError as e:
                    raise LLMError("Claude needs the Anthropic SDK: pip install anthropic") from e
                kw = {"api_key": self.s.api_key, "timeout": 600}
                if self.s.base_url:
                    kw["base_url"] = self.s.base_url
                self._client = anthropic.Anthropic(**kw)
            else:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.s.api_key, base_url=self.s.base_url, timeout=600)
        return self._client

    def chat(self, messages: list[dict], *, json_mode: bool = False, tools: list | None = None,
             max_tokens: int | None = None, thinking: bool | None = None, retries: int = 3) -> dict:
        if self.provider == "anthropic":
            return self._chat_anthropic(messages, json_mode=json_mode, tools=tools, max_tokens=max_tokens, retries=retries)
        kw: dict[str, Any] = {"model": self.s.model}
        mt = max_tokens or self.s.max_tokens
        if self.provider == "deepseek":
            thinking = self.s.thinking if thinking is None else thinking
            kw.update(messages=messages, max_tokens=mt, extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}})
            if thinking:
                kw["reasoning_effort"] = self.s.reasoning_effort
            else:
                kw["temperature"] = self.s.temperature
        elif self.provider == "openai":
            # current OpenAI models take max_completion_tokens and only their default temperature
            kw.update(messages=[_plain(m) for m in messages], max_completion_tokens=mt)
        else:  # gemini (OpenAI-compatible endpoint)
            kw.update(messages=[_plain(m) for m in messages], max_tokens=mt, temperature=self.s.temperature)
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        if tools:
            kw["tools"] = tools
        client = self.client  # raises immediately if no API key
        last = None
        relaxed = 0
        attempt = 0
        while attempt < retries:
            try:
                r = client.chat.completions.create(**kw)
                self.usage.add(getattr(r, "usage", None))
                m = r.choices[0].message
                out = {"role": "assistant", "content": m.content or ""}
                rc = getattr(m, "reasoning_content", None)
                if rc and self.provider == "deepseek":
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
                if status in (401, 403):
                    raise LLMError(f"{self.label}: API key rejected ({status}).") from e
                if status == 402:
                    raise LLMError(f"{self.label}: insufficient balance (402).") from e
                if status == 400:
                    # a model that rejects one optional parameter: drop it and retry at once
                    msg = str(e).lower()
                    for k in ("temperature", "response_format", "reasoning_effort"):
                        if k in kw and k in msg and relaxed < 4:
                            kw.pop(k)
                            relaxed += 1
                            break
                    else:
                        raise LLMError(f"{self.label} request error (400): {e}") from e
                    continue
                if status == 404:
                    raise LLMError(f"{self.label}: model or endpoint not found (404): {e}") from e
                last = e
                attempt += 1
                time.sleep(1.5 * attempt)
        raise LLMError(f"{self.label} call failed after {retries} attempts: {last}")

    def _chat_anthropic(self, messages: list[dict], *, json_mode: bool, tools: list | None,
                        max_tokens: int | None, retries: int) -> dict:
        import anthropic

        system, msgs = to_anthropic_messages(messages)
        if json_mode:  # no response_format on the Messages API: ask for JSON (parse_json_loose strips fences)
            system += "\n\nReply with one JSON object only, no other text."
        kw: dict[str, Any] = {"model": self.s.model, "max_tokens": min(max_tokens or self.s.max_tokens, 32000),
                              "messages": msgs}
        if system.strip():
            kw["system"] = system
        if tools:
            kw["tools"] = to_anthropic_tools(tools)
        client = self.client
        last = None
        for attempt in range(retries):
            try:
                if _FALLBACK_MODELS.match(self.s.model):
                    # on a policy decline the API re-runs the request on a fallback model, inside the same call
                    r = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
                else:
                    r = client.messages.create(**kw)
                u = r.usage
                cached = getattr(u, "cache_read_input_tokens", 0) or 0
                prompt = (u.input_tokens or 0) + cached + (getattr(u, "cache_creation_input_tokens", 0) or 0)
                self.usage.add_tokens(prompt, u.output_tokens or 0, cached)
                if r.stop_reason == "refusal":
                    cat = getattr(getattr(r, "stop_details", None), "category", None)
                    raise LLMError(f"{self.label} declined this request" + (f" ({cat})" if cat else "") + ".")
                blocks = [b.model_dump(mode="json", exclude_none=True) for b in r.content]
                out: dict[str, Any] = {"role": "assistant", "anthropic_content": blocks,
                                       "content": "".join(b.get("text", "") for b in blocks if b.get("type") == "text")}
                calls = [b for b in blocks if b.get("type") == "tool_use"]
                if calls:
                    out["tool_calls"] = [{"id": b["id"], "type": "function",
                                          "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False)}}
                                         for b in calls]
                if json_mode and not out["content"].strip():
                    raise LLMError("empty JSON content")
                return out
            except LLMError:
                raise
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
                raise LLMError(f"{self.label}: API key rejected ({e.status_code}).") from e
            except (anthropic.BadRequestError, anthropic.NotFoundError) as e:
                raise LLMError(f"{self.label} request error ({e.status_code}): {e.message}") from e
            except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as e:
                last = e
                time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"{self.label} call failed after {retries} attempts: {last}")

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
