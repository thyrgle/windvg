import pytest


def assert_pt(got, expected, tol=1e-9):
    """Assert a windvg Point (anything with .x/.y) equals expected (x, y) coordinates.

    cos(90 degrees) is 6.1e-16, not 0, so plain equality is too strict for
    anything derived from trigonometry, and `Point == pytest.approx(...)`
    degrades to exact comparison because Point.__eq__ bails on the approx type.
    """
    message = f"got {got!r}, want {expected}"
    assert (got.x, got.y) == pytest.approx(expected, abs=tol), message
