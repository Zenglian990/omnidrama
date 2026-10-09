"""测试 OmniDrama 多剧集连载管理器与小说智能切集算法."""
import os
import pytest
from omnidrama.core.series_manager import SeriesManager


def test_series_manager_init(tmp_path):
    mgr = SeriesManager(data_dir=str(tmp_path))
    reg = mgr.get_registry()
    assert "series" in reg
    assert len(reg["series"]) >= 1

    series = mgr.get_series(reg["active_series_id"])
    assert series is not None
    assert len(series["episodes"]) >= 1


def test_series_manager_add_episode(tmp_path):
    mgr = SeriesManager(data_dir=str(tmp_path))
    reg = mgr.get_registry()
    s_id = reg["active_series_id"]

    new_ep = mgr.add_episode(s_id, "逆鳞反噬", "剧情正文内容")
    assert new_ep["episode_num"] == 4
    assert "逆鳞反噬" in new_ep["title"]

    updated = mgr.get_series(s_id)
    assert len(updated["episodes"]) == 4


def test_auto_split_novel(tmp_path):
    mgr = SeriesManager(data_dir=str(tmp_path))
    novel = """
第一章 龙王退隐
北境风雪连天，叶辰卸下战铠，悄然回归江城。

第二章 林家入赘
三年蛰伏，林家大堂上，岳母将茶杯摔得粉碎。

第三章 战神再临
大门轰然碎裂，十万修罗战神齐声高呼：恭迎龙王！
"""
    eps = mgr.auto_split_novel(novel)
    assert len(eps) == 3
    assert "第一章" in eps[0]["title"]
    assert "第二章" in eps[1]["title"]
    assert "第三章" in eps[2]["title"]
