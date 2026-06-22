"""Heating-curve computation (ported from the original YAML template)."""

from __future__ import annotations

# Outside-temperature x-axis shared by every heating curve.
OUTSIDE_TEMPERATURES: list[int] = list(range(-20, 21))


def flow_temperatures(
    *,
    room_setpoint: float,
    slope: float,
    level: float,
    flow_min: float,
    flow_max: float,
) -> list[float]:
    """Flow temperatures for outside temps -20..20 °C, clamped to [min, max].

    Reproduces the formula from the upstream ``heating_curves.yaml`` exactly,
    including its ``(x - 20)`` reference shift. Pair element ``i`` with
    :data:`OUTSIDE_TEMPERATURES`\\ ``[i]``.
    """
    curve: list[float] = []
    for outside in OUTSIDE_TEMPERATURES:
        shifted = outside - 20
        flow = (
            24
            + level
            + 2 * slope * (room_setpoint - 20)
            - (0.1 + 0.9 * slope) * (1.5 * shifted + 0.01 * (shifted * shifted))
        )
        curve.append(round(max(flow_min, min(flow_max, flow)), 2))
    return curve
