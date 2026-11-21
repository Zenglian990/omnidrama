import pytest
from omnidrama.core.director import DirectorAgent
from omnidrama.schemas.drama_schema import DramaProject, ShotScaleEnum, CameraMotionEnum

def test_offline_director_breakdown():
    director = DirectorAgent()
    sample_text = """
    【第1幕：龙王归来】
    三年之期已到，叶辰站在苏家大院门前，眼神冷冽如刀。
    叶辰：“今日我重返江城，谁敢动我妹妹分毫，我便灭谁满门！”
    反派赵公子狂妄大笑：“哈哈哈！就凭你这个丧家之犬，也敢口出狂言？”
    瞬间，天际雷霆炸裂，无数黑衣修罗从天而降，齐声高呼：“恭迎龙王回归！”
    """
    project = director.breakdown_story_offline(sample_text, title="龙王赘婿逆袭记", genre="都市战神爽文")

    assert isinstance(project, DramaProject)
    assert project.title == "龙王赘婿逆袭记"
    assert len(project.characters) >= 2
    assert len(project.shots) >= 4
    
    # 验证镜头属性合规性
    for shot in project.shots:
        assert isinstance(shot.shot_scale, ShotScaleEnum)
        assert isinstance(shot.camera_motion, CameraMotionEnum)
        assert len(shot.visual_prompt) > 0
        assert len(shot.dialogue) > 0
