import pytest

from windvg import BLACK, Circle, Polygon, Polyline, Scene, rgba


@pytest.fixture
def scene() -> Scene:
    s = Scene(200, 100)
    s.fill(Polygon([(0, 0), (10, 0), (0, 10)]), rgba(1, 0, 0, 0.5))
    s.stroke(Circle((50, 50), 20), BLACK, width=2.5)
    s.stroke(Polyline([(0, 0), (5, 5)]), BLACK, width=1)
    return s


def test_document_scaffold(scene: Scene):
    svg = scene.to_svg()
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert 'width="200" height="100"' in svg
    assert 'viewBox="0 0 200 100"' in svg
    assert svg.rstrip().endswith("</svg>")


def test_polygon_with_opacity(scene: Scene):
    svg = scene.to_svg()
    assert '<polygon points="0,0 10,0 0,10" fill="#FF0000" fill-opacity="0.500"/>' in svg


def test_circle_stroke(scene: Scene):
    svg = scene.to_svg()
    assert (
        '<circle cx="50" cy="50" r="20" fill="none" stroke="#000000"'
        ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
    ) in svg


def test_polyline_element(scene: Scene):
    assert '<polyline points="0,0 5,5" fill="none"' in scene.to_svg()


def test_invisible_ops_are_omitted(scene: Scene):
    hidden = Scene(200, 100)
    hidden.fill(Polygon([(0, 0), (10, 0), (0, 10)]), rgba(1, 0, 0, 0.5))
    hidden.stroke(Circle((50, 50), 20), BLACK, width=2.5, visible=False)
    svg = hidden.to_svg()
    assert "<circle" not in svg
    assert '<polygon points="0,0 10,0 0,10"' in svg
