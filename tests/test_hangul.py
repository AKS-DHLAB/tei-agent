"""Old Hangul: tags must not split a conjoining-jamo syllable; compatibility jamo can be joined on request."""
from tei_agent.hangul import compat_to_conjoining, inspect_text
from tei_agent.xmlutils import check_preservation

RAW = "ᄒᆞᆫ 사ᄅᆞ〮ᆷ이 나랏〮말ᄊᆞ미"


def test_whole_syllables_inside_tags_pass():
    assert check_preservation(RAW, "<persName>ᄒᆞᆫ 사ᄅᆞ〮ᆷ</persName>이 나랏〮말ᄊᆞ미")["ok"]


def test_tag_boundary_inside_a_syllable_fails():
    for xml in ("<persName>ᄒᆞ</persName>ᆫ 사ᄅᆞ〮ᆷ이 나랏〮말ᄊᆞ미",      # vowel | final
                "<rs>ᄒ</rs>ᆞᆫ 사ᄅᆞ〮ᆷ이 나랏〮말ᄊᆞ미",                  # initial | vowel
                "ᄒᆞᆫ <rs>사ᄅᆞ</rs>〮ᆷ이 나랏〮말ᄊᆞ미",                  # syllable | tone mark
                "ᄒᆞᆫ 사ᄅᆞ〮ᆷ이 <placeName>나랏</placeName>〮말ᄊᆞ미"):   # precomposed syllable | tone mark
        r = check_preservation(RAW, xml)
        assert not r["ok"] and "Old Hangul syllable" in r["problems"][0], xml


def test_modern_korean_is_unaffected():
    assert check_preservation("김첨지는 웃었다", "<persName>김첨지</persName>는 웃었다")["ok"]


def test_compatibility_jamo_are_joined_only_where_archaic_letters_occur():
    text, n = compat_to_conjoining("ㅅㆍㅁ ㄱㆍㅿ ㄱ, ㄴ ㄱㅏ ㅎㆍㄴ ㆍ")
    assert text == "ᄉᆞᆷ ᄀᆞᇫ ㄱ, ㄴ ㄱㅏ ᄒᆞᆫ ㆍ" and n == 3
    r = inspect_text("ㅅㆍㅁ ")
    assert r["compat_runs"] == 1 and r["pua"] == 1
