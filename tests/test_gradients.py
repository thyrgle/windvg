
import pytest
from tvgreader import parse

from windvg import (
    Circle,
    LinearGradient,
    Point,
    Polygon,
    RadialGradient,
    Scene,
    rgb,
    rgba,
)

BLACK = rgb(0, 0, 0)
ORANGE = rgb(1, 0.6, 0.2)
PURPLE = rgb(0.5, 0.2, 0.9)


class TestTinyVGGradients:
    def test_linear_gradient_fill_round_trip(self):
        scene = Scene(200, 200)
        paint = LinearGradient((0, 0), (200, 200), ORANGE, PURPLE)
        scene.fill(Circle((100, 100), 60), paint)
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert shape["style"] == {
            "linear": {
                "points": ((0.0, 0.0), (200.0, 200.0)),
                "colors": (0, 1),
            }
        }
        assert parsed["colors"] == [
            (255, 153, 51, 255),  # ORANGE
            (128, 51, 230, 255),  # PURPLE
        ]

    def test_radial_gradient_fill_round_trip(self):
        scene = Scene(200, 200)
        paint = RadialGradient((100, 100), (160, 100), rgb(1, 1, 1), rgb(0, 0, 0))
        scene.fill(Circle((100, 100), 60), paint)
        parsed = parse(scene.to_tinyvg())
        style = parsed["shapes"][0]["style"]
        (name, data), = style.items()
        assert name == "radial"
        pts = [pt for pair in data["points"] for pt in pair]
        assert pts == pytest.approx([100, 100, 160, 100], abs=0.05)
        assert data["colors"] == (0, 1)

    def test_gradient_stroke_command_kind(self):
        scene = Scene(100, 100)
        paint = LinearGradient((0, 0), (100, 0), ORANGE, PURPLE)
        scene.stroke(Circle((50, 50), 30), paint, width=3.0)
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert shape["op"] == "stroke"
        assert "linear" in shape["style"]

    def test_outline_fill_mixed_kinds(self):
        scene = Scene(200, 200)
        square = Polygon([(20, 20), (180, 20), (180, 180), (20, 180)])
        scene.outline_fill(
            square,
            LinearGradient((20, 20), (180, 180), ORANGE, PURPLE),
            BLACK,
            width=2.0,
        )
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert "linear" in shape["style"]
        assert shape["outline_style"] == 2  # flat, third color in table
        assert parsed["colors"][2] == (0, 0, 0, 255)

    def test_flat_and_gradient_share_color_table(self):
        scene = Scene(100, 100)
        scene.fill(Polygon([(0, 0), (10, 0), (0, 10)]), ORANGE)
        shared = rgb(0, 0, 0)
        scene.fill(
            Polygon([(90, 90), (80, 90), (90, 80)]),
            LinearGradient((0, 0), (100, 100), ORANGE, shared),
        )
        parsed = parse(scene.to_tinyvg())
        # ORANGE reused by index, not duplicated; BLACK appended once
        assert parsed["colors"] == [
            (255, 153, 51, 255),
            (0, 0, 0, 255),
        ]
        style = parsed["shapes"][1]["style"]["linear"]
        assert style["colors"] == (0, 1)

    def test_gradient_points_count_toward_coord_range(self):
        scene = Scene(10, 10)
        scene.fill(
            Polygon([(0, 0), (5, 0), (0, 5)]),
            LinearGradient((0, 0), (40000, 40000), ORANGE, PURPLE),
        )
        parsed = parse(scene.to_tinyvg())
        assert parsed["coord_range"] == 2

    def test_alpha_colors_in_gradients(self):
        scene = Scene(100, 100)
        scene.fill(
            Circle((50, 50), 40),
            LinearGradient((0, 0), (100, 0), rgba(1, 0, 0, 0.5), rgba(0, 0, 1, 0.5)),
        )
        parsed = parse(scene.to_tinyvg())
        assert parsed["colors"] == [(255, 0, 0, 128), (0, 0, 255, 128)]


class TestSVGGradients:
    def test_linear_gradient_defs(self):
        scene = Scene(200, 100)
        paint = LinearGradient((0, 0), (200, 0), ORANGE, PURPLE)
        scene.fill(Circle((100, 50), 40), paint)
        svg = scene.to_svg()
        assert "<defs>" in svg
        assert (
            '<linearGradient id="g0" gradientUnits="userSpaceOnUse"'
            ' x1="0" y1="0" x2="200" y2="0">'
        ) in svg
        assert '<stop offset="0" stop-color="#FF9933"/>' in svg
        assert '<stop offset="1" stop-color="#8033E6"/>' in svg
        assert 'fill="url(#g0)"' in svg

    def test_radial_gradient_attrs(self):
        scene = Scene(200, 200)
        scene.fill(
            Circle((100, 100), 60),
            RadialGradient((100, 100), (160, 100), rgb(1, 1, 1), rgb(0, 0, 0)),
        )
        svg = scene.to_svg()
        assert '<radialGradient id="g0" gradientUnits="userSpaceOnUse"' in svg
        assert 'cx="100" cy="100" r="60"' in svg

    def test_gradient_stroke_url(self):
        scene = Scene(100, 100)
        paint = LinearGradient((0, 0), (100, 0), ORANGE, PURPLE)
        scene.stroke(Circle((50, 50), 30), paint, width=2.0)
        svg = scene.to_svg()
        assert 'stroke="url(#g0)"' in svg
        assert "fill=\"none\"" in svg

    def test_no_defs_for_flat_scenes(self):
        scene = Scene(100, 100)
        scene.fill(Circle((50, 50), 30), ORANGE)
        assert "<defs>" not in scene.to_svg()


class TestPaintHelpers:
    def test_paint_colors_order(self):
        paint = RadialGradient((0, 0), (10, 0), ORANGE, PURPLE)
        from windvg.gradient import paint_colors

        assert paint_colors(paint) == [ORANGE, PURPLE]
        assert paint_colors(ORANGE) == [ORANGE]

    def test_gradient_construction_from_tuples(self):
        paint = LinearGradient((0, 0), (10, 10), ORANGE, PURPLE)
        assert paint.start == Point(0, 0)
        assert paint.end == Point(10, 10)
