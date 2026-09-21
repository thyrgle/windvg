import pytest

from windvg import BLACK, Circle, Polygon, Polyline, Scene, rgb


def make_square() -> Polygon:
    return Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])


def test_scene_dimensions_validated():
    with pytest.raises(ValueError):
        Scene(0, 10)
    with pytest.raises(ValueError):
        Scene(10, -1)


def test_stroke_width_validated():
    with pytest.raises(ValueError):
        Scene(10, 10).stroke(Circle((5, 5), 2), BLACK, width=-1)


def test_ops_preserve_order():
    scene = Scene(10, 10)
    scene.fill(make_square(), BLACK)
    scene.stroke(Circle((5, 5), 2), BLACK)
    scene.outline_fill(make_square(), BLACK, rgb(1, 0, 0))
    assert [type(op).__name__ for op in scene.ops] == [
        "FillOp",
        "StrokeOp",
        "OutlineFillOp",
    ]


def test_tvgt_dump():
    scene = Scene(10, 10)
    scene.fill(make_square(), rgb(0, 0, 1))
    scene.stroke(Polyline([(0, 0), (5, 5)]), BLACK, width=2)
    dump = scene.to_tvgt()
    lines = dump.splitlines()
    assert lines[0] == "scene 10x10"
    assert lines[1].startswith("  0: fill    polygon")
    assert "#0000FF" in lines[1]
    assert "w=2" in lines[2]
