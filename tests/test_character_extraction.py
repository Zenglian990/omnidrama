# -*- coding: utf-8 -*-
import re
from typing import List, Dict, Any, Tuple

test_tianli = """
第 01章 爱哭本章字数：2102字更新时间：2022-04-08
三月，南城刚下过一场雨，空气有点潮湿，拂过的清风带着春意。
一座古色古香的宅院坐落于深山处，云雾缭绕，宛如仙府。
“我才没有哭。”温梨小声吸了吸鼻子。
周肆漫不经心地笑了一声：“没哭？那眼睛怎么红得跟小兔子似的？”
“被风吹的。”温梨倔强地抬起头，对上男人的视线。
周肆俯下身，修长的手指捏了捏小姑娘软乎乎的脸颊：“过来，哥哥给你拿草莓蛋糕。”
“……要两块。”小姑娘犹豫了一下，小声说。
"""

SPEECH_VERB_REGEX = (
    r"(?:漫不经心地|冷冷地|缓缓地|突然|微微|小声|轻声|倔强地|咬牙切齿地|平静地|低头|抬头|转身|见状|闻言|自报家门|率先行礼)?"
    r"(?:说道?|道|说|笑道?|笑了一?声|冷笑|冷哼(?:了一?声)?|怒道?|问道?|喊道?|轻叹|轻笑|低语|低笑|沉声道?|质问道?|哭喊道?|反驳道?|轻嗤|自嘲|嘟囔|喃喃|回应|提醒|惊呼|吸了吸鼻子|行礼|自报家门)"
)

STOPWORDS = {
    "旁白", "有人", "众人", "此言", "这时", "忽然", "突然", "顿时", "刹那", "立刻",
    "冷冷", "缓缓", "淡淡", "猛地", "不由", "哈哈", "转身", "只见", "此时", "随即",
    "下一秒", "他", "她", "它", "我", "你", "这", "那", "环境", "Scene", "提示", "第"
}

def clean_spk(raw: str) -> str:
    s = raw.strip().strip("“”\"'：:，,。")
    s = re.sub(r"^(?:身边的|门外的|一旁的|迎出来的|跟前的|那|这个|这位|那个|一名|一个)", "", s)
    s = re.sub(r"(?:漫不经心地|冷冷地|缓缓地|突然|微微|小声|轻声|倔强地|平静地|身边的|率先|当即|随后|缓步|正色)", "", s)
    s = re.sub(r"(?:说道?|道|说|笑道?|冷笑|怒道?|问道?|喊道?|提醒|行礼|自报家门)$", "", s)
    if not s or s in STOPWORDS or len(s) < 2 or len(s) > 5:
        return "旁白"
    return s

