# TEI Agent — 다국어 인문 텍스트 대화형 TEI 태깅 에이전트

원문 텍스트를 넣으면 **TEI P5 4.12.0**(2026-07-28 공개, `tei_all`) 규칙에 맞춰 1차 자동 태깅을 합니다. 그다음 연구자와 묻고 답하며 태그와 헤더 메타데이터를 다듬어 갑니다. LLM은 **DeepSeek-V4.1-Flash**(API 모델명 `deepseek-flash`)를 씁니다. 한국 근현대소설 TEI 데이터셋 **KNoTE**와 유럽·영미권의 개방 라이선스 TEI 코퍼스를 few-shot 예시로 사용합니다.

| 요청 기능 | 구현 |
|---|---|
| 1. 다국어·다장르 | 장르 프로필 10종(산문 서사, 시가, 희곡, 서간, 역사기록, 고인쇄본·필사본, 금석문(EpiDoc), 발화 전사, 사전, 비문학)과 일반 프로필, 언어 규칙(ko·ja·zh/lzh·en·de·fr·la·grc)을 둡니다. 장르와 언어는 자동 판별하고, 사용자가 바꿀 수 있습니다. |
| 2. 자동 태깅 → 대화형 수정 | 분석 → 개체 레지스트리(인물·장소·기관 `xml:id`) → 블록 단위 병렬 태깅 → 원문 보존 검사 → 스키마 검사 순으로 진행합니다. 이후 자연어 지시, 질문에 대한 답, 에이전트 대화(tool calling)로 수정합니다. |
| 3. 추가 태그 추천 | 정규식 증거(따옴표, 날짜, 단위, 한자 병기, 결락 부호 등)와 LLM 판단을 결합합니다. 각 추천에는 근거 예문, 예상 건수, 우선순위가 붙고, 선택한 항목을 바로 적용할 수 있습니다. |
| 4. 풍부한 teiHeader와 메타데이터 추천 | 메타데이터 카탈로그 31항목(장르별 권장 수준 포함)을 둡니다. LLM은 값과 근거를 제안하고, Wikidata 검색으로 전거를 확인합니다. 헤더 XML은 코드가 결정론적으로 생성합니다. |

## 브라우저판 (설치 없이 실습용) — `dist/TEI_Agent.html`
- **실행:** 파일 하나(2.4 MB)를 Chrome이나 Edge에서 열면 바로 씁니다. 각자 DeepSeek API 키를 넣으며, 키는 그 브라우저에만 저장됩니다.
- **동작 방식:** Python판과 같은 규칙(태그·메타데이터 카탈로그, 언어 규칙, TEI 4.12 속성 허용 목록, few-shot 예시)과 같은 파이프라인을 JavaScript로 옮겼습니다.
- **검증:** tei_all 4.12.0 전체 검증도 브라우저 안에서 합니다. libxml2를 웹어셈블리로 옮긴 xmllint-wasm(MIT)을 써서 Python판과 같은 엔진입니다.
- **외부 통신:** DeepSeek API와, 요청할 때만 Wikidata로 나갑니다.
- **화면 기능:** 작업이 끝나면 결과 요약이 담긴 완료 막대(실패 시 빨간 막대)가 *확인*을 누를 때까지 남습니다. 읽기 보기에서 태그를 클릭해 요소·속성을 바꾸거나 지우고, 글자를 드래그해 태그를 붙이고, 블록별 ✎ XML로 직접 고칠 수 있습니다(원문 보존·스키마 검사 동일 적용, 되돌리기 가능). 오른쪽 패널은 대화로 수정하기가 맨 위(💬 탭)이고 질문·추천 태그는 옆 탭입니다. 헤더의 언어 선택으로 UI를 한국어/English로 바꿉니다(모델의 질문·설명 언어도 함께 바뀜).
- **정답 데이터 (0.1.2):** 헤더의 *📚 정답 데이터*에 프로젝트 방식으로 태깅된 TEI XML을 추가합니다(현재 문서도 추가 가능). *예시로 사용*한 항목은 같은 언어일 때 내장 예시보다 먼저 few-shot 예시로 들어갑니다. *현재 문서와 비교*는 `scripts/eval_knote.py`와 같은 방식(공백 제외 문자 위치)으로 요소별 정확 일치·겹침 P/R/F1, micro 평균, 화자(`@who`) 일치율을 계산하고 JSON으로 저장할 수 있습니다. 데이터는 그 브라우저에만 저장됩니다.
- **TEI 합치기 (0.1.2):** 헤더의 *⧉ TEI 합치기*로 TEI 파일 여러 개(현재 문서 포함)를 순서대로 합칩니다. ① **teiCorpus**: 문서마다 헤더를 유지하고 코퍼스 헤더(출처 목록·변경 기록)를 붙여 내려받습니다. ② **하나의 TEI**: 본문을 이어 붙이고(자체 div가 없는 문서는 지정한 유형의 div로 감쌈) 인물·장소 목록을 통합한 뒤 바로 열어 이어서 작업합니다. 두 방식 모두 겹치는 `xml:id`는 이름을 바꾸고 그 id를 가리키는 `#참조`도 고치며, 합친 결과를 tei_all로 검증합니다.
- **수업 자료:** 실습 안내는 `dist/실습_안내.md`, 예시 텍스트는 `dist/samples/`에 있습니다.
- **다시 만들기:** `python scripts/build_standalone.py`. 원본은 `standalone/app.js`, `ui.js`, `ui.css`, `ui_body.html`입니다.

