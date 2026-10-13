"""Genre profiles, language rules, tag catalog (for recommendations) and header-metadata catalog.

All element/attribute choices were checked against the tei_all 4.12.0 index (data/schema/tei_index.json).
Notable 4.12 facts used here: person/place/org are datable; q has @type (spoken, thought, written, soCalled…);
birth/death take @where; said has NO @type/@mode; measure has NO @ref; rs has NO @sex; foreign has NO @type.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Tag catalog: things the agent can auto-apply or recommend.
# key: unique id; elements: TEI elements involved; level: core (auto in first pass for the genres listing it)
# ---------------------------------------------------------------------------
TAGS: dict[str, dict] = {
    # --- structure
    "div": {"elements": ["div", "head"], "cat": "structure", "ko": "장·절 구분(div/head)",
            "rule": "Divisions (chapter, section, act, scene, entry, letter…) become <div type=… n=…> with <head>."},
    "p": {"elements": ["p"], "cat": "structure", "ko": "문단(p)", "rule": "Prose paragraphs → <p>."},
    "lg": {"elements": ["lg", "l"], "cat": "structure", "ko": "연·행(lg/l)",
           "rule": "Verse: each newline-separated line of the source block → one <l> (in drama, inside <sp>); stanzas → <lg type=\"stanza\" n=…>. Never put <p> inside <lg>."},
    "sp": {"elements": ["sp", "speaker", "stage"], "cat": "structure", "ko": "대사·화자·지문(sp/speaker/stage)",
           "rule": "Drama: speech → <sp who=\"#id\"><speaker>…</speaker><p>|<l>…</sp>; directions → <stage type=…>."},
    "letter_parts": {"elements": ["opener", "closer", "dateline", "salute", "signed", "postscript"], "cat": "structure",
                     "ko": "서간 구성요소(opener/closer/salute/signed)",
                     "rule": "Letters: dateline+salute in <opener>; closing salutation+signature in <closer>; P.S. in <postscript>."},
    "u": {"elements": ["u", "incident", "kinesic", "vocal", "pause", "gap"], "cat": "structure",
          "ko": "발화 전사(u)와 비언어 요소",
          "rule": "Spoken transcripts: each turn → <u who=\"#id\">; noises/gestures/pauses → <vocal>/<kinesic>/<incident>/<pause>; (laughter) → <vocal><desc>laughter</desc></vocal>."},
    "list": {"elements": ["list", "item", "label"], "cat": "structure", "ko": "목록(list/item)", "rule": "Enumerations → <list><item>."},
    "milestones": {"elements": ["pb", "lb", "cb", "milestone"], "cat": "structure", "ko": "쪽·행 경계(pb/lb)",
                   "rule": "Page numbers/page breaks in the source → <pb n=\"…\"/> at the break (the number moves into @n)."},
    "floatingText": {"elements": ["floatingText"], "cat": "structure", "ko": "삽입 텍스트(편지·노래 등, floatingText)",
                     "rule": "A complete embedded text (letter, song) inside narrative → <floatingText type=…><body>…</body></floatingText> (only where a block may occur)."},
    "note": {"elements": ["note"], "cat": "structure", "ko": "주석(note)", "rule": "Author/editor notes in the source → <note place=… type=…>."},
    "cit": {"elements": ["cit", "quote", "bibl"], "cat": "structure", "ko": "인용+출처(cit/quote/bibl)",
            "rule": "Quotation with its source → <cit><quote>…</quote><bibl>…</bibl></cit>."},
    # --- speech & quotation
    "said": {"elements": ["said"], "cat": "speech", "ko": "직접화법(said)",
             "rule": "Direct speech → <said who=\"#id\" direct=\"true\" aloud=\"true\">; quotation marks stay OUTSIDE the element. @who only if the speaker is identifiable."},
    "thought": {"elements": ["said"], "cat": "speech", "ko": "내적 독백·생각(said aloud=false)",
                "rule": "Inner thought/monologue → <said aloud=\"false\" who=\"#id\">. (TEI has no @mode/@type on said; use @ana=\"#thought\" only if a taxonomy is declared.)"},
    "q": {"elements": ["q"], "cat": "speech", "ko": "인용·소위(q type=…)",
          "rule": "Quoted material that is not a character's live speech → <q type=\"written|soCalled|spoken|thought\"> (q/@type is new in 4.12)."},
    "soCalled": {"elements": ["soCalled", "mentioned"], "cat": "speech", "ko": "이른바·언급(soCalled/mentioned)",
                 "rule": "Scare quotes → <soCalled>; words mentioned as words → <mentioned>."},
    # --- named entities
    "persName": {"elements": ["persName"], "cat": "entity", "ko": "인명(persName)",
                 "rule": "Personal NAMES only → <persName ref=\"#id\">. Pronouns, first-person narrator forms (나/내/난, I) and kinship terms are never persName: use <rs type=\"person\" ref=…> (TEI practice; differs from KNoTE, which tags the narrator '나' as persName). Titles/honorifics may be split with <roleName>/<forename>/<surname> only when asked."},
    "placeName": {"elements": ["placeName"], "cat": "entity", "ko": "지명(placeName)",
                  "rule": "PROPER place names only → <placeName ref=\"#id\">; natural features may use <geogName>. Generic place nouns (가게, 학교, 동네, the shop, the village) are NOT placeName — tag them <rs type=\"place\"> only if rs is active and they refer to a registered place."},
    "orgName": {"elements": ["orgName"], "cat": "entity", "ko": "기관·단체명(orgName)", "rule": "Organisations → <orgName ref=\"#id\">."},
    "rs": {"elements": ["rs"], "cat": "entity", "ko": "지시어·별칭·대명사(rs, 공지시)",
           "rule": "Pronouns (incl. first-person narrator forms 나/내/난/저, I/me), kinship terms, epithets and descriptive noun phrases that refer to a registered entity → <rs type=\"person|place|org|object\" ref=\"#id\">. Tag every such mention, not only the first. The span never includes case particles: <rs>그</rs>의, <rs>내</rs>가."},
    "roleName": {"elements": ["roleName"], "cat": "entity", "ko": "직함·관직(roleName)", "rule": "Titles/offices/occupations used as names → <roleName type=…>."},
    "objectName": {"elements": ["objectName"], "cat": "entity", "ko": "사물명(objectName)", "rule": "Names of notable objects (ships, artworks, artefacts) → <objectName>."},
    "title": {"elements": ["title"], "cat": "entity", "ko": "작품·서명(title)", "rule": "Titles of works mentioned in the text → <title level=\"m|a|j|s|u\">."},
    "name": {"elements": ["name"], "cat": "entity", "ko": "기타 고유명(name type=…)", "rule": "Other proper names (deities, animals, brands, events) → <name type=…>."},
    "event": {"elements": ["name"], "cat": "entity", "ko": "역사적 사건명(name type=event)", "rule": "Named historical events → <name type=\"event\" ref=\"#id\">."},
    # --- time & measure
    "date": {"elements": ["date"], "cat": "time", "ko": "날짜(date when=…)",
             "rule": "Dates and other temporal expressions → <date>: calendar dates (@when=\"YYYY[-MM[-DD]]\" ONLY if exactly resolvable to ISO 8601), but ALSO seasons (봄/summer), relative days (오늘, 이튿날, the next day), named days/festivals and 'N years ago' expressions, without @when. Non-Gregorian dates: keep text, use @calendar=\"#id\" + @when-custom/@datingMethod. Never put non-ISO text in @when/@from/@to; a date without a year uses --MM-DD (never year 0000)."},
    "time": {"elements": ["time"], "cat": "time", "ko": "시각(time)", "rule": "Times of day and parts of the day (밤, 새벽 두 시쯤, 점심때, that evening, at noon) → <time>; @when=\"HH:MM:SS\" only if exact."},
    "measure": {"elements": ["measure", "num"], "cat": "measure", "ko": "수량·단위(measure/num)",
                "rule": "Quantities with units → <measure type=\"currency|age|duration|length|weight|area|count…\" quantity=\"number\" unit=\"…\">. The span covers ONLY the number + unit (삼 원, 열다섯 살, 서너 달, two miles), not the counted noun (돈, 지폐), which may be named in @commodity. Ages (type=age) and durations (몇 해, 하루 종일, type=duration) count as measures. Bare numbers → <num value=…>. Numeric attributes (@quantity, @value, @atLeast, @atMost) take Arabic numerals only (열세 → 13, 삼십 → 30); ranges (팔구, 서너) → @atLeast/@atMost; vague (몇) → omit."},
    # --- language & orthography
    "foreign": {"elements": ["foreign"], "cat": "language", "ko": "외국어·한자 병기(foreign xml:lang)",
                "rule": "Words in another language/script → <foreign xml:lang=\"BCP47\">. Korean in Hanja: xml:lang=\"ko-Hani\"; Literary Chinese passages: \"lzh\"; Japanese \"ja\"."},
    "ruby": {"elements": ["ruby", "rb", "rt"], "cat": "language", "ko": "루비·후리가나(ruby/rb/rt)", "rule": "Interlinear glosses (furigana, Hanja readings) → <ruby><rb>漢字</rb><rt>かんじ</rt></ruby>."},
    "orig_reg": {"elements": ["choice", "orig", "reg"], "cat": "language", "ko": "원형/정규화 병기(choice/orig/reg)",
                 "rule": "Historical spelling with modern form → <choice><orig>…</orig><reg>…</reg></choice>; the source spelling goes in <orig>."},
    "abbr": {"elements": ["choice", "abbr", "expan", "ex"], "cat": "language", "ko": "약어 풀이(abbr/expan)",
             "rule": "Abbreviations → <choice><abbr>…</abbr><expan>…</expan></choice> (or EpiDoc <expan><abbr/>+<ex/>)."},
    "sic_corr": {"elements": ["choice", "sic", "corr"], "cat": "editorial", "ko": "오류 교정(sic/corr)", "rule": "Source errors → <choice><sic>…</sic><corr>…</corr></choice>."},
    "hi": {"elements": ["hi", "emph"], "cat": "rendition", "ko": "강조·서체(hi rend/emph)", "rule": "Typographic highlighting → <hi rend=\"italic|bold|spaced|underline…\">; linguistic emphasis → <emph>."},
    "term": {"elements": ["term", "gloss"], "cat": "concept", "ko": "개념어·전문용어(term)", "rule": "Technical or culturally specific terms → <term type=…> (optionally with <gloss>)."},
    "gap": {"elements": ["gap", "unclear", "supplied", "damage"], "cat": "editorial", "ko": "결락·판독불가(gap/unclear/supplied)",
            "rule": "Illegible/missing text: □, ○, [...] → <gap reason=\"illegible|lost\" quantity=… unit=\"chars\"/>; uncertain readings → <unclear>; editorially supplied → <supplied reason=…>."},
    "add_del": {"elements": ["add", "del", "subst"], "cat": "editorial", "ko": "삭제·첨가(del/add)", "rule": "Authorial revisions → <del>, <add place=…>, <subst>."},
    "fw": {"elements": ["fw"], "cat": "editorial", "ko": "난외 문자·면주(fw)", "rule": "Running heads, catchwords, signatures → <fw type=\"header|catch|sig|pageNum\">."},
    "rhyme": {"elements": ["rhyme", "caesura", "seg"], "cat": "verse", "ko": "운·휴지·후렴(rhyme/caesura/seg)", "rule": "Rhyme words → <rhyme label=…>; caesura → <caesura/>; refrains → <seg type=\"refrain\">."},
    "dict": {"elements": ["entry", "form", "orth", "gramGrp", "pos", "sense", "def", "cit"], "cat": "structure", "ko": "사전 항목(entry/form/sense, TEI Lex-0)",
             "rule": "Dictionary entries (TEI Lex-0 style): <entry xml:id><form type=\"lemma\"><orth/></form><gramGrp><pos/></gramGrp><sense n><def/><cit type=\"example\"><quote/></cit></sense></entry>."},
}

# ---------------------------------------------------------------------------
# Genres
# ---------------------------------------------------------------------------
GENRES: dict[str, dict] = {
    "prose_fiction": {
        "ko": "산문 서사(소설·설화)", "en": "Prose fiction",
        "core": ["div", "p", "said", "persName", "placeName", "orgName", "date", "foreign"],
        "optional": ["rs", "thought", "q", "time", "measure", "roleName", "title", "objectName", "term", "floatingText", "note", "hi", "soCalled", "milestones", "orig_reg"],
        "registry_location": "particDesc",
        "exemplars": ["knote-dongbaek", "eltec-eng-trollope", "eltec-fra-adam", "knote-hyeol", "knote-unsu"],
        "notes": "Characters go into profileDesc/particDesc/listPerson (KNoTE, ELTeC practice).",
    },
    "poetry": {
        "ko": "시가(시·가사·시조)", "en": "Poetry / verse",
        "core": ["div", "lg", "persName", "placeName", "date", "foreign"],
        "optional": ["rhyme", "said", "q", "hi", "title", "term", "note", "orig_reg", "milestones"],
        "registry_location": "standOff",
        "exemplars": ["gerdracor-emilia", "knote-dongbaek"],
        "notes": "Each poem may be a <div type=\"poem\"> with <head>; keep line breaks as <l>.",
    },
    "drama": {
        "ko": "희곡·대본", "en": "Drama",
        "core": ["div", "sp", "p", "lg", "persName", "placeName"],
        "optional": ["date", "rs", "foreign", "hi", "note", "q", "title", "measure"],
        "registry_location": "particDesc",
        "exemplars": ["gerdracor-emilia"],
        "notes": "Cast goes to particDesc/listPerson (DraCor practice); @who on <sp> points to it; acts/scenes are nested divs.",
    },
    "correspondence": {
        "ko": "서간·편지", "en": "Correspondence",
        "core": ["div", "letter_parts", "p", "persName", "placeName", "orgName", "date"],
        "optional": ["rs", "q", "title", "measure", "foreign", "note", "add_del", "gap", "hi", "milestones"],
        "registry_location": "standOff",
        "exemplars": ["knote-hyeol", "eltec-eng-trollope"],
        "notes": "Header should carry correspDesc/correspAction (CMIF-compatible) for sender/addressee/place/date.",
    },
    "historical_record": {
        "ko": "역사 기록(연대기·실록·일기·공문서)", "en": "Historical record (annals, diaries, administrative)",
        "core": ["div", "p", "date", "persName", "placeName", "orgName", "roleName"],
        "optional": ["term", "measure", "event", "foreign", "q", "note", "gap", "orig_reg", "abbr", "title", "milestones"],
        "registry_location": "standOff",
        "exemplars": ["tcp-a00002", "knote-hyeol"],
        "notes": "Dated entries → <div type=\"entry\"> with <head><date …/></head>; declare non-Gregorian calendars in profileDesc/calendarDesc.",
    },
    "early_print": {
        "ko": "근대 이전 인쇄본·필사본(원문 전사)", "en": "Early print / manuscript transcription",
        "core": ["div", "p", "milestones", "hi", "persName", "placeName"],
        "optional": ["abbr", "orig_reg", "fw", "gap", "sic_corr", "add_del", "foreign", "note", "date", "lg", "title"],
        "registry_location": "standOff",
        "exemplars": ["tcp-a00002"],
        "notes": "Preserve original spelling; regularisation only inside <choice>.",
    },
    "inscription": {
        "ko": "금석문·비문(EpiDoc)", "en": "Inscription (EpiDoc)",
        "core": ["milestones", "abbr", "gap", "persName", "measure"],
        "optional": ["placeName", "date", "foreign", "sic_corr", "term", "note"],
        "registry_location": "standOff",
        "exemplars": ["isicily-1"],
        "notes": "Follow EpiDoc: <div type=\"edition\" xml:lang=…><ab><lb n=…/>…</ab></div>; header needs msDesc (object, material, findspot, date).",
    },
    "speech_transcript": {
        "ko": "발화 전사(의회·구술·인터뷰)", "en": "Speech transcript (parliament, oral history, interview)",
        "core": ["div", "u", "persName", "placeName", "orgName", "date"],
        "optional": ["rs", "time", "measure", "event", "q", "term", "foreign", "note"],
        "registry_location": "particDesc",
        "exemplars": ["parlamint-gb"],
        "notes": "Speakers in particDesc/listPerson; header: recordingStmt in sourceDesc, settingDesc for occasion (ParlaMint/Parla-CLARIN practice).",
    },
    "dictionary": {
        "ko": "사전·어휘집", "en": "Dictionary / glossary",
        "core": ["dict", "foreign"],
        "optional": ["cit", "abbr", "hi", "note", "term"],
        "registry_location": "standOff",
        "exemplars": [],
        "notes": "TEI Lex-0 recommendations (dictionary example added to the Guidelines in 4.10).",
    },
    "nonfiction": {
        "ko": "논설·학술·비문학 산문", "en": "Essay / scholarly / non-fiction prose",
        "core": ["div", "p", "persName", "placeName", "orgName", "date", "title", "cit"],
        "optional": ["note", "term", "q", "soCalled", "measure", "foreign", "list", "hi", "event", "milestones"],
        "registry_location": "standOff",
        "exemplars": ["eltec-eng-trollope", "parlamint-gb"],
        "notes": "",
    },
}
GENRES["generic"] = {"ko": "기타(일반)", "en": "Generic", "core": ["div", "p", "persName", "placeName", "orgName", "date"],
                     "optional": [k for k in TAGS if k not in {"div", "p"}], "registry_location": "standOff",
                     "exemplars": ["knote-dongbaek", "eltec-eng-trollope"], "notes": ""}

# ---------------------------------------------------------------------------
# Language-specific encoding rules
# ---------------------------------------------------------------------------
LANG_RULES: dict[str, str] = {
    "ko": ("Korean: NEVER include postpositional particles (조사: 은/는/이/가/을/를/의/에/에서/에게/와/과/도/만/이나/께서…) "
           "inside ANY entity/referring tag (persName, placeName, rs, date, time, measure…): <persName>이형식</persName>은, <rs>그</rs>의. "
           "Place names include an attached locative noun only when it is part of the name (칠성문 밖 as a district name). "
           "Honorific/address suffixes (군, 씨, 양, 님, 선생) stay OUTSIDE <persName>: <persName>우영</persName> 군. Hanja glosses in parentheses after Hangul → "
           "이형식(<foreign xml:lang=\"ko-Hani\">李亨植</foreign>); whole Literary-Chinese passages → xml:lang=\"lzh\". "
           "Keep archaic spellings (아래아, 옛한글) exactly. Quotation marks “ ” 「 」 『 』 stay outside <said>/<q>."),
    "ja": ("Japanese: keep kana/kanji exactly; furigana given in parentheses or brackets → <ruby><rb>…</rb><rt>…</rt></ruby>; "
           "do not include particles (は/が/を/に/の…) inside entity tags; 「」 stay outside <said>."),
    "zh": ("Chinese: do not segment or add spaces; for Literary Chinese (xml:lang=\"lzh\") keep original punctuation or its absence; "
           "variant characters may be recorded with <choice><orig/><reg/></choice> only when asked."),
    "lzh": "Literary Chinese: same as zh; xml:lang=\"lzh\".",
    "en": "English: historical spellings stay as in the source; long s (ſ) preserved; regularisation only via <choice><orig><reg>.",
    "de": "German: preserve historical orthography (Fraktur ligatures as characters, ſ, ꝛ, e superscript as given); Sperrsatz → <hi rend=\"spaced\">.",
    "fr": "French: preserve historical spellings and typographic quotes « »; guillemets stay outside <said>.",
    "la": "Latin: abbreviations follow EpiDoc (<expan><abbr>…</abbr><ex>…</ex></expan>) when expansions are requested.",
    "grc": "Ancient Greek: keep polytonic diacritics exactly; EpiDoc conventions for epigraphic texts.",
}


# ---------------------------------------------------------------------------
# Header metadata catalog (what can be recommended for <teiHeader>)
# level: required | recommended | optional ; genres: "*" or list
# ---------------------------------------------------------------------------
METADATA_FIELDS: list[dict] = [
    {"key": "title", "path": "fileDesc/titleStmt/title", "level": "required", "genres": "*", "ko": "작품명(원어·번역·부제)",
     "why": "TEI 필수 요소. 원제/번역제/부제를 @type·@xml:lang으로 구분하면 다국어 검색에 유리합니다."},
    {"key": "authors", "path": "fileDesc/titleStmt/author", "level": "recommended", "genres": "*", "ko": "저자 + 전거 ID(Wikidata·VIAF·ISNI)",
     "why": "LOD 연결: <author ref=\"wikidata URI\"> 및 <idno type=…>."},
    {"key": "resp", "path": "fileDesc/titleStmt/respStmt", "level": "recommended", "genres": "*", "ko": "책임 표시(인코딩·검수·자동 태깅 도구)",
     "why": "누가/무엇이 태깅했는지(사람·AI) 명시 — 기계 주석의 투명성."},
    {"key": "funder", "path": "fileDesc/titleStmt/funder", "level": "optional", "genres": "*", "ko": "연구비 지원기관·과제번호", "why": "과제 성과물 표기."},
    {"key": "edition", "path": "fileDesc/editionStmt", "level": "optional", "genres": "*", "ko": "전자판 판차·버전", "why": "개정 이력과 인용 안정성."},
    {"key": "extent", "path": "fileDesc/extent", "level": "recommended", "genres": "*", "ko": "분량(글자 수·단어 수, 자동 계산)", "why": "코퍼스 통계 비교."},
    {"key": "publication", "path": "fileDesc/publicationStmt", "level": "required", "genres": "*", "ko": "발행 정보(발행처·장소·일자·식별자)", "why": "TEI 필수 요소."},
    {"key": "licence", "path": "fileDesc/publicationStmt/availability/licence", "level": "recommended", "genres": "*",
     "ko": "이용 조건(CC 라이선스 URL)", "why": "재사용 조건을 기계가독형으로 명시(@target에 라이선스 URI)."},
    {"key": "pid", "path": "fileDesc/publicationStmt/idno[@type='DOI']", "level": "optional", "genres": "*", "ko": "영구 식별자(DOI·Handle)", "why": "인용 가능성(Zenodo 등)."},
    {"key": "series", "path": "fileDesc/seriesStmt", "level": "optional", "genres": "*", "ko": "소속 컬렉션·코퍼스명", "why": "코퍼스 단위 관리(예: KNoTE)."},
    {"key": "source", "path": "fileDesc/sourceDesc/bibl|biblStruct", "level": "required", "genres": "*",
     "ko": "저본 서지(초출지·발행일·쪽수·디지털 저본 URL)", "why": "TEI 필수. 초판/디지털 저본을 @type으로 구분하면 판본 추적이 가능합니다."},
    {"key": "msdesc", "path": "fileDesc/sourceDesc/msDesc", "level": "recommended", "genres": ["inscription", "early_print", "historical_record", "correspondence"],
     "ko": "자료 실물 기술(소장처·청구기호·재질·크기·상태)", "why": "필사본·금석문은 물리적 맥락이 해석의 근거."},
    {"key": "recording", "path": "fileDesc/sourceDesc/recordingStmt", "level": "recommended", "genres": ["speech_transcript"],
     "ko": "녹음·녹화 정보(일시·장소·매체·길이)", "why": "구술·의회 전사의 원자료 추적."},
    {"key": "project", "path": "encodingDesc/projectDesc", "level": "recommended", "genres": "*", "ko": "프로젝트 목적·범위", "why": "인코딩 의도 공유."},
    {"key": "sampling", "path": "encodingDesc/samplingDecl", "level": "optional", "genres": "*", "ko": "표본·발췌 방식", "why": "발췌본일 경우 범위 명시."},
    {"key": "editorial", "path": "encodingDesc/editorialDecl", "level": "recommended", "genres": "*",
     "ko": "편집 원칙(정규화·인용부호·하이픈·교정·분절)", "why": "원문 보존/정규화 정책을 명시해야 재현 가능."},
    {"key": "tagsDecl", "path": "encodingDesc/tagsDecl", "level": "recommended", "genres": "*", "ko": "사용 태그 통계(자동 생성)", "why": "문서에 쓰인 요소·빈도 자동 기록."},
    {"key": "classDecl", "path": "encodingDesc/classDecl/taxonomy", "level": "optional", "genres": "*", "ko": "분류 체계(장르·주제 taxonomy)", "why": "textClass/@ana 값의 정의."},
    {"key": "appInfo", "path": "encodingDesc/appInfo/application", "level": "recommended", "genres": "*", "ko": "사용 소프트웨어·모델(자동 기록)", "why": "AI 모델과 버전 기록."},
    {"key": "creation", "path": "profileDesc/creation", "level": "recommended", "genres": "*", "ko": "창작·작성 시기와 장소", "why": "출판일과 구분되는 저작 시기."},
    {"key": "languages", "path": "profileDesc/langUsage", "level": "recommended", "genres": "*", "ko": "사용 언어·문자(비율 포함)", "why": "다국어·혼종 문자 텍스트 기술."},
    {"key": "keywords", "path": "profileDesc/textClass/keywords", "level": "recommended", "genres": "*", "ko": "장르·주제어(통제어휘: LCSH, Wikidata 등)", "why": "검색·분류."},
    {"key": "abstract", "path": "profileDesc/abstract", "level": "optional", "genres": "*", "ko": "초록·줄거리", "why": "탐색 편의."},
    {"key": "persons", "path": "profileDesc/particDesc/listPerson | standOff/listPerson", "level": "recommended", "genres": "*",
     "ko": "인물 목록(성별·역할·관계·전거)", "why": "본문 @ref의 대상. 등장인물/역사 인물 메타데이터."},
    {"key": "places", "path": "standOff/listPlace", "level": "optional", "genres": "*", "ko": "장소 목록(좌표·Wikidata/GeoNames)", "why": "지도화·LOD."},
    {"key": "orgs", "path": "standOff/listOrg", "level": "optional", "genres": "*", "ko": "기관 목록", "why": "본문 orgName/@ref 대상."},
    {"key": "relations", "path": "standOff/listRelation", "level": "optional", "genres": ["prose_fiction", "drama", "correspondence", "historical_record"],
     "ko": "인물 관계(가족·사제·적대 등)", "why": "네트워크 분석."},
    {"key": "setting", "path": "profileDesc/settingDesc", "level": "optional", "genres": ["prose_fiction", "drama", "speech_transcript"], "ko": "배경(시공간)·발화 상황", "why": "서사 배경/회의 맥락."},
    {"key": "corresp", "path": "profileDesc/correspDesc", "level": "recommended", "genres": ["correspondence"], "ko": "발신·수신(인물·장소·일자, CMIF 호환)", "why": "correspSearch 연계."},
    {"key": "calendar", "path": "profileDesc/calendarDesc", "level": "recommended", "genres": ["historical_record", "correspondence", "inscription"],
     "ko": "역법 선언(음력·왕력·간지 등)", "why": "@calendar가 가리킬 대상."},
    {"key": "revisions", "path": "revisionDesc/change", "level": "recommended", "genres": "*", "ko": "수정 이력(자동 태깅·검수 기록)", "why": "기계/인간 작업 단계 추적."},
]


def genre_keys() -> list[str]:
    return list(GENRES)


def tags_for(genre: str, keys: list[str]) -> list[str]:
    els: list[str] = []
    for k in keys:
        els += TAGS.get(k, {}).get("elements", [])
    return sorted(set(els))


def rules_text(keys: list[str]) -> str:
    return "\n".join(f"- [{k}] {TAGS[k]['rule']}" for k in keys if k in TAGS)


def metadata_fields_for(genre: str) -> list[dict]:
    return [f for f in METADATA_FIELDS if f["genres"] == "*" or genre in f["genres"]]
