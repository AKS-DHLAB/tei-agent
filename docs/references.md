# 참고 자료와 확인 내역 (2026-10-12~13)

## 표준·모델
- TEI P5 Guidelines **4.12.0 "Igor"**, 2026-07-28. 근거: 현재 배포 중인 `tei_all.rng` 헤더("P5 Version 4.12.0. Last updated on 28th July 2026"). 릴리스 노트: https://tei-c.org/release/doc/tei-p5-doc/readme-4.12.0.html
  - 고정 스키마: https://www.tei-c.org/Vault/P5/4.12.0/xml/tei/custom/schema/relaxng/tei_all.rng (CC BY / BSD-2)
  - 이 도구의 규칙·헤더에 직접 쓰인 4.12 변경: `q/@type`, `person`·`place`·`org`의 datable 속성, `birth`·`death/@where`. 그 밖에 4.12 스키마에서 확인한 사항: `person`·`place`·`org` 안의 `ref` 허용, `div` 안의 `address` 허용
- DeepSeek API: https://api-docs.deepseek.com/quick_start/pricing (`deepseek-flash` = DeepSeek-V4.1-Flash), https://api-docs.deepseek.com/guides/thinking_mode, https://api-docs.deepseek.com/guides/json_mode
- DeepSeek Harness: https://github.com/deepseek-ai/deepseek-harness (commit d7432673, 2026-10-09 확인; MCP 연동은 `packages/mcp/mcp-client/README.md`)

## few-shot 코퍼스 (CC0/CC BY만 사용; 라이선스는 저장소 파일에서 직접 확인)
| 코퍼스 | URL | 라이선스 확인 근거 |
|---|---|---|
| KNoTE | https://github.com/AKS-DHLAB/KNoTE · doi:10.5281/zenodo.21218299 | Zenodo 레코드 메타데이터 `cc-by-4.0` |
| ELTeC-eng / ELTeC-fra | https://github.com/COST-ELTeC | README "Licence": 텍스트 PD, 마크업 CC BY 4.0 |
| GerDraCor | https://github.com/dracor-org/gerdracor | README: CC0 |
| EEBO-TCP Phase I (A00002) | https://github.com/TextCreationPartnership/A00002 | `<availability>`: CC0 1.0 |
| I.Sicily | https://github.com/ISicily/ISicily | `licence.txt`: CC BY 4.0 |
| ParlaMint (GB 샘플) | https://github.com/clarin-eric/ParlaMint | 파일 내 `<licence>`: CC BY 4.0 |
| DISCO (0.1.3) | https://github.com/pruizf/disco (`tei/15th-17th/per-sonnet/disco018g_0031.xml`) | README "Licence and Citation": CC BY 4.0 (파일 내 `<availability>`는 "freely available"만 표기) |
| Arthur Schnitzler: Briefwechsel (0.1.3) | https://github.com/arthur-schnitzler/schnitzler-briefe-data (`data/editions/L00040.xml`) | 파일 내 `<licence target=".../by/4.0/">`: CC BY 4.0 (저장소 코드는 MIT) |
| 校異源氏物語テキストDB (0.1.3) | https://github.com/kouigenjimonogatari/kouigenjimonogatari.github.io (`xml/master/05.xml`) | README "TEI data (`xml/master/*.xml`): CC0 1.0", 파일 내 `<availability>`: CC0 1.0 |
| RusDraCor (0.1.3) | https://github.com/dracor-org/rusdracor (`tei/gogol-revizor.xml`) | 파일 내 `<licence>`: CC0 1.0 |
| ELTeC-deu / ELTeC-spa (0.1.3) | https://github.com/COST-ELTeC/ELTeC-deu · ELTeC-spa (`level1/DEU001.xml`, `level1/SPA1001_…xml`) | README "Licence" 및 파일 내 `<licence>`: 텍스트 PD, 마크업 CC BY 4.0 |

0.1.3 예시는 2026-10-14에 각 저장소를 얕게 복제해 위 근거를 직접 확인했습니다. 예시를 만들 때 원 프로젝트의 이미지·API 서버를 가리키는 `@facs`·`@corresp` URL은 원문만으로 재현할 수 없어 지웠고(속성이 없어진 `seg`는 풀어 냄), 편집 주석(`note`)은 '원문(raw_input)'에서 뺐습니다.

## 참고했으나 예시에서 제외한 자료 (사용자 결정: CC0/CC BY만)
- 동일조건(SA): Deutsches Textarchiv(DTABf, CC BY-SA 4.0), Perseus canonical-greekLit/latinLit(CC BY-SA 4.0), SARIT(CC BY-SA 4.0)
- 비영리·구독: Folger Shakespeare(비영리), CBETA(CC BY-NC-SA 4.0), Women Writers Online(구독)
- TEI가 아님: Kanseki Repository(Mandoku org-mode)
- 0.1.3 조사에서 제외: FreDraCor(CC BY-NC-SA 4.0), Alfred Escher 서간(CC BY-SA 4.0), Eighteenth Century Poetry Archive(CC BY-SA 4.0), Corpus of Czech Verse(CC BY-SA), Sonetos Siglo de Oro(CC BY-NC 4.0)
- 0.1.3 보류(라이선스는 개방적이나 CC0/CC BY가 아님 — 사전 예시 후보): TEI Lex-0 예시(`BCDH/TEI-Lex-0`, BSD-3-Clause), DARIAH lexicalresources(BSD-2-Clause)
- 0.1.3 조사에서 개방 TEI를 찾지 못한 영역: 한문(lzh), 한국어 비문학·역사기록·고전시가, 현대 일본어 문학 → 정답 데이터 기능으로 프로젝트별 보충
- 메타데이터 표준으로만 참고: correspSearch CMIF(서간 `correspDesc`), ParlaMint/Parla-CLARIN(발화), EpiDoc(금석문), TEI Lex-0(사전)

## 논문
- Kim, G., Park, S., Ji, H., Lee, H., Lee, B., Jeong, C., & Kim, B. (2026). KNoTE: A TEI Encoded XML Dataset of Modern Korean Novels. *Journal of Open Humanities Data*, 12(1), 102. https://doi.org/10.5334/johd.590