## 프로젝트 지침 · 대화로 규칙 쌓기
- **프로젝트 지침**: 팀·반의 규칙(마크다운)을 모든 태깅 지시에 '9. PROJECT RULES'로 덧붙입니다. 일반 규칙과 충돌하면 지침이 우선하지만 원문 보존·스키마 검사는 바꿀 수 없습니다. `<!-- -->`는 메모로 보내지 않습니다. 작업 파일에 저장되고 TEI 헤더 `editorialDecl/interpretation`에 기록됩니다. 예시: `tei_agent/data/presets/mujeong_class.md`. CLI: `tei-agent tag 원문.txt -o out.xml --rules 지침.md`.
- **대화 루프**: 에이전트는 수정 요청마다 *측정(find_markup) → 일반 규칙이면 지침에 추가(set_project_rules) → 적용(apply_instruction, 검색어로 범위 제한) → 재측정·보고*를 따릅니다. 도구 19개.

## 범용성 (0.1.3)
- **규칙의 층:** ① TEI 공통 규칙(언어 중립, 예문은 문서 언어의 것만 삽입) ② 언어 규칙(ko·ja·zh/lzh·en·de·fr·es·it·pt·ru·la·grc) ③ 장르 프로필 ④ 관행 프리셋·프로젝트 지침. KNoTE의 태깅 관행은 프리셋 `knote_conventions`(브라우저판: *예시 지침 불러오기*, CLI: `--preset knote_conventions`)로 분리했습니다. KNoTE와 맞춰 태깅하거나 KNoTE 정답과 비교할 때 켭니다.
- **예시 선택:** 같은 장르 1편 + 문서 언어 1편. 장르도 언어도 다른 예시는 넣지 않습니다(예: 독일어 소설에 한국 소설 예시를 넣지 않음).
- **벤치마크:** `bench/manifest.json`(12편, 예시·튜닝에 쓰지 않은 파일), `scripts/fetch_bench.py` → `scripts/eval_gold.py` → `scripts/compare_runs.py`. API 없이 두 버전의 지시·예시를 비교하는 `scripts/probe_prompts.py`. v0.1.2와의 비교 결과는 `docs/generality_0.1.3.md`.

