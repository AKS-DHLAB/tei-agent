"""Old Hangul (옛한글) helpers.

Old Hangul syllables are written with conjoining jamo: an initial (L), a medial (V) and an optional final (T),
which a font with Old Hangul support joins into one syllable block. Two things break that block:

1. markup: a tag boundary inside such a sequence (between L and V, V and T, or before a tone mark) splits the
   syllable on screen and in every program that reads the TEI file. `jamo_splits` finds such boundaries;
   `check_preservation` treats them like a changed text.
2. input: Hangul Compatibility Jamo (ㅅ ㆍ ㅁ, U+3131–318E, what a plain keyboard types) never join. `compat_to_conjoining`
   turns runs that contain an archaic letter into conjoining jamo, as an explicit, user-chosen step before tagging.
   Characters in the Private Use Area (old HWP files) can only be reported, not converted.
"""
from __future__ import annotations

import re
import unicodedata

from lxml import etree

L_RE = re.compile("[ᄀ-ᅟꥠ-ꥼ]")
V_RE = re.compile("[ᅠ-ᆧힰ-ퟆ]")
T_RE = re.compile("[ᆨ-ᇿퟋ-ퟻ]")
S_RE = re.compile("[가-힣]")  # precomposed modern syllables
TONE_RE = re.compile("[〮〯]")  # 방점
COMPAT_RUN = re.compile("[ㄱ-ㆎ]+")
COMPAT_ARCHAIC = re.compile("[ㅤ-ㆎ]")
COMPAT_VOWEL = re.compile("[ㅏ-ㅣㆇ-ㆎ]")
PUA_RE = re.compile("[-]")


def _initial_to_final() -> dict[str, str]:
    """Choseong -> jongseong of the same letter, from the Unicode character names."""
    out: dict[str, str] = {}
    for cp in list(range(0x11A8, 0x1200)) + list(range(0xD7CB, 0xD7FC)):
        name = unicodedata.name(chr(cp), "")
        if not name.startswith("HANGUL JONGSEONG "):
            continue
        try:
            out.setdefault(unicodedata.lookup(name.replace("JONGSEONG", "CHOSEONG")), chr(cp))
        except KeyError:
            continue
    return out


INITIAL_TO_FINAL = _initial_to_final()


def splits_syllable(prev: str, nxt: str) -> bool:
    """True if a tag boundary between these two characters would cut one syllable apart."""
    if not prev or not nxt:
        return False
    if V_RE.match(nxt) and (L_RE.match(prev) or V_RE.match(prev) or S_RE.match(prev)):
        return True
    if T_RE.match(nxt) and (V_RE.match(prev) or T_RE.match(prev) or S_RE.match(prev)):
        return True
    if TONE_RE.match(nxt) and (L_RE.match(prev) or V_RE.match(prev) or T_RE.match(prev) or S_RE.match(prev)):
        return True
    return False


def jamo_splits(frag: etree._Element) -> list[str]:
    """Problems for every element boundary inside an Old Hangul syllable (all text, editorial included)."""
    text: list[str] = []
    marks: set[int] = set()

    def pos() -> int:
        return sum(len(t) for t in text)

    def walk(el, top: bool) -> None:
        if not top:
            marks.add(pos())
        if el.text:
            text.append(el.text)
        for ch in el:
            if isinstance(ch.tag, str):
                walk(ch, False)
            if ch.tail:
                text.append(ch.tail)
        if not top:
            marks.add(pos())

    walk(frag, True)
    s = "".join(text)
    out = []
    for p in sorted(marks):
        if 0 < p < len(s) and splits_syllable(s[p - 1], s[p]):
            out.append(f"a tag boundary splits an Old Hangul syllable: '{s[max(0, p - 6):p]}|{s[p:p + 6]}' — "
                       "keep initial, vowel, final consonant and tone mark of one syllable inside the same tag")
    return out


def compat_to_conjoining(text: str) -> tuple[str, int]:
    """Rewrite runs of compatibility jamo that contain an archaic letter (ㆍ ㅿ ㆁ ㆆ ㅸ …) as conjoining jamo,
    syllable by syllable: initial + vowel(s) + optional final. Runs without an archaic letter are left alone
    (modern explanations like 'ㄱ, ㄴ'). Returns (new text, number of syllables built)."""
    built = 0

    def convert(run: str) -> str:
        nonlocal built
        if not (COMPAT_ARCHAIC.search(run) and COMPAT_VOWEL.search(run)):
            return run
        toks = [unicodedata.normalize("NFKD", c) for c in run]
        out, i = [], 0
        while i < len(toks):
            t = toks[i]
            if len(t) == 1 and L_RE.match(t) and i + 1 < len(toks) and V_RE.match(toks[i + 1][:1]):
                syl = t
                i += 1
                while i < len(toks) and all(V_RE.match(c) for c in toks[i]):
                    syl += toks[i]
                    i += 1
                if i < len(toks):
                    nxt = toks[i]
                    followed_by_vowel = i + 1 < len(toks) and V_RE.match(toks[i + 1][:1])
                    if len(nxt) == 1 and L_RE.match(nxt) and not followed_by_vowel and nxt in INITIAL_TO_FINAL:
                        syl += INITIAL_TO_FINAL[nxt]
                        i += 1
                    elif all(T_RE.match(c) for c in nxt):
                        syl += nxt
                        i += 1
                out.append(syl)
                built += 1
            else:
                out.append(run[i])  # not part of a syllable: keep the original character
                i += 1
        return "".join(out)

    return COMPAT_RUN.sub(lambda m: convert(m.group(0)), text), built


def inspect_text(text: str) -> dict:
    """What the start screen reports before tagging."""
    runs = [m.group(0) for m in COMPAT_RUN.finditer(text) if COMPAT_ARCHAIC.search(m.group(0)) and COMPAT_VOWEL.search(m.group(0))]
    return {"compat_runs": len(runs), "compat_examples": runs[:3], "pua": len(PUA_RE.findall(text)),
            "conjoining": bool(L_RE.search(text) or V_RE.search(text))}
