import pytest

from windvg import (
    Circle,
    CircleSpec,
    Document,
    GridCellPoint,
    GridGuideSpec,
    Point,
    Polygon,
    PolySpec,
    rgb,
)
from windvg.document import _point_from_dict, _point_to_dict


@pytest.fixture
def doc():
    d = Document(240, 240)
    d.grid("grid1", origin=(10, 20), cols=6, rows=4, dx=30.0, dy=40.0)
    return d


class TestGridGuideNode:
    def test_grid_node_is_invisible_and_renders_nothing(self, doc):
        node = doc.get("grid1")
        assert not node.visible
        assert doc.resolve_to_json() == []
        assert doc.resolve().ops == []

    def test_grid_spec_round_trips_through_json(self, doc):
        d = doc.to_dict()
        assert d["nodes"][0]["shape"] == {
            "kind": "grid_guide",
            "origin": [10, 20],
            "cols": 6,
            "rows": 4,
            "dx": 30.0,
            "dy": 40.0,
        }
        restored = Document.from_dict(d)
        spec = restored.get("grid1").shape
        assert spec == GridGuideSpec(Point(10, 20), 6, 4, 30.0, 40.0)

    def test_grid_names_are_unique(self, doc):
        with pytest.raises(ValueError, match="duplicate node name"):
            doc.grid("grid1")


class TestGridCellPoint:
    def test_resolves_to_lattice_point(self, doc):
        doc.fill(
            "dot",
            CircleSpec(doc.grid_cell("grid1", 2, 3), 5),
            rgb(0, 0, 0),
        )
        scene = doc.resolve()
        shape = scene.ops[0].shape
        assert (shape.center.x, shape.center.y) == pytest.approx((70, 140))

    def test_offset_shifts_resolution(self, doc):
        doc.fill(
            "dot",
            CircleSpec(doc.grid_cell("grid1", 0, 0, offset=(5, -2)), 5),
            rgb(0, 0, 0),
        )
        shape = doc.resolve().ops[0].shape
        assert (shape.center.x, shape.center.y) == pytest.approx((15, 18))

    def test_serialization_round_trip(self):
        p = GridCellPoint("grid1", 2, 3, Point(1.5, -2.0))
        d = _point_to_dict(p)
        assert d == {
            "grid_cell": {"node": "grid1", "col": 2, "row": 3, "offset": [1.5, -2.0]}
        }
        back = _point_from_dict(d)
        assert back == p

    def test_offset_omitted_when_none(self):
        d = _point_to_dict(GridCellPoint("grid1", 0, 1))
        assert d == {"grid_cell": {"node": "grid1", "col": 0, "row": 1}}
        assert _point_from_dict(d) == GridCellPoint("grid1", 0, 1)

    def test_reference_to_non_grid_raises(self, doc):
        doc.fill("dot", Circle((0, 0), 5), rgb(0, 0, 0))
        doc.fill(
            "bad",
            CircleSpec(doc.grid_cell("dot", 1, 1), 5),
            rgb(0, 0, 0),
        )
        with pytest.raises(ValueError, match="not a grid guide"):
            doc.resolve()

    def test_missing_grid_raises(self):
        d = Document(10, 10)
        d.fill(
            "bad",
            CircleSpec(GridCellPoint("nope", 0, 0), 5),
            rgb(0, 0, 0),
        )
        with pytest.raises(KeyError):
            d.resolve()


class TestGridCodegen:
    def test_grid_and_cells_round_trip_through_code(self):
        doc = Document(240, 240)
        doc.grid("grid1", origin=(0, 0), cols=6, rows=6, dx=40.0, dy=40.0)
        doc.fill(
            "box",
            PolySpec(
                True,
                [
                    doc.grid_cell("grid1", 1, 0),
                    doc.grid_cell("grid1", 2, 0),
                    doc.grid_cell("grid1", 2, 1),
                    doc.grid_cell("grid1", 1, 1),
                ],
            ),
            rgb(0.4, 0.5, 0.9),
        )
        doc.fill(
            "dot",
            CircleSpec(doc.grid_cell("grid1", 3, 2, offset=(4.0, -1.0)), 5),
            rgb(0, 0, 0),
        )
        code = doc.generate_code()
        assert (
            "doc.grid('grid1', origin=(0.0, 0.0), cols=6, rows=6, dx=40.0, dy=40.0)" in code
        )
        assert "doc.grid_cell('grid1', 1, 0)" in code
        assert "doc.grid_cell('grid1', 3, 2, offset=(4.0, -1.0))" in code

        restored = Document.from_code(code)
        assert restored.get("grid1").shape == doc.get("grid1").shape
        scene = restored.resolve()
        box = next(op for op in scene.ops if isinstance(op.shape, Polygon))
        assert [(round(p.x), round(p.y)) for p in box.shape.points[:2]] == [
            (40, 0),
            (80, 0),
        ]
        dot = next(op for op in scene.ops if isinstance(op.shape, Circle))
        assert (dot.shape.center.x, dot.shape.center.y) == pytest.approx((124, 79))

    def test_grid_survives_to_dict_round_trip_with_cells(self):
        doc = Document(240, 240)
        doc.grid("g", origin=(0, 0), cols=4, rows=4, dx=60.0, dy=60.0)
        doc.fill(
            "dot",
            CircleSpec(doc.grid_cell("g", 1, 1), 5),
            rgb(0, 0, 0),
        )
        d = doc.to_dict()
        shape = Document.from_dict(d).get("dot").shape
        assert shape.center.node == "g" and shape.center.col == 1

    def test_visible_flag_is_preserved(self):
        doc = Document(240, 240)
        doc.grid("g")
        code = doc.generate_code()
        assert "visible" not in code  # grid nodes emit doc.grid(...), no fill
        other = Document(240, 240)
        other.fill("x", Circle((0, 0), 1), rgb(0, 0, 0), visible=False)
        assert "visible=False" in other.generate_code()
