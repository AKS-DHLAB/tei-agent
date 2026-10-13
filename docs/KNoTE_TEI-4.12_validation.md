# KNoTE × TEI P5 4.12.0 검증 보고서

- 검증 일자: 2026-10-13 · 스키마: `tei_all.rng` P5 4.12.0 (2026-07-28) · 검증기: libxml2 RELAX NG (lxml 6.1)
- 대상: `AKS-DHLAB/KNoTE` `dataset/*.xml` 33개 (main 브랜치)
- **결과: 1/33 파일 유효** (「메밀꽃 필 무렵」 `28_…When Buckwheat Flowers Bloom.xml`)
- **jing 20241231 교차검증: 동일하게 1/33 유효, 오류 총 1,009건** — 속성 오류 상위: `@mode` 426, `@agent` 51, `@ref` 32, `@sex` 27, `@type` 23

> 아래 유형별 건수는 libxml2 기준입니다(오류를 묶어 보고하므로 jing보다 적게 나옵니다). 유효/무효 판정은 두 검증기가 일치합니다.

## 오류 유형 (상위 30)

| 오류 메시지 | 건수 | 파일 수 |
|---|---:|---:|
| Invalid attribute mode for element said | 371 | 21 |
| Invalid attribute ref for element measure | 30 | 10 |
| Invalid attribute sex for element rs | 18 | 4 |
| Did not expect element listPlace there | 15 | 15 |
| Did not expect element object there | 13 | 2 |
| Invalid attribute when for element date | 10 | 6 |
| Did not expect text in element div content | 7 | 3 |
| Element div has extra content: text | 7 | 3 |
| Did not expect element p there | 7 | 5 |
| Did not expect text in element gap content | 7 | 2 |
| Element gap has extra content: text | 7 | 2 |
| Invalid attribute when for element time | 7 | 1 |
| Did not expect element person there | 6 | 6 |
| Element listPerson has extra content: person | 6 | 6 |
| Invalid attribute type for element said | 6 | 1 |
| Invalid attribute subtype for element rs | 6 | 1 |
| Invalid attribute from for element measure | 5 | 4 |
| Invalid attribute quantity for element rs | 5 | 2 |
| Invalid attribute who for element persName | 5 | 1 |
| Did not expect element rolename there | 4 | 2 |
| Did not expect element head there | 4 | 4 |
| Invalid attribute type for element person | 4 | 4 |
| Invalid attribute type for element foreign | 4 | 1 |
| Invalid attribute sex for element persName | 3 | 2 |
| Element listPerson failed to validate content | 3 | 2 |
| Element said has extra content: object | 3 | 1 |
| Invalid attribute rtype for element rs | 3 | 2 |
| Expecting an element , got nothing | 2 | 1 |
| Invalid attribute calender for element date | 2 | 1 |
| Did not expect element personGrp there | 2 | 2 |

## 주요 원인과 TEI 4.12 권장 대안

| KNoTE 관행 | 문제 | 권장 대안 |
|---|---|---|
| `said/@mode` (thought, soliloquy…), `said/@agent` | `said`에 `@mode`·`@type`·`@agent` 없음 | `said aloud="false"` + 필요 시 `@ana="#thought"`(classDecl에 taxonomy 선언) 또는 `q type="thought"`(4.12 신설) |
| `measure/@ref` | `measure`에 `@ref` 없음 | `@commodity`, `@unitRef`, 또는 `@corresp` |
| `rs/@sex`, `persName/@sex`, `persName/@who` | 해당 속성 없음 | 성별은 `person/@sex`·`@gender`(레지스트리)에, 연결은 `@ref` |
| `date/@when`, `time/@when`의 비ISO 값 | `@when`은 ISO 8601만 허용 | 음력 등은 `@when-custom` + `@datingMethod`/`@calendar`, 혹은 텍스트만 |
| `foreign/@type` | `foreign`에 `@type` 없음 | `@xml:lang`(예: `ko-Hani`, `lzh`, `ja`)만 사용 |
| `div` 안의 맨 텍스트, `gap` 내부 텍스트 | 내용 모델 위반 | 텍스트는 `p`/`ab`로 감싸고, `gap`은 빈 요소 + `@reason`/`@quantity` |
| `listPlace`·`object` 위치 | 허용되지 않는 위치 | `standOff` 또는 `sourceDesc` 아래 `listPlace`/`listObject` |

