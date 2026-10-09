package com.omnidrama.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.ShotItem
import com.omnidrama.app.ui.theme.*

data class DramaPreset(
    val title: String,
    val genre: String,
    val synopsis: String,
    val episodeCount: Int,
    val characters: List<CharacterItem>,
    val shots: List<ShotItem>
)

@Composable
fun DramaSwitcherDialog(
    currentTitle: String,
    onSelectDrama: (ProjectData) -> Unit,
    onCreateNew: () -> Unit,
    onDismiss: () -> Unit
) {
    val presets = listOf(
        DramaPreset(
            title = "至尊龙王归位",
            genre = "都市战神爽文",
            synopsis = "入赘三年受尽欺凌，逆鳞触动之日，十万修罗战神破门叩首！",
            episodeCount = 10,
            characters = listOf(
                CharacterItem("叶辰 (主角)", "至尊龙王", "云希 (磁性沉稳霸道)", "/output/至尊龙王归位/shots/shot_004.jpg", "黑发冷眸，修罗战神之主，隐藏滔天权势"),
                CharacterItem("林清雪 (千金女帝)", "豪门白月光女主", "晓涵 (温柔清纯甜美)", "/output/至尊龙王归位/shots/shot_002.jpg", "清冷绝美，白裙若仙，商业天才"),
                CharacterItem("岳母柳琴", "刁难反派", "晓晓 (尖酸刻薄逼迫)", "/output/至尊龙王归位/shots/shot_002.jpg", "翡翠旗袍，拜金势力，豪门大堂"),
                CharacterItem("赵公子", "狂妄对手", "云健 (嚣张跋扈)", "/output/至尊龙王归位/shots/shot_005.jpg", "定制西装，手持红酒，自傲恶少")
            ),
            shots = listOf(
                ShotItem(1, "旁白", "WIDE_SHOT", "ZOOM_IN", "镜头推进", "林家祖宅大堂，狂风骤雨拍打着雕花木窗。", "/output/至尊龙王归位/shots/shot_001.jpg", "/output/至尊龙王归位/shots/shot_001.mp3", "暴雨环境音"),
                ShotItem(2, "岳母柳琴", "MEDIUM_SHOT", "PAN_LEFT", "向左横移", "叶辰，入赘三年，今日若拿不出三千万，就立刻滚出林家！", "/output/至尊龙王归位/shots/shot_002.jpg", "/output/至尊龙王归位/shots/shot_002.mp3", "无"),
                ShotItem(3, "旁白", "CLOSE_UP", "ZOOM_IN", "镜头推进", "叶辰神色淡然，深邃的双眸中隐现寒光。", "/output/至尊龙王归位/shots/shot_003.jpg", "/output/至尊龙王归位/shots/shot_003.mp3", "无"),
                ShotItem(4, "叶辰", "CLOSE_UP", "ZOOM_IN", "镜头推进", "三千万？当年若非我暗中相助，林家早在三年前就已灰飞烟灭！", "/output/至尊龙王归位/shots/shot_004.jpg", "/output/至尊龙王归位/shots/shot_004.mp3", "疾风起势 (Whoosh)"),
                ShotItem(5, "赵公子", "MEDIUM_SHOT", "ZOOM_OUT", "镜头拉远", "哈哈哈！大言不惭的废物，也不撒泡尿照照自己是个什么东西！", "/output/至尊龙王归位/shots/shot_005.jpg", "/output/至尊龙王归位/shots/shot_005.mp3", "无"),
                ShotItem(6, "旁白", "FULL_SHOT", "SHAKE", "镜头震撼", "突然，天地间惊雷滚滚，整座大堂剧烈震颤！", "/output/至尊龙王归位/shots/shot_006.jpg", "/output/至尊龙王归位/shots/shot_006.mp3", "惊雷劈裂 (Thunder)"),
                ShotItem(7, "旁白", "FULL_SHOT", "ZOOM_OUT", "镜头拉远", "大门轰然破碎，十八位身披黑金战铠的修罗战神破门而入！", "/output/至尊龙王归位/shots/shot_007.jpg", "/output/至尊龙王归位/shots/shot_007.mp3", "重低音轰鸣 (Impact)"),
                ShotItem(8, "修罗战神", "CLOSE_UP", "ZOOM_IN", "镜头推进", "恭迎龙王回归！十万修罗殿众将，随时听候调遣！", "/output/至尊龙王归位/shots/shot_008.jpg", "/output/至尊龙王归位/shots/shot_008.mp3", "金铁下跪 (Armor)"),
                ShotItem(9, "岳母与赵公子", "MEDIUM_SHOT", "SHAKE", "镜头震撼", "龙……龙王？！你竟然是那位镇守北境的至尊龙王！", "/output/至尊龙王归位/shots/shot_009.jpg", "/output/至尊龙王归位/shots/shot_009.mp3", "无"),
                ShotItem(10, "叶辰", "EXTREME_CLOSE_UP", "ZOOM_IN", "镜头推进", "犯我逆鳞者，杀无赦！", "/output/至尊龙王归位/shots/shot_010.jpg", "/output/至尊龙王归位/shots/shot_010.mp3", "终极大爆炸 (Impact)")
            )
        ),
        DramaPreset(
            title = "真千金归来杀疯豪门",
            genre = "现代豪门复仇",
            synopsis = "被掉包流落乡下二十年，真千金强势回归，千亿财团听其号令！",
            episodeCount = 8,
            characters = listOf(
                CharacterItem("林清雪 (女主角)", "千亿继承人", "晓梦 (傲娇泼辣独立)", "", "银发蓝眸，冷艳绝尘，身着黑色修身风衣，气场强大"),
                CharacterItem("假千金林若薇", "心机反派", "晓晓 (尖酸刻薄逼迫)", "", "珠光宝气，眼神嫉妒，楚楚可怜却心肠歹毒"),
                CharacterItem("顾北宸", "护妻霸总", "云希 (磁性沉稳霸道)", "", "顶级财阀掌门人，深邃冷冽，唯对女主极致宠溺")
            ),
            shots = listOf(
                ShotItem(1, "旁白", "WIDE_SHOT", "ZOOM_IN", "镜头推进", "林氏庄园寿宴，万众瞩目，假千金挽着未婚夫接受全场恭维。", "", "", "轻柔小提琴"),
                ShotItem(2, "假千金林若薇", "MEDIUM_SHOT", "PAN_LEFT", "向左横移", "多谢各位捧场，我林若薇才是林家唯一的合法继承人！", "", "", "无"),
                ShotItem(3, "旁白", "FULL_SHOT", "ZOOM_OUT", "镜头拉远", "轰隆一声，宴会大门被十名黑衣保镖猛烈推开！", "", "", "重低音轰鸣 (Impact)"),
                ShotItem(4, "林清雪", "CLOSE_UP", "ZOOM_IN", "镜头推进", "林若薇，鸠占鹊巢二十年，也该把一切吐出来了！", "", "", "清脆高跟鞋声"),
                ShotItem(5, "顾北宸", "MEDIUM_SHOT", "ZOOM_IN", "镜头推进", "顾氏财团全权注资林清雪小姐，谁敢动她，便是与顾某为敌！", "", "", "全场倒吸凉气 (Gasp)")
            )
        ),
        DramaPreset(
            title = "修仙万载重回都市",
            genre = "玄幻仙尊爽剧",
            synopsis = "渡劫飞升失败重回少年时期，这一次，我要让诸天神佛皆臣服！",
            episodeCount = 12,
            characters = listOf(
                CharacterItem("萧凡 (男主角)", "无极仙尊", "云扬 (热血青年男主)", "", "白衣胜雪，剑眉星目，双眸若有日月星辰运转"),
                CharacterItem("江城首富王天霸", "投诚豪门", "云浩 (沉稳长辈/正剧)", "", "唐装老者，神情敬畏，双手奉上百亿资产"),
                CharacterItem("反派恶少陈飞", "无知顽少", "云健 (嚣张跋扈反派)", "", "黄毛耳钉，狂妄大笑，最终被一指镇压")
            ),
            shots = listOf(
                ShotItem(1, "旁白", "WIDE_SHOT", "ZOOM_OUT", "镜头拉远", "江城云顶天宫，漫天紫气东来三万里，雷霆汇聚于少年一人之身！", "", "", "天雷滚滚 (Thunder)"),
                ShotItem(2, "萧凡", "CLOSE_UP", "ZOOM_IN", "镜头推进", "重活一世，欠我的，都要千百倍奉还！", "", "", "剑鸣龙吟 (Sword)"),
                ShotItem(3, "王天霸", "MEDIUM_SHOT", "PAN_RIGHT", "向右横移", "江城王家，愿永世追随仙尊座下！", "", "", "金铁下跪 (Armor)"),
                ShotItem(4, "陈飞", "CLOSE_UP", "SHAKE", "镜头震撼", "装神弄鬼的穷学生，给我上，打断他的腿！", "", "", "急促脚步声"),
                ShotItem(5, "萧凡", "EXTREME_CLOSE_UP", "ZOOM_IN", "镜头推进", "蝼蚁之辈，也配向神明出手？跪下！", "", "", "大地轰鸣 (Impact)")
            )
        )
    )

    Dialog(onDismissRequest = onDismiss) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.85f)
                .clip(RoundedCornerShape(16.dp))
                .background(CardDark)
                .border(1.dp, BorderDark, RoundedCornerShape(16.dp))
                .padding(20.dp)
        ) {
            Column(modifier = Modifier.fillMaxSize()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "剧目管理与作品库",
                            color = TextPrimary,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "随时切换剧本、角色与镜头体系",
                            color = BrandCyan,
                            fontSize = 11.sp
                        )
                    }
                    IconButton(onClick = onDismiss) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // 创建全新剧本按钮
                Button(
                    onClick = {
                        onDismiss()
                        onCreateNew()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = AccentGold),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(imageVector = Icons.Default.Add, contentDescription = null, tint = BgDark, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("⚡ 导入小说 / 创作全新短剧", color = BgDark, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }

                Spacer(modifier = Modifier.height(14.dp))

                Text("选择已入库短剧:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(8.dp))

                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(presets) { p ->
                        val isCurrent = (p.title == currentTitle)
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(10.dp))
                                .background(if (isCurrent) BrandCyan.copy(alpha = 0.1f) else BgDark)
                                .border(
                                    width = if (isCurrent) 1.5.dp else 1.dp,
                                    color = if (isCurrent) BrandCyan else BorderDark,
                                    shape = RoundedCornerShape(10.dp)
                                )
                                .clickable {
                                    onSelectDrama(
                                        ProjectData(
                                            title = p.title,
                                            genre = p.genre,
                                            duration = p.shots.size * 6.0,
                                            characters = p.characters,
                                            shots = p.shots,
                                            video_url = if (p.title == "至尊龙王归位") "/output/至尊龙王归位/至尊龙王归位_影视级成片.mp4" else "",
                                            live_actor_video = if (p.title == "至尊龙王归位") "/output/至尊龙王归位/真人演员_叶辰_会说话.mp4" else ""
                                        )
                                    )
                                    onDismiss()
                                }
                                .padding(12.dp)
                        ) {
                            Column {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(
                                            text = "《${p.title}》",
                                            color = if (isCurrent) BrandCyan else TextPrimary,
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                        if (isCurrent) {
                                            Spacer(modifier = Modifier.width(6.dp))
                                            Box(
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(4.dp))
                                                    .background(BrandCyan)
                                                    .padding(horizontal = 4.dp, vertical = 1.dp)
                                            ) {
                                                Text("当前创作中", color = BgDark, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                                            }
                                        }
                                    }
                                    Text(
                                        text = p.genre,
                                        color = AccentGold,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = p.synopsis,
                                    color = TextMuted,
                                    fontSize = 11.sp,
                                    maxLines = 2
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Row {
                                    Text("包含 ${p.characters.size} 位角色 · ${p.shots.size} 个分镜镜头", color = TextSecondary, fontSize = 10.sp)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
