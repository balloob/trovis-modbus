"""Trovis-specific pieces layered on the ``modbus_connection.model`` framework.

The generic ``Component`` base, the field descriptors and the typed factories
come straight from ``modbus_connection.model`` (sub-systems import those
directly). This module adds only what is specific to the Trovis 557x:

- :class:`TrovisComponent`, a ``Component`` preset with the controller's readable
  address ranges, so every sub-system reads without crossing an unreadable gap;
- :func:`temperature`, a 0.1-scaled register with the controller's NaN sentinel.

Values needing device-specific shaping (operating modes, weekdays, packed times,
dates) are declared as a private raw field plus a normal ``@property`` on the
sub-system, so only very generic field types are used here.
"""

from __future__ import annotations

from modbus_connection.model import Component, RegisterField, gauge

from .ranges import COIL_RANGES, REGISTER_RANGES

NAN_INT16 = 0x7FFF  # the value the controller returns for an absent sensor


class TrovisComponent(Component):
    """A Trovis sub-system, preset with the controller's readable address ranges."""

    register_ranges = REGISTER_RANGES
    coil_ranges = COIL_RANGES


def temperature(
    address: int,
    *,
    stride: int = 0,
    writable: bool = False,
    level_coil: int | None = None,
    level_coil_stride: int = 0,
    unit: str = "°C",
) -> RegisterField[float]:
    """A signed 0.1-scaled temperature register with the Trovis NaN sentinel."""
    return gauge(
        address,
        0.1,
        signed=True,
        nan=NAN_INT16,
        stride=stride,
        writable=writable,
        level_coil=level_coil,
        level_coil_stride=level_coil_stride,
        unit=unit,
    )
