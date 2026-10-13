"""Runtime settings. Values come from environment variables or a `.env` file in the working dir.

DeepSeek facts (checked 2026-10-12 at api-docs.deepseek.com):
  - model string for DeepSeek-V4.1-Flash: `deepseek-flash`
  - OpenAI-compatible base URL: https://api.deepseek.com
  - thinking mode is ON by default; toggle with extra_body={"thinking": {"type": "enabled"|"disabled"}}
  - JSON output: response_format={"type": "json_object"} (prompt must mention "json")
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
TEI_VERSION = "4.12.0"
TEI_NS = "http://www.tei-c.org/ns/1.0"
APP_NAME = "TEI-Agent"
APP_VERSION = "0.1.0"


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _bool(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    # Thinking off by default: tagging is schema-driven and benefits more from speed/cost than CoT.
    thinking: bool = False
    reasoning_effort: str = "high"  # low | high | max (only used when thinking=True)
    temperature: float = 0.1  # ignored by the API in thinking mode
    chunk_chars: int = 2500  # raw characters per tagging request
    max_workers: int = 4  # concurrent chunk requests
    max_tokens: int = 32000
    ui_lang: str = "ko"  # language for explanations/questions shown to the user
    sessions_dir: Path = field(default_factory=lambda: Path("sessions"))

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        s = cls()
        s.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        s.base_url = os.environ.get("DEEPSEEK_BASE_URL", s.base_url)
        s.model = os.environ.get("TEI_AGENT_MODEL", s.model)
        s.thinking = _bool(os.environ.get("TEI_AGENT_THINKING"), s.thinking)
        s.reasoning_effort = os.environ.get("TEI_AGENT_REASONING_EFFORT", s.reasoning_effort)
        s.chunk_chars = int(os.environ.get("TEI_AGENT_CHUNK_CHARS", s.chunk_chars))
        s.max_workers = int(os.environ.get("TEI_AGENT_MAX_WORKERS", s.max_workers))
        s.ui_lang = os.environ.get("TEI_AGENT_UI_LANG", s.ui_lang)
        s.sessions_dir = Path(os.environ.get("TEI_AGENT_SESSIONS_DIR", "sessions"))
        return s
