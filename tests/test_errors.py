from dubstudio.errors import DubError


def test_dub_error_formatting():
    err = DubError(
        code="TEST_CODE",
        user_message_vi="Có lỗi xảy ra",
        hint_vi="Hãy thử lại sau",
        details={"file": "test.mp4", "line": 10},
    )
    formatted = err.format_user()
    assert "TEST_CODE" in formatted
    assert "Có lỗi xảy ra" in formatted
    assert "Hãy thử lại sau" in formatted
    assert "test.mp4" in formatted
