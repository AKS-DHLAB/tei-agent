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

## 참고했으나 예시에서 제외한 자료 (사용자 결정: CC0/CC BY만)
- 동일조건(SA): Deutsches Textarchiv(DTABf, CC BY-SA 4.0), Perseus canonical-greekLit/latinLit(CC BY-SA 4.0), SARIT(CC BY-SA 4.0)
- 비영리·구독: Folger Shakespeare(비영리), CBETA(CC BY-NC-SA 4.0), Women Writers Online(구독)
- TEI가 아님: Kanseki Repository(Mandoku org-mode)
- 메타데이터 표준으로만 참고: correspSearch CMIF(서간 `correspDesc`), ParlaMint/Parla-CLARIN(발화), EpiDoc(금석문), TEI Lex-0(사전)

## 논문
- Kim, G., Park, S., Ji, H., Lee, H., Lee, B., Jeong, C., & Kim, B. (2026). KNoTE: A TEI Encoded XML Dataset of Modern Korean Novels. *Journal of Open Humanities Data*, 12(1), 102. https://doi.org/10.5334/johd.590