def parse_tianli(text: str, title: str, genre: str):
    raw_lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    lines = []
    for rl in raw_lines:
        if re.search(r"本章字数|更新时间|作者有话说|最新网址|加入书架|目录|下一[页章]", rl):
            continue
        if rl.startswith("【") and rl.endswith("】"):
            continue
        lines.append(rl)

    shots = []
    characters = {}
    main_female = ""
    main_male = ""

    # 预扫描主要人物
    for line in lines:
        for m in re.finditer(r"([“\"])(.+?)[”\"]", line):
            pre = line[:m.start()].strip()
            suf = line[m.end():].strip()
            for seg in (pre, suf):
                m_name = re.search(r"([\u4e00-\u9fa5]{2,4}?)\s*" + SPEECH_VERB_REGEX, seg)
                if m_name:
                    cand = clean_spk(m_name.group(1))
                    if cand != "旁白":
                        is_fem = any(w in cand for w in "女妹妻小姐姐母琴雪涵妃婉瑶虞梨娇儿娘姑娘")
                        if is_fem and not main_female:
                            main_female = cand
                        elif not is_fem and not main_male:
                            main_male = cand

    for idx, line in enumerate(lines[:14], start=1):
        speaker = "旁白"
        dialogue = ""
        action_beat = line

        q_match = re.search(r"[“\"](.+?)[”\"]", line)
        if q_match:
            dialogue = q_match.group(1).strip()
            prefix = line[:q_match.start()].strip()
            suffix = line[q_match.end():].strip()

            cand = "旁白"
            # 检查自报家门 / 称呼前缀: "小的是言则" / "在下言十安"
            m_self = re.search(r"(?:在下|小的|在下是|我是|小女子|老夫|贫道)([\u4e00-\u9fa5]{2,3})", dialogue)
            if m_self:
                cand = clean_spk(m_self.group(1))

            if cand == "旁白" and prefix:
                m_pre = re.search(r"([\u4e00-\u9fa5]{2,4}?)\s*" + SPEECH_VERB_REGEX + r"[：:，,\s]*$", prefix)
                if m_pre:
                    cand = clean_spk(m_pre.group(1))
                if cand == "旁白":
                    m_sub = re.match(r"^([\u4e00-\u9fa5]{2,4}?)(?:[，,]|微微|转过身|俯下身|迈开长腿|伸手|率先行礼|抬头|看着|望着|轻笑|自报家门)", prefix)
                    if m_sub:
                        cand = clean_spk(m_sub.group(1))

            if cand == "旁白" and suffix:
                m_post = re.search(r"^([，,\s]*)([\u4e00-\u9fa5]{2,4}?)\s*" + SPEECH_VERB_REGEX, suffix)
                if m_post:
                    cand = clean_spk(m_post.group(2))
                if cand == "旁白":
                    m_sub2 = re.match(r"^([，,\s]*)([\u4e00-\u9fa5]{2,4}?)(?:[，,]|唇角|神色|目光|眼神|轻笑|自报家门|转身|犹豫|小声|红着眼|吸了吸鼻子|倔强地)", suffix)
                    if m_sub2:
                        cand = clean_spk(m_sub2.group(2))

            # 别称归一化: "小姑娘" 归入已识别的女主
            if cand in ("小姑娘", "少女", "女孩", "姑娘") and main_female:
                cand = main_female
            elif cand in ("男人", "少年", "青年") and main_male:
                cand = main_male

            speaker = cand
            action_beat = (prefix or suffix) if (prefix or suffix) else f"{speaker}正色说道"
        else:
            colon_m = re.match(r"^([^：:\s，,。]{2,6})[：:](.+)$", line)
            if colon_m:
                cand = clean_spk(colon_m.group(1))
                if cand != "旁白":
                    speaker = cand
                    dialogue = colon_m.group(2).strip().strip("“”\"'")
                    action_beat = f"{speaker}正色开口"
            else:
                dialogue = line
                action_beat = line
                m_lead = re.match(r"^([\u4e00-\u9fa5]{2,4}?)(?:靠着|收回视线|纵身而下|自报家门|轻笑|微微一愣|走上前|转过身|看着|心中|抬头|俯下身)", line)
                if m_lead:
                    cand = clean_spk(m_lead.group(1))
                    if cand != "旁白":
                        speaker = cand

        if speaker != "旁白":
            if speaker not in characters:
                is_fem = any(w in speaker for w in "女妹妻小姐姐母琴雪涵妃婉瑶虞梨娇儿娘姑娘")
                characters[speaker] = {
                    "name": speaker,
                    "gender": "female" if is_fem else "male",
                    "voice": "晓涵 (温柔清纯甜美)" if is_fem else "云扬 (热血阳光青年)"
                }

        shots.append({
            "id": idx,
            "speaker": speaker,
            "dialogue": dialogue,
            "action": action_beat
        })

    # 若全篇无任何角色或仅有1个角色，从题材自动提炼核心主配角
    if len(characters) < 2:
        if "甜宠" in genre or "言情" in genre:
            if not any(c["gender"] == "female" for c in characters.values()):
                f_name = main_female or (title[:2] if len(title) >= 2 else "女主")
                characters[f_name] = {"name": f_name, "gender": "female", "voice": "晓涵 (温柔清纯甜美)"}
            if not any(c["gender"] == "male" for c in characters.values()):
                characters["男主"] = {"name": "男主", "gender": "male", "voice": "云扬 (热血阳光青年)"}

    # 旁白根据题材定制音色
    is_romance = any(k in genre for k in ["甜宠", "言情", "现言", "古言", "恋爱", "青春", "校园"])
    characters["旁白"] = {
        "name": "旁白",
        "gender": "female" if is_romance else "male",
        "voice": "晓晓 (尖酸刻薄/成熟女主)" if is_romance else "云希 (磁性沉稳霸道)"
    }

    print("=== CHARACTERS ===")
    for c in characters.values():
        print(f"  {c['name']} [{c['gender']}] -> {c['voice']}")

    print("=== SHOTS ===")
    for s in shots:
        print(f"  #{s['id']:02d} [{s['speaker']}]: {s['dialogue'][:35]}")

def test_director_agent_breakdown():
    from core.director import DirectorAgent
    agent = DirectorAgent()
    proj = agent.breakdown_story_offline(test_tianli, "咬一口甜梨", "青春甜宠，现代言情")
    char_names = [c.name for c in proj.characters]
    assert "温梨" in char_names, f"Expected 温梨 in {char_names}"
    assert "周肆" in char_names, f"Expected 周肆 in {char_names}"
    assert "旁白" in char_names, f"Expected 旁白 in {char_names}"

    speakers = [s.speaker for s in proj.shots]
    assert "温梨" in speakers, f"Expected 温梨 in shot speakers {speakers}"
    assert "周肆" in speakers, f"Expected 周肆 in shot speakers {speakers}"
    assert "旁白" in speakers, f"Expected 旁白 in shot speakers {speakers}"

    # 验证第一镜没有杂质时间戳和字数
    assert "本章字数" not in proj.shots[0].dialogue
    assert "更新时间" not in proj.shots[0].dialogue
