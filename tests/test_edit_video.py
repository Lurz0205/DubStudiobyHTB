import pytest
from pathlib import Path
if not Path('ui').exists():
    pytest.skip('Legacy PyQt6 v1 UI tests skipped because ui/ was decommissioned in v2.0.0', allow_module_level=True)

"""Tests for Video Editor API payload and analyze stage data structure."""
import pytest
from dubstudio.api.app import EditVideoRequest


def test_edit_video_request_model():
    req = EditVideoRequest(
        video_path="samples/test.mp4",
        crop_box={"x": 10, "y": 20, "w": 300, "h": 200},
        color_boxes=[
            {"enabled": True, "x": 0, "y": 100, "w": 400, "h": 50, "color": "#000000", "opacity": 0.8},
            {"enabled": True, "x": 10, "y": 200, "w": 300, "h": 40, "color": "#FF0000", "opacity": 0.5},
        ],
        image_overlay={"image_path": "logo.png", "fix_scale": True},
        output_name="custom_out.mp4",
    )
    assert req.video_path == "samples/test.mp4"
    assert req.crop_box["w"] == 300
    assert len(req.color_boxes) == 2
    assert req.output_name == "custom_out.mp4"


def test_overlay_multibox_management():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from ui.widgets.video_editor_overlay import VideoEditorOverlay

    overlay = VideoEditorOverlay()
    overlay.set_video_dimensions(1920, 1080, None)

    # Initial state has 0 boxes by default
    assert len(overlay.get_boxes()) == 0

    # Add first box
    idx1 = overlay.add_box()
    assert idx1 == 0
    assert len(overlay.get_boxes()) == 1

    # Add a second box
    idx2 = overlay.add_box()
    assert idx2 == 1
    assert len(overlay.get_boxes()) == 2
    assert overlay._selected_box_idx == 1

    # Add a third box
    idx3 = overlay.add_box()
    assert idx3 == 2
    assert len(overlay.get_boxes()) == 3

    # Delete selected box (box 3)
    new_sel = overlay.delete_selected_box()
    assert len(overlay.get_boxes()) == 2
    assert new_sel == 1

    # Update params of selected box
    overlay.set_box_params(True, 100, 200, 400, 80, "#FF0000", 0.9, 10)
    sel = overlay.get_selected_box()
    assert sel["x"] == 100
    assert sel["y"] == 200
    assert sel["w"] == 400
    assert sel["h"] == 80
    assert sel["color"] == "#FF0000"
    assert sel["opacity"] == 0.9