## 수업에서 쓰기 · GitHub로 관리하기
- **학생:** `dist/TEI_Agent.html`을 **내려받아** Chrome/Edge로 열고 본인 DeepSeek 키를 넣습니다. 드라이브·메일의 '미리보기'로 열면 동작하지 않습니다.
- **GitHub Pages(선택):** 저장소 Settings → Pages → Source를 *GitHub Actions*로 두면 `.github/workflows/pages.yml`이 `dist/`를 `https://<owner>.github.io/<repo>/`에 올립니다. 학생은 주소만 열면 됩니다(DeepSeek API는 Pages 출처의 브라우저 호출도 허용 — 2026-10-13 preflight 확인). 키는 그 주소의 브라우저 저장소에만 남습니다.
- **고치는 순서:** `standalone/`(브라우저판 원본)과 `tei_agent/`(파이썬판)를 함께 고친 뒤 `python scripts/build_standalone.py`로 `dist/TEI_Agent.html`을 다시 만들고 `pytest`를 돌려 커밋합니다. CI(`tests.yml`)가 테스트와 dist 최신 여부를 검사합니다.
- **스키마 갱신:** 새 TEI 판이 나오면 `tei_all.rng`를 교체하고 `python scripts/build_schema_index.py` → `build_standalone.py`.
- **올리지 말 것:** `.env`(API 키), `sessions/`, 학생 작업 파일(`*.teiagent.json`) — `.gitignore`에 들어 있습니다.
- 제3자 자료 라이선스는 `NOTICE.md`.

## 설치 (Windows / macOS / Linux)

Python 3.10 이상이 필요합니다.

```powershell
cd "TEI Agent\tei-agent"
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[mcp]"
copy .env.example .env          # macOS/Linux: cp .env.example .env
# .env에 DEEPSEEK_API_KEY=sk-... 입력
tei-agent serve                 # → http://127.0.0.1:8765
```

## 사용법

**웹 UI** (`tei-agent serve`)
1. 원문을 붙여넣고 **분석·자동 태깅 시작**을 누릅니다. 장르·언어 판별, 레지스트리 구축, 자동 태깅, 태그 추천이 차례로 실행됩니다.
2. **읽기 보기**에서 개체별 색 표시를 확인합니다. 마우스를 올리면 태그와 속성이 보입니다. 블록을 더블클릭하면 해당 블록에 대한 지시를 쓸 수 있습니다.
3. **추천 태그**에서 필요한 항목을 체크하고 *선택 태그 적용*을 누릅니다. 적용 시 추가 지침을 함께 쓸 수 있습니다.
4. **질문**에 답합니다. 화자가 불분명한 대사, 한자 언어 태그, 역법 같은 질문이 올라옵니다.
5. **대화로 수정하기**에 자연어로 지시합니다. 예: "‘그’가 김첨지를 가리키는 곳은 rs로 연결해줘", "저자 Wikidata ID 찾아서 넣어줘".
6. **메타데이터** 탭에서 *메타데이터 추천*을 받아 값을 적용하고, Wikidata로 전거를 지정합니다.
7. **검증 (tei_all)**을 돌리고, 오류가 있으면 **자동 수리**를 누른 뒤 **XML 저장**을 합니다.

기존 TEI 파일(예: KNoTE)을 **TEI XML 불러오기**로 열면 헤더는 그대로 두고 본문 검증·수리·추가 태깅을 할 수 있습니다.

**CLI**
```sh
tei-agent tag novel.txt -o novel.xml --accept-recommended --repair     # 일괄 처리
tei-agent tag novel.txt -o novel.xml --preset knote_conventions          # KNoTE 관행으로
tei-agent tag poem.txt -o poem.xml --genre poetry --interactive          # 터미널 대화
tei-agent validate file.xml                                              # tei_all 4.12.0 검증
tei-agent fix knote.xml -o knote_fixed.xml                               # 기존 TEI 스키마 오류 자동 수리
tei-agent mcp                                                            # MCP 서버 (DeepSeek Harness 연동)
```

## 설계 원칙: 신뢰할 수 있는 자동 태깅을 위해

