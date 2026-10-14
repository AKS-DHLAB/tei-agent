# 범용성 개선 확인 — v0.1.2 → v0.1.3 (2026-10-14)

## 무엇이 바뀌었나
1. **규칙의 층 분리:** 공통 태그 규칙(`profiles.TAGS[*].rule`)을 TEI 지침 기준의 언어 중립 문장으로 바꾸고, 예문은 언어별(`examples`)로 두어 **문서의 언어에 해당하는 예문만** 프롬프트에 넣는다. KNoTE에서 정한 범위·관행(서술자 '나' = persName, 계절·상대 날짜 = date, 나이·기간 = measure, 하루의 때 = time, 한자 = `zh`, 모든 said에 aloud/direct)은 프리셋 `knote_conventions`로 옮겼다. 일반 명칭(친족어·호칭) 목록도 언어별로 나눴다(`GENERIC_FORMS_BY_LANG`).
2. **예시 선택:** ① 같은 장르 1편(같은 언어 우선) ② 문서 언어 1편(①이 이미 같은 언어면 같은 장르·언어일 때만). 장르도 언어도 맞지 않는 예시는 쓰지 않는다. 사전처럼 구조가 전혀 다른 장르는 다른 장르로 대신하지 않는다. ParlaMint 예시의 장르 표기 오류(`parliamentary` → `speech_transcript`)를 고쳤다.
3. **예시 보강:** 시가(es), 서간(de), 일본어 고전(ja), 러시아어 희곡(ru), 독일어·스페인어 소설 6편.
4. **범용성 벤치마크:** `bench/manifest.json`(5개 언어 이상·6개 장르·12편, 예시·튜닝에 쓰지 않은 파일, 커밋 고정) + `scripts/fetch_bench.py`, `scripts/eval_gold.py`, `scripts/compare_runs.py`, `scripts/probe_prompts.py`.
5. **버그 수정:** Python판 원문 보존 검사(`xmlutils.source_text`)가 편집 주석 안 하위 요소 뒤의 글자(`<note>… <rs>…</rs> 이 부분</note>`)를 원문으로 셌다. 해설 주석이 있는 서간·학술 편집본을 정답대로 태깅해도 '원문 변경'으로 거부될 수 있었다. 브라우저판은 원래 맞게 동작했다.

## 오프라인 확인 (API 호출 없음, `scripts/probe_prompts.py`)
각 벤치마크 항목에 대해 두 버전이 **모델에 실제로 보내는 태깅 지시**와 **정답 인코딩을 원문 보존 검사에 넣었을 때의 결과**를 비교했다.

| 항목 | v0.1.2 예시 | v0.1.3 예시 | 규칙 속 한글(자) | 정답 거부 | 프롬프트(자) |
|---|---|---|---|---|---|
| ko-knote-16/33/22 | knote-dongbaek, knote-hyeol | 같음 | 16 → 24 | 0 → 0 | 13,634 → 13,623 |
| en-eltec-tupper | eltec-eng-trollope, **knote-dongbaek** | eltec-eng-trollope | 16 → 0 | 0 → 0 | 13,139 → 9,422 |
| fr-eltec-audoux | eltec-fra-adam, **knote-dongbaek** | eltec-fra-adam | 16 → 0 | 0 → 0 | 13,113 → 9,314 |
| de-eltec-002 | **knote-dongbaek**, eltec-eng-trollope | eltec-deu | 16 → 0 | 0 → 0 | 13,156 → 9,404 |
| es-eltec-1002 | **knote-dongbaek**, eltec-eng-trollope | eltec-spa | 16 → 0 | 0 → 0 | 13,052 → 9,341 |
| de-drama-kleist | gerdracor-emilia | 같음 | 10 → 0 | 0 → 0 | 8,914 → 8,894 |
| ru-drama-chaika | gerdracor-emilia | rusdracor-revizor | 10 → 0 | 0 → 0 | 8,810 → 8,851 |
| es-poetry-disco | **gerdracor-emilia(희곡), knote-dongbaek(한국 소설)** | disco-sonnet | 16 → 0 | 0 → 0 | 12,754 → 8,043 |
| de-letter-schnitzler | **gerdracor-emilia(희곡), knote-hyeol(한국 소설)** | schnitzler-letter | 16 → 0 | **1 → 0** | 13,032 → 8,064 |
| la-inscription-isic | isicily-1 | 같음 | 31 → 0 | 0 → 0 | 9,052 → 8,902 |

합계(비한국어 9항목): 장르·언어 모두 다른 예시 **3 → 0**, 언어가 맞는 예시 5 → 9, 규칙 속 한글 **147자 → 0**, 'KNoTE' 언급 9 → 0, 정답 인코딩 오거부 **1 → 0**. 한국어 항목은 예시가 그대로이고, 한국어 예문이 명시적으로 늘었다(16 → 24자).

**해석:** 비한국어 텍스트에서 모델이 받는 지시와 예시가 그 언어·장르에 맞게 바뀌었고, 다른 언어의 관행(한국어 조사 규칙, KNoTE의 서술자 처리)을 섞어 보내지 않는다. 지시는 약 30% 짧아졌다(비용·주의 분산 감소). **다만 이것은 입력의 적합성이고, 태깅 정확도(F1)의 향상은 아직 측정하지 않았다** — 아래 실측이 필요하다.

## 실측 방법 (DeepSeek API 필요)
```sh
python scripts/fetch_bench.py                                   # 12편 내려받기 (bench/data/, 커밋되지 않음)
git worktree add ../tei-agent-0.1.2 9053a15                      # 비교용 이전 버전(GitHub main의 "update v0.1.2" 커밋)
python scripts/eval_gold.py --package-root ../tei-agent-0.1.2 --no-presets --out bench/results/v012
python scripts/eval_gold.py --no-presets --out bench/results/v013-neutral        # 중립 규칙만
python scripts/eval_gold.py --out bench/results/v013                              # KNoTE 항목에 knote_conventions 적용
python scripts/compare_runs.py bench/results/v012 bench/results/v013-neutral     # 범용성: 비한국어 항목을 볼 것
python scripts/compare_runs.py bench/results/v012 bench/results/v013             # 회귀: KNoTE 항목이 떨어지지 않아야 함
```
- 판정 기준 제안: 비한국어 항목에서 원문 보존·유효성 유지 + 구조/개체 F1 평균 상승, KNoTE 항목에서 `knote_conventions`를 켰을 때 v0.1.2 대비 하락 없음.
- ELTeC level-1은 개체 정답이 없어 구조(`head`·`p`)만 비교된다. 편당 비용은 6,000–8,000자 기준 약 $0.01–0.05로 추정(피크 단가).
