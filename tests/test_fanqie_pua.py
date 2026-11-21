from core.director import DirectorAgent
from providers.fanqie_provider import FanqieProvider


def test_fanqie_pua_decode_full_sentence():
    # '的' = 0xE4F3, '一' = 0xE4DE, '是' = 0xE41E, '在' = 0xE3E9
    raw_obfuscated = "姜\ue4f3族\ue4de直\ue41e最\ue3e9意荣耀\ue4f3部族。"
    decoded = FanqieProvider.decode_pua(raw_obfuscated)
    assert decoded == "姜的族一直是最在意荣耀的部族。"


def test_director_sanitize_strips_legacy_fake_wuxia_lines():
    agent = DirectorAgent()
    polluted_text = (
        "主角：围绕第2章 买21亿的物资装满空间，无论前方有多少强敌环伺，我绝不退缩半步！\n"
        "强敌首领：大局已定，凭你一己之力，也妄想逆天改命？\n"
        "林晚星：立刻签下这21亿的采购合同，把整个港口的集装箱全部运进仓库！"
    )
    cleaned = agent._sanitize_or_enrich_raw_text(
        raw_text=polluted_text,
        title="天灾，我囤几十亿物资在末世求生",
        genre="科幻末世",
    )
    assert "无论前方有多少强敌环伺" not in cleaned
    assert "大局已定，凭你一己之力" not in cleaned
    assert "21亿的采购合同" in cleaned
