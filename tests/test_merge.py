from pathlib import Path
import pytest
from dubstudio.errors import DubError
from dubstudio.ffmpeg_utils import probe_file
from dubstudio.tools.merge import can_stream_copy, merge_videos


def test_merge_not_enough_files():
    with pytest.raises(DubError) as exc:
        merge_videos([Path("samples/tiny.mp4")], Path("out/test.mp4"))
    assert exc.value.code == "MERGE_NOT_ENOUGH_FILES"


def test_merge_missing_file():
    with pytest.raises(DubError) as exc:
        merge_videos([Path("samples/tiny.mp4"), Path("samples/non_existent.mp4")], Path("out/test.mp4"))
    assert exc.value.code == "MERGE_FILE_NOT_FOUND"


def test_can_stream_copy_logic():
    prof_same_1 = ({"codec": "h264", "width": 1920, "height": 1080}, {"codec": "aac", "sample_rate": "44100", "channels": 2})
    prof_same_2 = ({"codec": "h264", "width": 1920, "height": 1080}, {"codec": "aac", "sample_rate": "44100", "channels": 2})
    prof_diff_res = ({"codec": "h264", "width": 1280, "height": 720}, {"codec": "aac", "sample_rate": "44100", "channels": 2})
    prof_diff_codec = ({"codec": "hevc", "width": 1920, "height": 1080}, {"codec": "aac", "sample_rate": "44100", "channels": 2})

    assert can_stream_copy([prof_same_1, prof_same_2]) is True
    assert can_stream_copy([prof_same_1, prof_diff_res]) is False
    assert can_stream_copy([prof_same_1, prof_diff_codec]) is False


def test_merge_tiny_videos_stream_copy(tmp_path):
    tiny = Path("samples/tiny.mp4")
    out_merged = tmp_path / "merged_copy.mp4"

    res = merge_videos([tiny, tiny], out_merged, force_reencode=False)
    assert res.exists()
    assert res.stat().st_size > 0

    probe = probe_file(res)
    duration = float(probe["format"]["duration"])
    # tiny.mp4 is 10s, two merged should be ~20s
    assert duration > 15.0


def test_merge_tiny_videos_reencode(tmp_path):
    tiny = Path("samples/tiny.mp4")
    out_merged = tmp_path / "merged_reencode.mp4"

    res = merge_videos([tiny, tiny], out_merged, force_reencode=True, nvenc=False)
    assert res.exists()
    assert res.stat().st_size > 0

    probe = probe_file(res)
    duration = float(probe["format"]["duration"])
    assert duration > 15.0
