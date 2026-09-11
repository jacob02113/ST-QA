import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FILE = Path(__file__).resolve().parents[1] / "finetune" / "video_split.py"
SPEC = importlib.util.spec_from_file_location("video_split", FILE)
video_split = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(video_split)


def fake_clip(audio=None):
    clip = MagicMock()
    clip.audio = audio
    clip.__enter__.return_value = clip
    clip.__exit__.return_value = False
    clip.subclipped.return_value = MagicMock()
    return clip


def test_001():
    # 测试用例001：正常视频按起始时间切分
    row = {"video_name": "demo", "start-time/s": "1.5", "question_id": "q1"}
    clip = fake_clip()
    with patch.object(video_split, "VideoFileClip", return_value=clip):
        video_split.data_process(row, "videos")
    clip.subclipped.assert_called_once_with(0, 1.5)


def test_002():
    # 测试用例002：负起始时间被限制为最小值
    row = {"video_name": "demo", "start-time/s": "-2", "question_id": "q2"}
    clip = fake_clip()
    with patch.object(video_split, "VideoFileClip", return_value=clip):
        video_split.data_process(row, "videos")
    clip.subclipped.assert_called_once_with(0, 0.1)


def test_003():
    # 测试用例003：零起始时间被限制为最小值
    row = {"video_name": "demo", "start-time/s": "0", "question_id": "q3"}
    clip = fake_clip()
    with patch.object(video_split, "VideoFileClip", return_value=clip):
        video_split.data_process(row, "videos")
    clip.subclipped.assert_called_once_with(0, 0.1)


def test_004():
    # 测试用例004：带音频视频使用音频编码参数输出
    row = {"video_name": "demo", "start-time/s": "1", "question_id": "q4"}
    clip = fake_clip(audio=MagicMock())
    with patch.object(video_split, "VideoFileClip", return_value=clip):
        video_split.data_process(row, "videos")
    clip.subclipped.return_value.write_videofile.assert_called_once_with(
        "./video_clip/q4.mp4", codec="libx264", audio_codec="aac"
    )


def test_005():
    # 测试用例005：无音频视频关闭音频输出
    row = {"video_name": "demo", "start-time/s": "1", "question_id": "q5"}
    clip = fake_clip()
    with patch.object(video_split, "VideoFileClip", return_value=clip):
        video_split.data_process(row, "videos")
    clip.subclipped.return_value.write_videofile.assert_called_once_with(
        "./video_clip/q5.mp4", codec="libx264", audio=False
    )


def test_006():
    # 测试用例006：非法时间文本应被识别并报告
    row = {"video_name": "demo", "start-time/s": "abc", "question_id": "q6"}
    with pytest.raises(ValueError):
        video_split.data_process(row, "videos")


def test_007():
    # 测试用例007：缺少问题编号时应在打开视频前报错
    row = {"video_name": "demo", "start-time/s": "1"}
    with patch.object(video_split, "VideoFileClip") as video_file_clip:
        with pytest.raises(KeyError):
            video_split.data_process(row, "videos")
    video_file_clip.assert_not_called()
