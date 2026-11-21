"""OmniDrama 电影级短剧爆款人设母版库 (Built-in Drama Archetypes Library).

内置行业专业电影级短剧标准人设母版：
- 04 现代女主-都市丽人 (04_modern_female_urban)
- 05 现代男主-霸总 (05_modern_male_boss)
- 06 古装男主-清冷世子 (06_ancient_male_noble)
- 08 反派女二-绿茶千金 (08_antagonist_female_greentea)

提供标准人物三视图 (16:9)、骨相五官锁、发型发色锁、服饰装束锁、专属防崩排异负向词、
最佳 Edge-TTS 音色绑定 (含微调语速语调)、生图与多模态参考参数，以及母版检索、套用与分镜提示词编译核心接口。
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field, model_validator

try:
    from omnidrama.schemas.drama_schema import (
        CharacterAsset,
        CharacterConsistencyCard,
        ReferenceImageConfig,
        ShotScaleEnum,
    )
except ImportError:
    from schemas.drama_schema import (
        CharacterAsset,
        CharacterConsistencyCard,
        ReferenceImageConfig,
        ShotScaleEnum,
    )

# 向后兼容别名
ConsistencyCard = CharacterConsistencyCard


class DramaArchetype(BaseModel):
    """爆款短剧角色母版模型 (Drama Archetype Contract)."""
    id: str = Field(..., description="母版全局唯一标识，如 '04_modern_female_urban'")
    code: str = Field(..., description="数字代号，如 '04'")
    name: str = Field(..., description="母版中文名称，如 '现代女主-都市丽人'")
    genre_category: str = Field(default="", description="适用题材类型，如 '现代都市 / 职场言情 / 双强商战'")
    gender: str = Field(default="male", description="性别: 'male' / 'female'")
    role_type: str = Field(default="male_lead", description="剧本默认角色定位: female_lead / male_lead / antagonist_female / antagonist_male")
    summary: str = Field(default="", description="一句话人设定位")
    description: Optional[str] = Field(default="", description="详细人设描述 (向后兼容字段)")
    
    # 核心一致性控制卡
    consistency_card: CharacterConsistencyCard = Field(..., description="角色一致性物理特征锁 (五官骨相、发型发色、服饰装束、专属负向词与参考图)")
    
    # 电影级 16:9 专业三视图生成提示词
    turnaround_prompt: str = Field(..., description="用于文生图/图生图生成纯白底 16:9 角色正/侧/背全身与胸像特写定妆三视图提示词")
    
    # 语音引擎推荐配置
    voice_binding: Dict[str, Any] = Field(default_factory=dict, description="Edge-TTS 推荐绑定配置 (voice_id, name, rate, pitch, prompt)")
    
    # 生图与视频控制参数
    generation_params: Dict[str, Any] = Field(default_factory=dict, description="生图与多模态参考参数 (aspect_ratio, turnaround_aspect_ratio, style_tags, cref_weight, ip_adapter_scale)")
    
    # 基础物理锚点 (兼容原有字段)
    visual_anchor: str = Field(default="", description="中文物理特征锚点")
    visual_tags: str = Field(default="", description="英文锁脸与外观Prompt")

    @model_validator(mode="before")
    @classmethod
    def sync_summary_and_description(cls, data: Any):
        if isinstance(data, dict):
            if "summary" in data and not data.get("description"):
                data["description"] = data["summary"]
            elif "description" in data and not data.get("summary"):
                data["summary"] = data["description"]
        return data

    @property
    def voice_name(self) -> str:
        """获取推荐 Edge-TTS 音色代号."""
        return self.voice_binding.get("voice_id", "zh-CN-YunxiNeural")

    @property
    def voice_rate(self) -> str:
        """获取语速微调偏移量 (如 '+2%')."""
        return self.voice_binding.get("rate", "+0%")

    @property
    def voice_pitch(self) -> str:
        """获取语调微调偏移量 (如 '-3Hz')."""
        return self.voice_binding.get("pitch", "+0Hz")

    @property
    def voice_prompt(self) -> str:
        """获取音色与情绪提示词."""
        return self.voice_binding.get("prompt", "")

    @property
    def recommended_params(self) -> Dict[str, Any]:
        """获取推荐生图参数 (兼容 PROJECT.md 接口)."""
        return self.generation_params


BUILTIN_ARCHETYPES: Dict[str, DramaArchetype] = {
    # -------------------------------------------------------------------------
    # 04 现代女主-都市丽人
    # -------------------------------------------------------------------------
    "04_modern_female_urban": DramaArchetype(
        id="04_modern_female_urban",
        code="04",
        name="现代女主-都市丽人",
        genre_category="现代都市 / 职场言情 / 双强商战",
        gender="female",
        role_type="female_lead",
        summary="26岁职场精英独立女性，坚韧知性、从容优雅、清冷干练，不依附于人的当代大女主。",
        consistency_card=CharacterConsistencyCard(
            facial_lock=(
                "delicate Asian oval face structure with taut defined jawline, subtle high cheekbones, "
                "refined almond eyes with natural hooded double eyelids, clear sharp confident gaze, "
                "straight slender nasal bridge with delicately rounded tip, well-defined cupid's bow "
                "on natural rose-nude moisturized lips, authentic Asian cool-fair skin texture with visible "
                "micro pores, high-end editorial cosmetics"
            ),
            hair_lock=(
                "effortless French-style clavicle-grazing wavy lob haircut, airy natural volume at crown, "
                "elegant side-swept bangs framing cheekbones, silky flowing hair strands with healthy natural "
                "sheen, deep cold espresso brunette hair color"
            ),
            costume_lock=(
                "bespoke tailored oatmeal-white double-breasted fine-wool blazer with sharp structured shoulder "
                "silhouette, champagne-colored silk satin inner camisole, high-waisted fluid draped trousers, "
                "pointed-toe nude leather pumps, minimalist 18k white-gold baroque pearl pendant necklace, "
                "delicate matching pearl stud earrings, slim vintage rectangular leather-strap dress watch"
            ),
            exclusive_negative_prompt=(
                "childish round face, chubby cheeks, aegyo-sal, heavy artificial fake eyelashes, exaggerated "
                "eyeliner, cheap glitter, neon lipstick, plastic surgery chin, anime big eyes, clumsy posture, "
                "cheap shiny polyester, wrinkled suit, gaudy neon colors, revealing clubbing outfit, messy "
                "frizzy hair, doll face, 3d render, CGI wax figure"
            ),
            reference_images=[],
        ),
        turnaround_prompt=(
            "Character model turnaround sheet of a 26-year-old Chinese modern urban chic female protagonist, "
            "displayed on a pure plain white cyclorama studio background. Three full-body standing views: "
            "front view, 90-degree side profile view, and 180-degree rear view horizontally aligned with identical "
            "eye line and precise human anatomical proportions. In front view: perfectly upright poised stance, "
            "facing directly at camera, tailored oatmeal-white double-breasted blazer buttoned at waist, champagne "
            "silk camisole visible at lapels, high-waisted tailored trousers falling straight to shoes. In 90-degree "
            "side profile view: facing right edge of canvas, clean sharp jawline, upright elegant neck posture, "
            "clavicle-length wavy hair drape. In 180-degree rear view: smooth back tailoring seams of the wool blazer, "
            "natural fall of wavy brunette hair down upper back, back trousers silhouette. Left quadrant includes "
            "an ultra-detailed close-up head-and-shoulders bust portrait as facial baseline: almond-shaped confident "
            "eyes, defined cupid's bow, cool fair skin with microscopic pores. Photographed with 85mm portrait prime "
            "lens, soft diffused directional studio strobe lighting, crisp white background, 8k resolution, authentic "
            "live-action cinematography, zero cartoon, zero anime, proportions strictly preserved."
        ),
        voice_binding={
            "voice_id": "zh-CN-XiaoxiaoNeural",
            "name": "晓晓 (知性独立女声)",
            "rate": "+2%",
            "pitch": "+0Hz",
            "prompt": "冷静从容、知性干练、吐字清晰、尾音干净不拖沓的青年都市女性音色",
            "backup_voice_id": "zh-CN-XiaohanNeural",
        },
        generation_params={
            "aspect_ratio": "9:16",
            "turnaround_aspect_ratio": "16:9",
            "style_tags": (
                "cinematic realism, ARRI Alexa 65 film capture, 35mm anamorphic lens, master cinematography, "
                "authentic Chinese actress, editorial high-fashion realism, photorealistic skin pores, 8k masterpiece"
            ),
            "cref_weight": 85,
            "ip_adapter_scale": 0.85,
        },
        visual_anchor="鹅蛋骨相脸，清澈坚定的杏仁明眸，及肩法式微卷冷茶黑发，身着定制燕麦白双排扣精纺西装配香槟真丝吊带与高腰垂感阔腿裤，冷白皮质感",
        visual_tags=(
            "photorealistic Chinese actress, 26 years old, delicate oval face, refined almond eyes, "
            "clavicle wavy espresso hair, tailored oatmeal-white blazer, champagne silk inner camisole, "
            "8k cinema movie still, authentic skin pores, dramatic film lighting, no cartoon, no anime"
        ),
    ),

    # -------------------------------------------------------------------------
    # 05 现代男主-霸总
    # -------------------------------------------------------------------------
    "05_modern_male_boss": DramaArchetype(
        id="05_modern_male_boss",
        code="05",
        name="现代男主-霸总",
        genre_category="现代都市 / 豪门商战 / 契约婚姻 / 战神回归",
        gender="male",
        role_type="male_lead",
        summary="30岁顶级财阀掌控者，深沉内敛、气场迫人、杀伐果断，眼神自带上位者压迫感与禁欲力量。",
        consistency_card=CharacterConsistencyCard(
            facial_lock=(
                "sculpted masculine Chinese jawline with razor-sharp angular mandibles, high prominent cheekbones "
                "and brow ridge, deep-set piercing narrow hooded eyes, sharp commanding gaze, tall straight "
                "aquiline nose with defined bridge, thin sculpted lips set in a stern resolute line, natural "
                "healthy Asian male fair skin with realistic pore texture, subtle faint shadow of stubble along "
                "clean jawline"
            ),
            hair_lock=(
                "modern textured slicked-back side-part hairstyle with clean tapered fade at temples and nape, "
                "one subtle loose textured strand naturally falling across forehead, jet black hair with natural "
                "matte finish"
            ),
            costume_lock=(
                "bespoke midnight-navy three-piece tailored suit in fine wool-cashmere blend, broad peak lapels, "
                "tailored waistcoat, crisp spread-collar Egyptian cotton white dress shirt, dark charcoal silk "
                "jacquard necktie, subtle platinum lapel pin, black onyx and silver cufflinks, luxury dark-dial "
                "mechanical chronometer watch, polished black calfskin oxford shoes"
            ),
            exclusive_negative_prompt=(
                "boyish baby face, chubby rounded cheeks, effeminate features, silly grin, goofy expression, "
                "casual messy unwashed hair, loose baggy hoodie, cheap shiny polyester, wrinkled suit, colorful "
                "gaudy ties, gold chain gangster jewelry, anime aesthetics, doll eyes, smooth plastic skin, "
                "3d render, CGI figure"
            ),
            reference_images=[],
        ),
        turnaround_prompt=(
            "Character model turnaround sheet of a 30-year-old imposing Chinese corporate tycoon male protagonist "
            "on a seamless pure white studio background. Three full-body standing views: front view, 90-degree side "
            "profile view, and 180-degree rear view horizontally aligned with consistent 186cm athletic build and identical "
            "eye level. In front view: authoritative commanding posture, standing upright with one hand casually hooked "
            "in suit trouser pocket and the other relaxed at side, wearing a bespoke midnight-navy three-piece suit, "
            "peak lapels, white collared shirt, dark silk tie, tailored trousers, and polished black leather oxfords. "
            "In 90-degree side profile view: facing right canvas edge, razor-sharp jawline contour, prominent nose bridge, "
            "tall upright spine, broad shoulders. In 180-degree rear view: broad athletic back, impeccably fitted suit seams "
            "tapering into waist, neat hair taper at nape. Left quadrant features an intense close-up portrait: piercing "
            "hooded eyes, sword eyebrows, authoritative cold composure, photorealistic skin pores and natural micro-stubble. "
            "Shot on 85mm prime lens, cinematic rim lighting with soft directional fill, plain white cyclorama backdrop, "
            "8k resolution, blockbuster film still realism, zero cartoon, proportions strictly preserved."
        ),
        voice_binding={
            "voice_id": "zh-CN-YunxiNeural",
            "name": "云希 (磁性霸总男声)",
            "rate": "-4%",
            "pitch": "-3Hz",
            "prompt": "低沉浑厚、磁性从容、隐忍克制中透出压迫感与上位者气魄的青年男声",
            "backup_voice_id": "zh-CN-YunzeNeural",
        },
        generation_params={
            "aspect_ratio": "9:16",
            "turnaround_aspect_ratio": "16:9",
            "style_tags": (
                "cinematic chiaroscuro, ARRI Alexa LF, Panavision 50mm anamorphic lens, blockbuster film lighting, "
                "photorealistic Chinese male actor, corporate drama still, high-contrast atmospheric tone, 8k masterpiece"
            ),
            "cref_weight": 90,
            "ip_adapter_scale": 0.90,
        },
        visual_anchor="刀削般冷峻下颌线，深邃如鹰隼的丹凤眼与剑眉，利落侧背大背头，身着定制午夜深蓝三件套西装配真丝领带与机械腕表，气场强大沉稳",
        visual_tags=(
            "photorealistic Chinese actor, 30 years old, sharp angular jawline, commanding eyes, sword eyebrows, "
            "textured slick-back black hair, bespoke midnight-navy three-piece suit, 8k cinema movie still, "
            "authentic skin pores, dramatic film lighting, no cartoon, no anime"
        ),
    ),

    # -------------------------------------------------------------------------
    # 06 古装男主-清冷世子
    # -------------------------------------------------------------------------
    "06_ancient_male_noble": DramaArchetype(
        id="06_ancient_male_noble",
        code="06",
        name="古装男主-清冷世子",
        genre_category="古风权谋 / 仙侠修真 / 宫廷争斗 / 江湖武侠",
        gender="male",
        role_type="male_lead",
        summary="22岁王府世子与仙门贵胄，清冷孤傲、出尘绝俗、心怀苍生而拒人千里，高岭之花。",
        consistency_card=CharacterConsistencyCard(
            facial_lock=(
                "slender aristocratic classical Chinese oval face, clean defined aesthetic jawline, smooth noble "
                "forehead, finely arched calligraphic black eyebrows extending toward temples, elongated phoenix "
                "eyes with aloof transcendent gaze, straight slender high nose bridge, delicate thin pale-rose "
                "lips with natural contour, flawless porcelain-fair translucent skin like cold nephrite jade "
                "with subtle realistic texture"
            ),
            hair_lock=(
                "traditional ancient Chinese half-up high topknot hairstyle with flowing waist-length silk-black "
                "hair cascading down back, secured by a carved white jade crown and silver hairpin, two delicate "
                "thin flowing wisps of hair framing jawline gracefully in the breeze, deep raven ink-black hair"
            ),
            costume_lock=(
                "multi-layered moonlight-white silk flowing Hanfu robes with wide dramatic sleeves, draped outer "
                "gossamer translucent silver-embroidered cloak, subtle silver metallic bamboo leaf and cloud patterns "
                "embroidered along lapels and cuffs, wide silver-embroidered sash belt with carved mutton-fat white "
                "jade pendant and blue silk tassels hanging at waist, white silk embroidered martial boots, holding "
                "a closed bamboo folding fan"
            ),
            exclusive_negative_prompt=(
                "modern clothing, modern hairstyle, short hair, plastic lace wig mesh, western facial features, "
                "heavy beard, mustache, rough rugged warrior face, casual modern shoes, bright cheap nylon costume, "
                "neon colors, western armor, medieval knight, 3d video game render, low polygon model, cartoon, "
                "anime illustration"
            ),
            reference_images=[],
        ),
        turnaround_prompt=(
            "Character model turnaround sheet of an ethereal 22-year-old Chinese ancient noble prince (世子) on a "
            "plain pure white studio background. Three full-body standing views: front view, 90-degree side profile view, "
            "and 180-degree rear view horizontally aligned with matching proportions, 182cm slender noble posture, "
            "and consistent eye level. In front view: upright poised noble stance holding a closed bamboo folding fan "
            "gently at waist, multi-layered flowing moonlight-white silk Hanfu, silver bamboo-leaf embroidery along cuffs, "
            "wide embroidered sash with hanging white jade tassel pendant. In 90-degree side profile view: facing right "
            "edge of canvas, aristocratic slender profile, high jade topknot with silver hairpin, long raven-black hair "
            "cascading down the spine, sweeping wide sleeve silhouette. In 180-degree rear view: long silk-black hair falling "
            "straight past waist, translucent outer gossamer cloak draping over robes, hem of sweeping gown. Left quadrant "
            "features a transcendent close-up bust portrait: clear distant phoenix eyes, pale jade-like skin, delicate "
            "arched brows, serene detached noble expression. Photographed with 85mm portrait prime lens, soft cool diffused "
            "studio illumination, seamless white backdrop, 8k resolution, masterpiece historical cinema realism, zero "
            "cartoon, proportions strictly preserved."
        ),
        voice_binding={
            "voice_id": "zh-CN-YunjianNeural",
            "name": "云健 (清冷孤傲男声)",
            "rate": "-2%",
            "pitch": "+1Hz",
            "prompt": "嗓音清冽如碎玉击泉、平稳淡然、不带人间烟火气与凡俗情绪的东方清冷贵胄男声",
            "backup_voice_id": "zh-CN-YunxiNeural",
        },
        generation_params={
            "aspect_ratio": "9:16",
            "turnaround_aspect_ratio": "16:9",
            "style_tags": (
                "traditional Chinese costume drama still, cinematic Wuxia aesthetic, ARRI Alexa LF, 50mm Cooke "
                "anamorphic lens, soft ethereal mist, photorealistic Chinese actor, masterwork costume design, "
                "elegant ancient oriental atmosphere, 8k masterpiece"
            ),
            "cref_weight": 85,
            "ip_adapter_scale": 0.85,
        },
        visual_anchor="古典清贵骨相，淡漠修长的丹凤眸，半束高玉冠墨黑及腰长发，身着月白双层真丝暗纹交领汉服大袖长袍，罩半透明银丝云雾绡大氅，配白玉带钩流苏佩，气韵出尘冷冽",
        visual_tags=(
            "photorealistic Chinese actor, 22 years old, slender aristocratic face, elongated cool phoenix eyes, "
            "ancient Chinese Hanfu half-up topknot with white jade crown, moonlight-white embroidered silk robes, "
            "gossamer cloak, 8k cinema movie still, authentic skin texture, dramatic film lighting, no cartoon, no anime"
        ),
    ),

    # -------------------------------------------------------------------------
    # 08 反派女二-绿茶千金
    # -------------------------------------------------------------------------
    "08_antagonist_female_greentea": DramaArchetype(
        id="08_antagonist_female_greentea",
        code="08",
        name="反派女二-绿茶千金",
        genre_category="现代豪门 / 真假千金 / 都市言情 / 宅斗逆袭",
        gender="female",
        role_type="antagonist_female",
        summary="23岁心机富家千金，表面天真无邪、柔弱无辜、楚楚可怜，实则暗藏机心、挑拨离间的高阶绿茶反派。",
        consistency_card=CharacterConsistencyCard(
            facial_lock=(
                "delicate youthful heart-shaped Asian face with soft rounded cheeks tapering to a petite pointed chin, "
                "wide innocent round almond eyes with natural dewy aegyo-sal, subtly downturned outer eye corners "
                "creating a vulnerable tearful look, petite upturned nose tip with narrow bridge, glossy peach-pink "
                "pouty cherry lips with dewy lacquer shine, translucent peachy-fair porcelain skin with natural "
                "soft pink blush on cheeks"
            ),
            hair_lock=(
                "luxurious half-up half-down princess hairstyle with cascading soft mermaid waves, high-crown volume, "
                "delicate curled tendrils gently framing temples and neck, accessorized with a dainty micro-pavé "
                "crystal bow hair clip, warm honey-tea brown hair color with soft glossy salon luster"
            ),
            costume_lock=(
                "bespoke pastel baby-pink and cream French tweed cropped tailored jacket with pearl buttons and "
                "delicate fringe trim, cream-white ruffled chiffon high-neck inner blouse, matching high-waisted "
                "pleated tweed mini skirt, sheer stockings, nude beige patent-leather Mary Jane heels, dainty rose-gold "
                "mother-of-pearl clover pendant necklace, mini pastel pink quilted leather chain handbag"
            ),
            exclusive_negative_prompt=(
                "overt villain evil smirk, heavy gothic makeup, dark black eyeshadow, aggressive masculine features, "
                "mature aged face, wrinkles, deep nasolabial folds, flat chest, messy unwashed hair, casual baggy "
                "t-shirt, athletic sportswear, cheap dirty clothing, doll eyes, cartoon, anime, 3d render"
            ),
            reference_images=[],
        ),
        turnaround_prompt=(
            "Character model turnaround sheet of a 23-year-old deceptively innocent Chinese wealthy heiress "
            "antagonist on a plain pure white studio background. Three full-body standing views: front view, 90-degree "
            "side profile view, and 180-degree rear view horizontally aligned with matching proportions, 165cm slender "
            "petite frame, and identical eye level. In front view: demure innocent posture with feet angled slightly "
            "inward, hands gently clasping a pastel pink mini handbag in front of her, dressed in tailored pastel baby-pink "
            "tweed cropped jacket with pearl buttons, cream ruffled lace inner blouse, matching pleated tweed A-line skirt, "
            "and low-heel Mary Jane pumps. In 90-degree side profile view: facing right canvas edge, subtle playful tilt "
            "of the head, delicate upturned nose profile, elegant arch of the spine, cascading soft wavy brown curls falling "
            "past shoulders. In 180-degree rear view: clean tailored seams of the tweed jacket, half-up princess hair "
            "secured with a dainty ribbon bow clip, soft pleated skirt hem. Left quadrant features an ultra-detailed "
            "close-up bust portrait: doe-like dewy round eyes with tearful innocence, glossy pink cherry lips, soft blush, "
            "intricate skin texture with natural pores. Photographed with 85mm portrait prime lens, high-key soft beauty "
            "studio illumination, seamless white background, 8k resolution, crisp photorealistic detail, zero cartoon, "
            "proportions strictly preserved."
        ),
        voice_binding={
            "voice_id": "zh-CN-XiaoyiNeural",
            "name": "晓伊 (娇嗲千金女声)",
            "rate": "+4%",
            "pitch": "+3Hz",
            "prompt": "娇嗲轻柔、尾音微扬带撒娇感，听似楚楚动人无辜可怜，实则机敏多变的年轻富家女二音色",
            "backup_voice_id": "zh-CN-XiaoxiaoNeural",
        },
        generation_params={
            "aspect_ratio": "9:16",
            "turnaround_aspect_ratio": "16:9",
            "style_tags": (
                "cinematic drama still, ARRI Alexa Mini LF, Zeiss Supreme Prime 50mm lens, glamorous romantic lighting, "
                "soft pastel color grading, photorealistic Chinese actress, high society melodrama aesthetic, 8k masterpiece"
            ),
            "cref_weight": 85,
            "ip_adapter_scale": 0.85,
        },
        visual_anchor="精致心形脸，水汪汪圆杏眼配无辜卧蚕，微翘水光蜜桃唇，半扎公主头波浪微卷蜂蜜茶色长发戴水钻发夹，身着小香风淡粉粗花呢收腰套装配珍珠扣与百褶短裙，透着娇弱与机心",
        visual_tags=(
            "photorealistic Chinese actress, 23 years old, heart-shaped face, innocent dewy round eyes with aegyo-sal, "
            "honey-tea wavy hair with crystal bow, pastel pink tweed jacket and skirt, pearl buttons, "
            "8k cinema movie still, authentic skin pores, glamorous romantic lighting, no cartoon, no anime"
        ),
    ),
}


# =============================================================================
# 核心业务接口函数 (Core Archetype APIs)
# =============================================================================

def list_archetypes() -> List[Dict[str, Any]]:
    """获取所有内置母版的轻量级列表（供 Web 监视器与 Android 原生端 UI 下拉展示与选择）.
    
    Returns:
        List[Dict[str, Any]]: 包含各母版关键元数据（id, code, name, gender, role_type, summary, voice 等）的字典列表
    """
    results: List[Dict[str, Any]] = []
    # 按照代号排序，确保界面顺序稳定
    sorted_archetypes = sorted(BUILTIN_ARCHETYPES.values(), key=lambda a: a.code)
    for arch in sorted_archetypes:
        results.append({
            "id": arch.id,
            "code": arch.code,
            "name": arch.name,
            "gender": arch.gender,
            "role_type": arch.role_type,
            "genre_category": arch.genre_category,
            "summary": arch.summary,
            "description": arch.description or arch.summary,
            "voice_name": arch.voice_name,
            "voice_rate": arch.voice_rate,
            "voice_pitch": arch.voice_pitch,
            "voice_display": arch.voice_binding.get("name", "默认音色"),
            "voice_prompt": arch.voice_prompt,
            "visual_anchor": arch.visual_anchor,
            "aspect_ratio": arch.generation_params.get("aspect_ratio", "9:16"),
            "turnaround_aspect_ratio": arch.generation_params.get("turnaround_aspect_ratio", "16:9"),
        })
    return results


def get_archetype(archetype_id_or_code: str) -> Optional[DramaArchetype]:
    """根据母版全局 ID（如 '04_modern_female_urban'）、短代号前缀（如 '04'）或中文名精确/前缀检索母版.

    Args:
        archetype_id_or_code: 母版标识或代号

    Returns:
        Optional[DramaArchetype]: 匹配的母版对象，若无匹配则返回 None
    """
    if not archetype_id_or_code:
        return None

    cleaned = str(archetype_id_or_code).strip()
    if not cleaned:
        return None

    # 1. 精确全局 ID 匹配
    if cleaned in BUILTIN_ARCHETYPES:
        return BUILTIN_ARCHETYPES[cleaned]

    # 2. 区分大小写不敏感匹配
    cleaned_lower = cleaned.lower()
    for arch_id, arch in BUILTIN_ARCHETYPES.items():
        if arch_id.lower() == cleaned_lower:
            return arch

    # 3. 按两数字/短代号匹配 (如 "04", "05", "06", "08")
    for arch in BUILTIN_ARCHETYPES.values():
        if arch.code == cleaned or arch.code.lstrip("0") == cleaned.lstrip("0"):
            return arch

    # 4. 按名称匹配 (精确匹配或有效中文子串)
    for arch in BUILTIN_ARCHETYPES.values():
        if arch.name == cleaned:
            return arch
    if len(cleaned) >= 2:
        for arch in BUILTIN_ARCHETYPES.values():
            if cleaned in arch.name:
                return arch

    return None


def apply_archetype_to_character(
    character: CharacterAsset,
    archetype_id: str,
    custom_name: Optional[str] = None
) -> CharacterAsset:
    """将指定母版的外观锁、发型锁、服饰锁、三视图提示词、Edge-TTS 声音及参数一键套用至已有 CharacterAsset.

    Args:
        character: 已有角色资产对象
        archetype_id: 母版 ID 或代号
        custom_name: 可选自定义角色名，若提供则重命名，否则保留原有 character.name

    Returns:
        CharacterAsset: 套用母版特征后的角色资产对象

    Raises:
        ValueError: 当指定母版不存在时抛出
    """
    arch = get_archetype(archetype_id)
    if not arch:
        raise ValueError(f"未找到人设母版: {archetype_id}")

    char_name = custom_name.strip() if custom_name and custom_name.strip() else character.name
    character.name = char_name
    character.gender = arch.gender
    character.archetype = arch.id
    character.visual_anchor = arch.visual_anchor
    character.visual_tags = arch.visual_tags
    character.voice_name = arch.voice_name
    character.voice_prompt = arch.voice_prompt
    character.turnaround_prompt = arch.turnaround_prompt
    
    # 深度拷贝一致性卡，避免多个角色实例共享引用导致属性污染
    character.consistency_card = arch.consistency_card.model_copy(deep=True)

    # 增量注入母版人设背景说明
    bio_tag = f"【人设母版: {arch.name}】{arch.summary}"
    if not character.bio:
        character.bio = bio_tag
    elif bio_tag not in character.bio:
        character.bio = f"{character.bio}\n{bio_tag}".strip()

    return character


def create_character_from_archetype(
    archetype_id: str,
    character_name: Optional[str] = None,
    **kwargs: Any
) -> CharacterAsset:
    """工厂函数: 直接根据母版 ID 实例化全新的专业电影级 CharacterAsset.

    Args:
        archetype_id: 母版 ID 或短代号 (如 '04_modern_female_urban' 或 '04')
        character_name: 角色自定义姓名，未指定时默认使用母版末尾职能名称 (如 '都市丽人')
        **kwargs: 额外自定义覆盖字段 (如 turnaround_image, custom_role, bio 等)

    Returns:
        CharacterAsset: 初始化的标准角色资产对象

    Raises:
        ValueError: 当指定母版不存在时抛出
    """
    arch = get_archetype(archetype_id)
    if not arch:
        raise ValueError(f"未找到人设母版: {archetype_id}")

    if character_name and character_name.strip():
        name = character_name.strip()
    else:
        name = arch.name.split("-")[-1] if "-" in arch.name else arch.name

    turnaround_img = kwargs.get("turnaround_image") or ""
    bio_val = f"【母版原型: {arch.name}】{arch.summary}"
    if kwargs.get("custom_role"):
        bio_val = f"{kwargs['custom_role']}。{bio_val}"
    if kwargs.get("bio"):
        bio_val = f"{kwargs['bio']}\n{bio_val}"

    return CharacterAsset(
        name=name,
        gender=kwargs.get("gender") or arch.gender,
        visual_tags=kwargs.get("visual_tags") or arch.visual_tags,
        voice_name=kwargs.get("voice_name") or arch.voice_name,
        bio=bio_val,
        visual_anchor=kwargs.get("visual_anchor") or arch.visual_anchor,
        voice_prompt=kwargs.get("voice_prompt") or arch.voice_prompt,
        archetype=arch.id,
        turnaround_prompt=kwargs.get("turnaround_prompt") or arch.turnaround_prompt,
        turnaround_image=turnaround_img,
        consistency_card=kwargs.get("consistency_card") or arch.consistency_card.model_copy(deep=True),
    )


def compile_character_consistency_prompt(
    character: CharacterAsset,
    shot_scale: Union[str, ShotScaleEnum] = "medium_shot",
    emotion_action: str = ""
) -> Tuple[str, str]:
    """为角色编译单镜头专业电影级强锁定正向提示词与专属防崩负向词.

    按照电影级工业流水线拼装规范：
    - 正向提示词: 【ARRI Alexa 65 电影机画质】 + 【景别】 + 【角色演员】 + 【骨相五官锁 + 发型发色锁 + 服饰装束锁】 + 【情绪与肢体动作】 + 【真实皮肤质感与胶片颗粒】
    - 负向提示词: 【通用防崩词库 (no cartoon/anime/3d render)】 + 【角色专属防崩排异词】

    Args:
        character: 角色资产对象
        shot_scale: 镜头景别 (支持 ShotScaleEnum 或字符串如 'medium_shot', 'close_up')
        emotion_action: 本分镜的角色情绪、微表情与物理动作描述

    Returns:
        Tuple[str, str]: (positive_prompt, negative_prompt)
    """
    card = character.consistency_card
    if card and (card.facial_lock or card.hair_lock or card.costume_lock):
        locks = [l.strip() for l in [card.facial_lock, card.hair_lock, card.costume_lock] if l and l.strip()]
        lock_chunk = ", ".join(locks)
        exclusive_neg = card.exclusive_negative_prompt.strip() if card.exclusive_negative_prompt else ""
    else:
        lock_chunk = (character.visual_tags or character.visual_anchor or "").strip()
        exclusive_neg = ""

    # 解析与规范化景别描述
    if shot_scale is None:
        scale_desc = "medium shot"
    elif hasattr(shot_scale, "value"):
        scale_val = str(shot_scale.value).replace("_", " ").strip()
        scale_desc = scale_val if scale_val and scale_val.lower() != "none" else "medium shot"
    else:
        scale_str = str(shot_scale).replace("_", " ").strip()
        scale_desc = scale_str if scale_str and scale_str.lower() != "none" else "medium shot"

    # 清洗角色名与动作描述中的换行符为单个空格
    safe_name = re.sub(r"[\r\n]+", " ", str(character.name)).strip() if character.name else ""
    safe_action = re.sub(r"[\r\n]+", " ", str(emotion_action)).strip() if emotion_action else ""

    actor_chunk = f"photorealistic Chinese actor playing {safe_name}" if safe_name else "photorealistic Chinese actor"

    segments = [
        "8k cinematic live-action movie still",
        "shot on ARRI Alexa 65",
        "35mm Panavision anamorphic lens",
        scale_desc,
        actor_chunk,
    ]
    if lock_chunk:
        segments.append(lock_chunk)
    if safe_action:
        segments.append(safe_action)
    segments.extend([
        "authentic facial skin texture",
        "subtle pores",
        "theatrical cinema lighting",
        "35mm film grain",
        "blockbuster cinematography",
        "masterpiece",
        "vertical 9:16",
    ])

    positive_prompt = ", ".join(segments)

    universal_negative = (
        "cartoon, anime, 3d render, CGI, bad anatomy, deformed hands, extra limbs, blurry, low resolution, poorly drawn face"
    )
    if exclusive_neg:
        clean_exclusive = re.sub(r"[\r\n]+", " ", exclusive_neg).strip()
        full_negative = f"{universal_negative}, {clean_exclusive}"
    else:
        full_negative = universal_negative

    return positive_prompt, full_negative


# 兼容性别名
compile_consistency_prompt = compile_character_consistency_prompt
