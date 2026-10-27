import pytest
from pathlib import Path
if not Path('ui').exists():
    pytest.skip('Legacy PyQt6 v1 UI tests skipped because ui/ was decommissioned in v2.0.0', allow_module_level=True)

import os
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF, QEvent
from PyQt6.QtGui import QMouseEvent
from ui.widgets.subtitle_editor import SubtitleEditorWidget, NoScrollComboBox
from ui.widgets.timeline_ruler import TimelineWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_replace_all_syncs_cues_and_sub_slices(qapp):
    editor = SubtitleEditorWidget()
    segments = [
        {
            "id": 1,
            "start": 0.0,
            "end": 4.0,
            "zh_text": "iPhone",
            "vi_text": "Đây là chiếc Iphone xịn",
            "voice": "Minh Đức",
            "cues": [
                {"text": "Đây là chiếc Iphone", "start": 0.0, "end": 2.0},
                {"text": "xịn", "start": 2.0, "end": 4.0},
            ],
            "sub_slices": [
                {"text": "Đây là chiếc Iphone", "start": 0.0, "end": 2.0},
                {"text": "xịn", "start": 2.0, "end": 4.0},
            ],
        }
    ]
    editor.load_segments(segments)

    batch_emitted = []
    editor.segments_batch_changed.connect(lambda updates: batch_emitted.extend(updates))

    # Replace 'Iphone' -> 'Iphone Duo'
    count = editor.replace_all("Iphone", "Iphone Duo")
    assert count == 1
    assert editor.item(0, editor.COL_VI).text() == "Đây là chiếc Iphone Duo xịn"

    # Check that in-memory segments were updated
    assert editor._segments[0]["vi_text"] == "Đây là chiếc Iphone Duo xịn"
    assert editor._segments[0]["cues"][0]["text"] == "Đây là chiếc Iphone Duo"
    assert editor._segments[0]["sub_slices"][0]["text"] == "Đây là chiếc Iphone Duo"

    # Check signal emitted full payload
    assert len(batch_emitted) == 1
    assert batch_emitted[0]["id"] == 1
    assert batch_emitted[0]["vi_text"] == "Đây là chiếc Iphone Duo xịn"
    assert batch_emitted[0]["cues"][0]["text"] == "Đây là chiếc Iphone Duo"
    assert batch_emitted[0]["sub_slices"][0]["text"] == "Đây là chiếc Iphone Duo"


def test_mouse_hover_does_not_select_row_in_voice_col(qapp):
    editor = SubtitleEditorWidget()
    segments = [
        {"id": 1, "start": 0.0, "end": 2.0, "zh_text": "zh1", "vi_text": "vi1", "voice": "Minh Đức"},
        {"id": 2, "start": 2.0, "end": 4.0, "zh_text": "zh2", "vi_text": "vi2", "voice": "Hải Đăng"},
    ]
    editor.load_segments(segments)
    editor.show()

    selected_rows = []
    editor.itemSelectionChanged.connect(lambda: selected_rows.append([idx.row() for idx in editor.selectedIndexes()]))

    cb1 = editor.cellWidget(1, editor.COL_VOICE)
    assert isinstance(cb1, NoScrollComboBox)
    assert cb1.focusPolicy() == Qt.FocusPolicy.NoFocus

    # Send mouse move without mouse buttons pressed
    ev_move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(20, 20),
        QPointF(20, 20),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(cb1, ev_move)
    qapp.sendEvent(editor.viewport(), ev_move)

    # Must NOT have triggered selection change
    assert len(selected_rows) == 0
    assert len(editor.selectedIndexes()) == 0
