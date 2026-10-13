"""Convert Korean (native & Sino-Korean) and Han numerals to Arabic, for TEI numeric attributes
(@quantity, @value, @atLeast, @atMost, @min, @max must be teidata.numeric)."""
from __future__ import annotations

import re

NUMERIC = re.compile(r"^-?(\d+(\.\d+)?([eE][-+]?\d+)?|\d+/\d+)$")
NUMERIC_ATTRS = {"quantity", "atLeast", "atMost", "min", "max"}

_SINO_DIGIT = {"영": 0, "공": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "륙": 6, "칠": 7, "팔": 8, "구": 9,
               "〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "壹": 1, "貳": 2, "參": 3}
_SINO_UNIT = {"십": 10, "백": 100, "천": 1000, "十": 10, "百": 100, "千": 1000, "拾": 10}
_BIG = {"만": 10_000, "억": 100_000_000, "萬": 10_000, "億": 100_000_000}
_NATIVE = {"하나": 1, "한": 1, "둘": 2, "두": 2, "셋": 3, "세": 3, "석": 3, "서": 3, "넷": 4, "네": 4, "넉": 4, "너": 4,
           "다섯": 5, "닷": 5, "여섯": 6, "엿": 6, "일곱": 7, "여덟": 8, "아홉": 9}
_NATIVE_TENS = {"열": 10, "스물": 20, "스무": 20, "서른": 30, "마흔": 40, "쉰": 50, "예순": 60, "일흔": 70, "여든": 80, "아흔": 90}


def _sino(s: str) -> int | None:
    total, section, digit = 0, 0, None
    for ch in s:
        if ch in _SINO_DIGIT:
            if digit is not None:
                return None  # two digits in a row (e.g. 팔구 = 8–9) → a range, not a number
            digit = _SINO_DIGIT[ch]
        elif ch in _SINO_UNIT:
            section += (digit if digit is not None else 1) * _SINO_UNIT[ch]
            digit = None
        elif ch in _BIG:
            section += digit or 0
            total += (section or 1) * _BIG[ch]
            section, digit = 0, None
        else:
            return None
    return total + section + (digit or 0)


def _native(s: str) -> int | None:
    val, rest = 0, s
    for w, n in sorted(_NATIVE_TENS.items(), key=lambda x: -len(x[0])):
        if rest.startswith(w):
            val, rest = n, rest[len(w):]
            break
    if rest:
        if rest in _NATIVE:
            val += _NATIVE[rest]
        else:
            return None
    return val or None


def to_arabic(value: str) -> str | None:
    v = value.strip().replace(",", "")
    if NUMERIC.match(v):
        return v
    if not v:
        return None
    n = _native(v)
    if n is None:
        n = _sino(v)
    return str(n) if n is not None else None
