"""Deterministic text signals: scripts, quotation styles, dates, measures, verse/drama/letter cues.
Used as (a) fallback analysis without an API key, (b) evidence for recommendations."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

PATTERNS = {
    "quote_double_curly": r"“[^”]{1,400}”",
    "quote_straight": r"\"[^\"\n]{1,400}\"",
    "quote_kakko": r"「[^」]{1,400}」",
    "quote_double_kakko": r"『[^』]{1,400}』",
    "quote_guillemet": r"«[^»]{1,400}»",
    "quote_single_curly": r"‘[^’]{1,300}’",
    "paren_hanja": r"[가-힣]+\s?\([一-鿿]+\)",
    "year": r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?:년|\b)",
    "korean_date": r"\d{1,4}년\s?\d{1,2}월(?:\s?\d{1,2}일)?|\d{1,2}월\s?\d{1,2}일",
    "western_date": r"\b\d{1,2}(?:st|nd|rd|th)?\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s\d{4}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{1,2},?\s\d{4}\b",
    "sexagenary": r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]|[갑을병정무기경신임계][자축인묘진사오미신유술해]년",
    "lunar": r"음력|陰曆|윤[0-9一二三四五六七八九十]+월",
    "time": r"\b\d{1,2}:\d{2}\b|\d{1,2}시(?:\s?\d{1,2}분)?|(?:오전|오후|새벽|아침|저녁|밤|정오|자정)",
    "measure_ko": r"\d[\d,\.]*\s?(?:원|전|냥|량|리|척|근|평|간|되|말|섬|석|명|살|세|개|채|필|마리|km|kg|m)\b",
    "measure_west": r"[£$€]\s?\d[\d,\.]*|\b\d[\d,\.]*\s?(?:pounds?|shillings?|pence|francs?|marks?|Taler|Gulden|miles?|yards?|feet|foot|inches|livres?|sous|leagues?)\b",
    "speaker_colon": r"(?m)^\s*[^\s:：]{1,20}\s?[:：]\s?\S",
    "stage_paren": r"(?m)^\s*\([^)]{3,200}\)\s*$",
    "act_scene": r"(?mi)^\s*(?:act|scene|akt|szene|auftritt|aufzug|acte|scène|제?\s?\d+\s?막|제?\s?\d+\s?장)\b",
    "chapter": r"(?mi)^\s*(?:chapter|kapitel|chapitre|capítulo|제\s?\d+\s?[장회편절]|[一二三四五六七八九十百]+[章回]|\d{1,3}\.?)\s*.{0,30}$",
    "letter_open": r"(?mi)^\s*(?:dear|my dear|lieber|liebe|cher|chère|親愛|님께|님 보시오|前略|拜啓)",
    "letter_close": r"(?mi)(?:yours (?:truly|sincerely|faithfully|ever)|your (?:loving|affectionate)|ihr ergebener|dein|votre dévoué|올림|드림|上書|敬具|草々)\s*[,\.]?\s*$",
    "gap_marks": r"[□■○●]{1,}|\[\s?\.\.\.\s?\]|\[…\]|\(판독불가\)|\[illegible\]",
    "page_number_line": r"(?m)^\s*[-–—\[(]?\s*\d{1,4}\s*[-–—\])]?\s*$",
    "line_end_hyphen": r"[A-Za-zÀ-ÿ]-\n[a-zà-ÿ]",
    "long_s": r"ſ",
    "footnote_mark": r"\[\d{1,3}\]|\(\d{1,3}\)|※|\*\d",
    "markdown_emph": r"(?<!\w)[*_][^*_\n]{1,60}[*_](?!\w)",
    "ruby_paren": r"[一-鿿]+[（(][぀-ゟ]+[)）]",
    "vocal_noise": r"\((?:웃음|박수|침묵|울음|laughter|applause|pause|inaudible|unclear)\)|\[(?:웃음|박수|laughter|applause|inaudible)\]",
}
_COMPILED = {k: re.compile(v) for k, v in PATTERNS.items()}


def script_profile(text: str) -> dict[str, int]:
    c: Counter = Counter()
    for ch in text:
        if ch.isspace() or not ch.isalpha():
            continue
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7A3 or 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F:
            c["Hangul"] += 1
        elif 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2EBEF:
            c["Han"] += 1
        elif 0x3040 <= cp <= 0x30FF:
            c["Kana"] += 1
        elif 0x0370 <= cp <= 0x03FF or 0x1F00 <= cp <= 0x1FFF:
            c["Greek"] += 1
        elif 0x0400 <= cp <= 0x04FF:
            c["Cyrillic"] += 1
        elif 0x0590 <= cp <= 0x05FF:
            c["Hebrew"] += 1
        elif 0x0600 <= cp <= 0x06FF:
            c["Arabic"] += 1
        elif 0x0900 <= cp <= 0x097F:
            c["Devanagari"] += 1
        elif "LATIN" in unicodedata.name(ch, ""):
            c["Latin"] += 1
        else:
            c["Other"] += 1
    total = sum(c.values()) or 1
    return {k: round(100 * v / total) for k, v in c.most_common()}


def signals(text: str, max_examples: int = 4) -> dict[str, dict]:
    out = {}
    for k, rx in _COMPILED.items():
        ms = rx.findall(text)
        if ms:
            ex = []
            for m in ms[:max_examples]:
                ex.append((m if isinstance(m, str) else m[0])[:80])
            out[k] = {"count": len(ms), "examples": ex}
    lines = [l for l in text.splitlines() if l.strip()]
    if lines:
        short = sum(1 for l in lines if len(l.strip()) < 45)
        out["_short_line_ratio"] = {"count": round(100 * short / len(lines)), "examples": []}
    return out


def guess(text: str) -> dict:
    """Very rough offline guess of main language and genre."""
    sp = script_profile(text)
    sig = signals(text)
    main = "en"
    if sp.get("Hangul", 0) > 20:
        main = "ko"
    elif sp.get("Kana", 0) > 5:
        main = "ja"
    elif sp.get("Han", 0) > 50:
        main = "lzh"
    elif sp.get("Greek", 0) > 50:
        main = "grc"
    elif sp.get("Latin", 0) > 50:
        toks = re.findall(r"[a-zà-ÿß]+", text.lower())
        stop = {"en": {"the", "and", "of", "to", "i", "was", "in", "on", "my", "you", "sir", "yours", "is", "it", "that"},
                "de": {"und", "der", "die", "das", "nicht", "ich", "ist", "zu", "mit", "sie", "ein", "eine"},
                "fr": {"et", "le", "la", "les", "une", "est", "je", "il", "que", "de", "des", "du"},
                "la": {"et", "est", "cum", "ad", "non", "sed", "quod", "qui", "atque", "enim", "vixit", "annis"}}
        scores = {l: sum(1 for t in toks if t in ws) for l, ws in stop.items()}
        main = max(scores, key=scores.get) if any(scores.values()) else "en"
    genre = "prose_fiction"
    if sig.get("letter_open") or sig.get("letter_close"):
        genre = "correspondence"
    elif sig.get("speaker_colon", {}).get("count", 0) > 5:
        genre = "drama" if sig.get("act_scene") or sig.get("stage_paren") else "speech_transcript"
    elif sig.get("_short_line_ratio", {}).get("count", 0) > 70 and len(text) < 20000 and len(text.splitlines()) > 8:
        genre = "poetry"
    elif sig.get("gap_marks", {}).get("count", 0) > 3 and len(text) < 3000:
        genre = "inscription"
    langs = [{"ident": main, "label": main, "usage": 100}]
    if main == "ko" and sp.get("Han", 0) >= 1:
        langs = [{"ident": "ko", "label": "Korean", "usage": 100 - sp["Han"]}, {"ident": "ko-Hani", "label": "Korean in Han script", "usage": sp["Han"]}]
    return {"main_lang": main, "languages": langs, "genre": genre, "genre_confidence": 0.3, "scripts": sp,
            "title": None, "author": None, "structure": {}, "notes": "offline heuristic analysis"}


# which catalog keys a signal supports (for recommendation evidence)
SIGNAL_TO_TAG = {
    "quote_double_curly": "said", "quote_straight": "said", "quote_kakko": "said", "quote_guillemet": "said",
    "quote_double_kakko": "title", "quote_single_curly": "thought", "paren_hanja": "foreign", "year": "date",
    "korean_date": "date", "western_date": "date", "sexagenary": "date", "lunar": "date", "time": "time",
    "measure_ko": "measure", "measure_west": "measure", "speaker_colon": "sp", "stage_paren": "sp",
    "act_scene": "div", "chapter": "div", "letter_open": "letter_parts", "letter_close": "letter_parts",
    "gap_marks": "gap", "page_number_line": "milestones", "line_end_hyphen": "milestones", "long_s": "orig_reg",
    "footnote_mark": "note", "markdown_emph": "hi", "ruby_paren": "ruby", "vocal_noise": "u",
}
