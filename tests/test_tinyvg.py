import pytest
from tvgreader import parse

from windvg import (
    BLACK,
    BLUE,
    CCW,
    CW,
    Circle,
    Polygon,
    Polyline,
    Scene,
    connect,
    regular_polygon,
    rgb,
    rgba,
    star_polygon,
)
from windvg.tinyvg import encode, write_varuint


class TestVarUInt:
    # examples straight from the TinyVG specification
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, bytes([0x00])),
            (100, bytes([0x64])),
            (127, bytes([0x7F])),
            (128, bytes([0x80, 0x01])),
            (16271, bytes([0x8F, 0x7F])),
            (16383, bytes([0xFF, 0x7F])),
            (16384, bytes([0x80, 0x80, 0x01])),
            (1048576, bytes([0x80, 0x80, 0x40])),
            (4294967295, bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x0F])),
        ],
    )
    def test_spec_examples(self, value, expected):
        assert write_varuint(value) == expected


class TestGoldenBytes:
    def test_minimal_triangle(self):
        scene = Scene(10, 10)
        scene.fill(Polygon([(0, 0), (10, 0), (0, 10)]), rgb(1, 0, 0))
        expected = bytes.fromhex(
            "72 56 01 04"  # magic, version, scale=4 | RGBA8888 | 16-bit
            "0A 00"  # width
            "0A 00"  # height
            "01"  # one color
            "FF 00 00 FF"  # red, opaque
            "01"  # fill polygon, flat style
            "02"  # 3 points (off by one)
            "00"  # color index 0
            "00 00 00 00"  # (0, 0)
            "A0 00 00 00"  # (10, 0)
            "00 00 A0 00"  # (0, 10)
            "00"  # end of document
        )
        assert encode(scene) == expected

    def test_empty_scene(self):
        data = encode(Scene(10, 10))
        parsed = parse(data)
        assert parsed["shapes"] == []
        assert parsed["colors"] == []
        assert data == bytes.fromhex("72 56 01 04 0A 00 0A 00 00 00")


class TestHeader:
    def test_round_trip_fields(self):
        scene = Scene(320, 240)
        scene.stroke(Circle((160, 120), 50), BLUE, width=2.5)
        parsed = parse(scene.to_tinyvg())
        assert parsed["version"] == 1
        assert parsed["scale"] == 4
        assert parsed["color_encoding"] == 0
        assert parsed["coord_range"] == 0
        assert parsed["width"] == 320
        assert parsed["height"] == 240
        assert parsed["colors"] == [(0, 0, 255, 255)]

    def test_auto_switches_to_32_bit_units(self):
        scene = Scene(50000, 50000)
        scene.fill(Polygon([(0, 0), (40000, 0), (0, 40000)]), BLACK)
        parsed = parse(scene.to_tinyvg())
        assert parsed["coord_range"] == 2
        assert parsed["width"] == 50000

    def test_color_dedup_and_order(self):
        scene = Scene(10, 10)
        red, green = rgb(1, 0, 0), rgb(0, 1, 0)
        scene.fill(Polygon([(0, 0), (5, 0), (0, 5)]), red)
        scene.fill(Polygon([(5, 5), (10, 5), (5, 10)]), green)
        scene.stroke(Circle((5, 5), 2), red, 1.0)
        parsed = parse(scene.to_tinyvg())
        assert parsed["colors"] == [(255, 0, 0, 255), (0, 255, 0, 255)]