- **원문 무변경 보장.** 모델 출력에서 태그를 걷어낸 텍스트를 원문과 비교합니다(공백 제외). 글자가 하나라도 바뀌면 그 블록은 수리를 한 번 요청합니다. 그래도 바뀌어 있으면 이전 마크업으로 되돌리고 ⚠ 표시합니다. 예외는 쪽번호 같은 제거 패턴과 편집적 추가 요소(`reg`, `corr`, `expan`, `ex`, `supplied`, `note`)뿐입니다.
- **스키마 기반 속성 허용 목록.** `tei_all.rng`(4.12.0)에서 요소 588개의 허용 속성과 자식 요소를 추출해 프롬프트에 넣습니다. 출력도 같은 목록으로 즉시 검사합니다. 허용되지 않은 속성은 수리를 요청하고, 그래도 남으면 결정론적으로 제거한 뒤 기록합니다.
- **헤더는 코드가 생성.** LLM은 값(JSON)만 제안하고, `teiHeader`와 `standOff`는 lxml로 조립합니다. 그래서 항상 well-formed이고 스키마에도 맞습니다.
- **기계 주석의 투명성.** `respStmt`(TEI-Agent + 모델명), `appInfo/application`, `revisionDesc/change`를 자동으로 기록합니다. 불확실한 태그에는 `@cert="low"`를 붙이고 질문으로 올립니다. 4.12의 `@generatedBy`는 CMC 모듈 전용이고 `post`에 묶여 있어 쓰지 않았습니다.
- **일관된 상호참조.** 문서 전체로 개체 레지스트리를 먼저 만들고, 모든 청크가 같은 `xml:id`를 씁니다. 등장인물은 `particDesc/listPerson`(KNoTE·DraCor 관행)에, 그 밖의 개체는 `standOff`에 둡니다. 정의되지 않은 `@ref`는 자동 보완하고 보고합니다.
- **한자 언어 태그.** KNoTE는 `xml:lang="zh"`를 썼습니다. 이 도구는 BCP 47에 따라 한국어의 한자 표기는 `ko-Hani`, 한문 구절은 `lzh`를 기본값으로 씁니다. 바꾸려면 대화창에 지시하면 됩니다.
- **되돌리기와 세션 저장.** 변경할 때마다 스냅샷을 남기고, 세션은 `sessions/*.json`에 저장합니다.

## few-shot 예시 코퍼스 (CC0 / CC BY만 사용)

| 예시 | 언어·장르 | 라이선스 |
|---|---|---|
| KNoTE 3편(동백꽃·운수 좋은 날·혈의 누) | ko 산문 | CC BY 4.0 (Zenodo 10.5281/zenodo.21218299) |
| ELTeC-eng (Trollope), ELTeC-fra (Adam) | en/fr 소설 | 텍스트 PD, 마크업 CC BY 4.0 |
| GerDraCor (Lessing, *Emilia Galotti*) | de 희곡 | CC0 |
| EEBO-TCP Phase I A00002 | en 근세 인쇄본 | CC0 |
| I.Sicily ISic000001 | la 금석문(EpiDoc) | CC BY 4.0 |
| ParlaMint-GB 샘플 | en 의회 발화 | CC BY 4.0 |
| DISCO 소네트 1편 *(0.1.3)* | es 시가(`lg`/`l`, 운율 속성) | CC BY 4.0 |
| Arthur Schnitzler 서간 L00040 *(0.1.3)* | de 서간(`address`·`salute`·`rs`·`note`) | CC BY 4.0 |
| 校異源氏物語テキストDB 5권 *(0.1.3)* | ja 고전 인쇄본(`pb`·`lb`) | CC0 1.0 |
| RusDraCor, Gogol 『Ревизор』 *(0.1.3)* | ru 희곡 | CC0 1.0 |
| ELTeC-deu, ELTeC-spa *(0.1.3)* | de/es 소설 | 텍스트 PD, 마크업 CC BY 4.0 |

출처와 라이선스 확인 내역은 `docs/references.md`에 있습니다. 예시를 다시 생성하려면 `scripts/build_exemplars.py`를 실행합니다. 예시 속의 4.12 무효 속성(예: KNoTE의 `said/@mode`)은 프롬프트에서 "따라 하지 말 것"으로 명시했습니다.