## 파일별 결과

| 파일 | 유효 | 보고 오류 |
|---|:---:|---:|
| 01_Yi In-jik_Tears of Blood (Hyeol-ui Nu).xml | ✗ | 37 |
| 02_Yi Hae-jo_The Iron World (Cheol-segye).xml | ✗ | 26 |
| 03_Yi Kwang-su_The Heartless (Mujeong - Short Story).xml | ✗ | 18 |
| 04_Yi Hae-jo_Blood of Flowers (Hwa-ui Hyeol).xml | ✗ | 6 |
| 05_Kim Myeong-sun_The Girl of Mystery (Uisim-ui Sonyeo).xml | ✗ | 6 |
| 06_Na Hye-seok_Kyung-hee.xml | ✗ | 11 |
| 07_Na Hye-seok_To the Revived Granddaughter.xml | ✗ | 5 |
| 08_Kim Dong-in_The Sorrows of the Weak.xml | ✗ | 119 |
| 09_Yi Ik-sang_The Straggler (Nagoja).xml | ✗ | 6 |
| 10_Hyun Jin-geon_A Poor Wife (Bincheo).xml | ✗ | 14 |
| 11_Na Hye-seok_Gyu-won.xml | ✗ | 28 |
| 12_Hyun Jin-geon_A Society That Drives You to Drink.xml | ✗ | 2 |
| 13_Choi Seo-hae_Nostalgia (Hyangsu).xml | ✗ | 2 |
| 14_Hyun Jin-geon_A Lucky Day (Unsu Joeun Nal).xml | ✗ | 8 |
| 15_Kim Dong-in_Potato (Gamja).xml | ✗ | 13 |
| 16_Hyun Jin-geon_Director B and the Love Letters.xml | ✗ | 15 |
| 17_Na Do-hyang_The Watermill (Mullebang-a).xml | ✗ | 9 |
| 18_Bang Jeong-hwan_For Our Friends.xml | ✗ | 6 |
| 19_Bang Jeong-hwan_The Eternal Shirt (Mannyeon Shirt).xml | ✗ | 10 |
| 20_Bang Jeong-hwan_The Gold Watch.xml | ✗ | 1 |
| 21_Kim Dong-in_Dr. K's Research.xml | ✗ | 17 |
| 22_Kim Nam-cheon_Water (Mul).xml | ✗ | 17 |
| 23_Chae Man-sik_Ready-made Life.xml | ✗ | 33 |
| 24_Kang Kyeong-ae_Salt (Sogeum).xml | ✗ | 119 |
| 25_Gye Yong-mook_Adada the Idiot (Baekchi Adada).xml | ✗ | 13 |
| 26_Kim Yu-jeong_The Camellias (Dongbaek-kkot).xml | ✗ | 1 |
| 27_Yi Sang_The Wings (Nalgae).xml | ✗ | 39 |
| 28_Yi Hyo-seok_When Buckwheat Flowers Bloom.xml | ✓ | 0 |
| 29_Chae Man-sik_Uncle Chi-suk.xml | ✗ | 6 |
| 30_Jeong In-taek_Melancholy (Uuljeung).xml | ✗ | 5 |
| 31_Kim Sa-ryang_The Man Met in the Detention Center.xml | ✗ | 10 |
| 32_Ji Ha-ryeon_The Journey (Dojeong).xml | ✗ | 8 |
| 33_Kang So-cheon_The Photo Studio that Takes Pictures of Dreams.xml | ✗ | 6 |

TEI Agent의 `tei-agent fix <file> -o <out>` 또는 웹 UI의 'TEI 가져오기 → 검증 → 자동 수리'로 일괄 수정할 수 있습니다(DeepSeek API 키 필요).