class TestShapesRoundTrip:
    def test_fill_polygon(self):
        scene = Scene(100, 100)
        triangle = Polygon([(10, 10), (90, 10), (10, 90)])
        scene.fill(triangle, rgba(0.5, 0.5, 0.5, 0.5))
        parsed = parse(scene.to_tinyvg())
        assert parsed["colors"] == [(128, 128, 128, 128)]
        assert len(parsed["shapes"]) == 1
        shape = parsed["shapes"][0]
        assert shape["op"] == "fill"
        assert shape["points"][0] == pytest.approx((10, 10), abs=0.05)
        assert shape["points"][1] == pytest.approx((90, 10), abs=0.05)

    def test_stroke_polygon_is_line_loop(self):
        scene = Scene(100, 100)
        scene.stroke(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]), BLACK, width=1.5)
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert shape["op"] == "stroke"
        assert "strip" not in shape
        assert shape["width"] == pytest.approx(1.5, abs=0.01)
        assert shape["points"][0] == pytest.approx((0, 0), abs=0.05)

    def test_stroke_polyline_is_line_strip(self):
        scene = Scene(100, 100)
        scene.stroke(Polyline([(0, 0), (10, 10), (20, 0)]), BLACK, width=1.0)
        parsed = parse(scene.to_tinyvg())
        assert parsed["shapes"][0].get("strip") is True

    def test_fill_circle_is_two_exact_half_arcs(self):
        scene = Scene(100, 100)
        circle = Circle((50, 50), 20)
        scene.fill(circle, BLUE)
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert shape["op"] == "fill"
        assert len(shape["paths"]) == 1
        segment = shape["paths"][0]
        assert len(segment["commands"]) == 3
        assert segment["start"] == pytest.approx((70, 50), abs=0.05)
        arc0, arc1, closing = segment["commands"]
        assert arc0["cmd"] == "arc" and arc1["cmd"] == "arc"
        assert closing == {"cmd": "close"}
        for arc in (arc0, arc1):
            assert arc["large_arc"] == 0
            assert arc["sweep"] == 0  # right turns = visually clockwise
            assert arc["radius"] == pytest.approx(20, abs=0.05)
        assert arc0["target"] == pytest.approx((30, 50), abs=0.05)
        assert arc1["target"] == pytest.approx((70, 50), abs=0.05)

    def test_stroke_circle_is_line_path(self):
        scene = Scene(100, 100)
        scene.stroke(Circle((50, 50), 20), BLACK, width=3.0)
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert shape["op"] == "stroke"
        assert shape["width"] == pytest.approx(3.0, abs=0.01)
        assert shape["paths"][0]["commands"][0]["cmd"] == "arc"

    def test_outline_fill_circle(self):
        scene = Scene(100, 100)
        scene.outline_fill(Circle((50, 50), 20), BLUE, BLACK, width=2.0)
        parsed = parse(scene.to_tinyvg())
        shape = parsed["shapes"][0]
        assert shape["op"] == "outline_fill"
        assert shape["style"] == 0 and shape["outline_style"] == 1
        assert parsed["colors"] == [(0, 0, 255, 255), (0, 0, 0, 255)]

    def test_outline_fill_polygon(self):
        scene = Scene(100, 100)
        scene.outline_fill(regular_polygon((50, 50), 30, 6), BLUE, BLACK, width=2.0)
        parsed = parse(scene.to_tinyvg())
        assert parsed["shapes"][0]["op"] == "outline_fill"

    def test_outline_fill_large_polygon_falls_back(self):
        scene = Scene(200, 200)
        # 65 points: too many for the outline fill polygon command
        big = regular_polygon((100, 100), 80, 65)
        scene.outline_fill(big, BLUE, BLACK, width=1.0)
        parsed = parse(scene.to_tinyvg())
        assert [shape["op"] for shape in parsed["shapes"]] == ["fill", "stroke"]


class TestAnchorDrivenScene:
    def test_full_drawing_round_trips(self):
        circle = Circle((100, 100), 60)
        square = regular_polygon((100, 100), 80, 4)
        scene = Scene(200, 200)
        scene.fill(star_polygon(circle, 5, 2), rgb(0.95, 0.8, 0.2))
        anchor_a = circle.anchor((160, 100), CW)
        anchor_b = square.anchor((100, 20), CCW)
        scene.stroke(connect((anchor_a, 50), anchor_b), BLACK, width=2.0)
        parsed = parse(scene.to_tinyvg())
        assert [shape["op"] for shape in parsed["shapes"]] == ["fill", "stroke"]
        assert parsed["colors"] == [(242, 204, 51, 255), (0, 0, 0, 255)]


class TestValidation:
    def test_scale_out_of_range(self):
        with pytest.raises(ValueError):
            Scene(10, 10).to_tinyvg(scale=16)

    def test_cannot_fill_polyline(self):
        with pytest.raises(ValueError):
            Scene(10, 10).fill(Polyline([(0, 0), (5, 5)]), BLACK)
