from dse_panel.mapping import describe_buttons, mask_names, union_buttons
from dse_panel.protocol import names_from_buttons


def test_names_from_buttons_includes_edge_and_hat():
    names = names_from_buttons((0x08, 0x40, 0xF1, 0))
    assert "L3" in names
    assert "PS" in names
    assert "FN1" in names
    assert "FN2" in names
    assert "左背键" in names
    assert "右背键" in names


def test_mask_names_excludes_hat_direction():
    assert mask_names((0x00, 0x00, 0x00, 0)) == []
    assert mask_names((0x08, 0x40, 0x00, 0)) == ["L3"]


def test_describe_buttons_joins_combo():
    assert describe_buttons((0x08, 0x40, 0x00, 0)) == "L3"
    assert describe_buttons((0x48, 0x40, 0x00, 0)) == "圆圈 + L3"
    assert describe_buttons((0x08, 0, 0, 0)) == "无按键"


def test_union_buttons_merges_combo():
    left = (0x08, 0x40, 0x00, 0)
    right = (0x48, 0x00, 0x00, 0)
    assert union_buttons(left, right) == (0x48, 0x40, 0x00, 0)
