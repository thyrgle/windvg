"""Arc-length tables for tracks whose length has no closed form (ellipses, paths).

Samples a parametric curve uniformly in its parameter and accumulates chord
lengths. Inversion (distance -> parameter) and forward mapping interpolate
linearly between samples, so accuracy scales with the sample count; tangents
should use analytic derivatives where available.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable

from .geometry import Point


class ArcLengthTable:
    """Chordal arc-length model of a parametric curve over one parameter span."""

    def __init__(
        self,
        param_start: float,
        param_end: float,
        point_at: Callable[[float], Point],
        samples: int = 1440,
    ):
        if samples < 2:
            raise ValueError("an arc length table needs at least 2 samples")
        step = (param_end - param_start) / (samples - 1)
        self.params = [param_start + i * step for i in range(samples)]
        self.cum = [0.0]
        prev = point_at(self.params[0])
        for t in self.params[1:]:
            cur = point_at(t)
            self.cum.append(self.cum[-1] + prev.distance_to(cur))
            prev = cur
        self.total = self.cum[-1]
        self._point_at = point_at

    def param_to_distance(self, t: float) -> float:
        """Arc length at parameter `t`, which must lie within the sampled span."""
        i = bisect.bisect_right(self.params, t) - 1
        i = max(0, min(i, len(self.params) - 2))
        t0, t1 = self.params[i], self.params[i + 1]
        f = 0.0 if t1 == t0 else max(0.0, min(1.0, (t - t0) / (t1 - t0)))
        return self.cum[i] + f * (self.cum[i + 1] - self.cum[i])

    def distance_to_param(self, d: float) -> float:
        """Parameter at arc length `d`, clamped to [0, total]."""
        d = max(0.0, min(self.total, d))
        i = bisect.bisect_right(self.cum, d) - 1
        i = max(0, min(i, len(self.cum) - 2))
        seg = self.cum[i + 1] - self.cum[i]
        f = 0.0 if seg == 0 else (d - self.cum[i]) / seg
        return self.params[i] + f * (self.params[i + 1] - self.params[i])