## 폴더 구성
```
tei_agent/
  pipeline.py    세션: analyze → registry → tag_all → recommend → retag/instruction → validate/repair → to_xml
  profiles.py    장르 프로필, 언어 규칙, 태그 카탈로그(39), 메타데이터 카탈로그(31)
  header.py      teiHeader·standOff 결정론적 생성
  schema.py      tei_all 4.12.0 RELAX NG 검증 + 속성 허용 목록
  xmlutils.py    원문 보존 검사
  heuristics.py  문자 체계·패턴 탐지 (오프라인 폴백, 추천 근거)
  tools.py       에이전트 도구(함수 호출 스키마) + 대화 루프
  mcp_server.py  MCP 서버 (DeepSeek Harness 등)
  server.py / web/index.html   로컬 웹 앱
  data/schema    tei_all.rng (4.12.0, CC BY/BSD-2), tei_index.json
  data/exemplars few-shot 예시 JSON
harness/         DeepSeek Harness overlay + 설명
docs/            KNoTE 4.12 검증 보고서, 참고문헌
tests/           mock DeepSeek 기반 종단 테스트 (pytest)
```

## DeepSeek 설정 (2026-10-12 공식 문서 확인)
- `model="deepseek-flash"`, `base_url="https://api.deepseek.com"` (OpenAI 호환), 컨텍스트 1M, 최대 출력 384K
- 기본값은 **thinking 끔**(`TEI_AGENT_THINKING=false`)입니다. 스키마 규칙을 따르는 태깅이라 속도와 비용을 우선했습니다. 켜면 tool calling 대화에서 `reasoning_content`를 매 턴 되돌려 보내야 하는데, 이 처리는 구현되어 있습니다.
- 비용은 사용량(토큰)과 피크 시간 단가 추정치로 UI 상단 배지에 표시됩니다.

## 실사용 검증 결과 (2026-10-13, `docs/live_evaluation_2026-10-13.md`)
- **KNoTE 6편 (41,200자):** 원문 보존 6/6, tei_all 4.12.0 유효 6/6, 편당 약 1분·약 $0.05(피크 단가 기준).
- **정확 일치 F1:** `said` 0.95, 한자 `foreign` 0.92, `persName` 0.69, 화자(`@who`) 일치 0.77.
- **약한 영역:** `rs`·`date`·`measure`·`placeName`은 0.4–0.5입니다. 일부는 모델 오류지만, 상당 부분은 KNoTE 정답의 관행 차이입니다(예: 서술자 '나'를 `persName`으로 태깅).
- **독일어 운문 희곡(GerDraCor):** `l` 176/176, `stage` 12/12. 영어 소설(ELTeC)은 구조가 일치했습니다.
- **모델이 낸 식별자는 신뢰할 수 없습니다.** 실제로 엉뚱한 Wikidata ID를 '높은 확신'으로 제시한 사례가 있었습니다. 그래서 식별자는 검증된 전거 검색으로만 넣고, 원문에 없는 서지 값은 '검증 필요'로 표시합니다.

## 한계와 다음 단계
- 공지시(`rs`)처럼 촘촘한 주석은 자동 1회로는 재현율이 낮습니다(약 0.3). 대화로 범위를 지정해 반복 적용하는 사용법을 권합니다.
- Schematron 규칙은 검증하지 않습니다(RELAX NG만). 최종 납품본은 jing이나 oXygen으로 한 번 더 검증할 것을 권합니다.
- 실제 `dsh` 환경에서 Harness overlay를 로드해 보지는 않았습니다.
- 다음 단계 후보:
  - 0.1.3 벤치마크(`bench/`)의 실측(DeepSeek API)과 33편 전체로 넓힌 평가
  - 한문·한국어 비문학·역사기록 예시(개방 TEI가 없어 직접 제작 필요)
  - 프로젝트 전용 ODD 생성
