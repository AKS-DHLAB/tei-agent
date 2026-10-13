# DeepSeek Harness 연동 (2단계)

**결론: TEI Agent를 MCP 서버로 노출하고, dsh가 공식 `@deepseek-ai/dsh-mcp-client` 플러그인으로 연결하는 방식을 택했습니다.**

## 왜 MCP인가 (2026-10-12 확인)
- DeepSeek Harness(`deepseek-ai/deepseek-harness`, CLI `dsh`, MIT)는 현재 *developer preview*이고, README가 호환성을 깨는 변경을 예고합니다.
- dsh에는 외부 MCP 서버를 붙이는 공식 플러그인 `@deepseek-ai/dsh-mcp-client`가 있습니다(stdio / Streamable HTTP). 도구 이름은 `mcp__<serverName>__<tool>` 형식입니다.
- TEI 로직은 Python에 그대로 두고, dsh 내부 API(Cordis 플러그인)에 의존하지 않습니다. 그래서 dsh가 바뀌어도 overlay YAML만 고치면 됩니다.
- 같은 MCP 서버를 다른 MCP 호스트에서도 그대로 쓸 수 있습니다.

## 사용법
```sh
pip install -e ".[mcp]"
export DEEPSEEK_API_KEY=sk-...
dsh web --patch "$PWD/harness/tei-agent.cordis.yml"
```
- 연결을 계속 유지하려면 overlay의 `insert` 항목을 `$DSH_HOME/cordis.patch.yml`에 병합합니다(dsh 문서 `docs/user/guide/mcp-memory.md` 방식).
- `toolCallTimeoutMs`는 15분으로 잡아 두었습니다. dsh 기본값 60초로는 긴 문서 태깅이 끝나지 않습니다.

## 노출되는 도구
| 도구 | 기능 |
|---|---|
| `tei_new_session` | 원문 투입 후 분석(언어·장르·구조) |
| `tei_import` | 기존 TEI 파일 불러오기 |
| `tei_tag` | 레지스트리 구축 후 1차 자동 태깅 |
| `tei_recommend_tags` / `tei_accept_tags` | 추가 태그 추천과 적용 |
| `tei_instruct` / `tei_answer` | 자연어 지시, 질문에 대한 답변 반영 |
| `tei_recommend_metadata` / `tei_update_metadata` | 헤더 메타데이터 추천과 갱신 |
| `tei_lookup_authority` | Wikidata 후보 검색 |
| `tei_validate` | tei_all 4.12.0 검증(옵션으로 자동 수리) |
| `tei_export` | XML 파일로 저장 |
| `tei_status` / `tei_show_blocks` | 상태 확인 |

## 확인하지 못한 것
- 실제 `dsh` 실행 환경에서 overlay를 로드해 보지 않았습니다(이 작업 환경에 dsh 미설치). 다만 MCP 서버 자체는 공식 Python MCP 클라이언트로 stdio 왕복을 테스트했습니다.
- `!!js process.env…` 구문은 dsh 예제 파일을 그대로 따랐습니다.
