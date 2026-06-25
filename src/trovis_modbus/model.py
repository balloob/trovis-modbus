"""Trovis-specific pieces layered on the ``modbus_connection.model`` framework.

The generic ``Component`` base, the field descriptors and the typed factories
(including ``enum`` for operating modes / weekdays) come straight from
``modbus_connection.model`` — sub-systems import those directly. This module adds
only what is specific to the Trovis 557x:

- :class:`TrovisComponent`, a ``Component`` preset with the controller's readable
  address ranges and the "Ebene" write-unlock sequencing;
- :func:`temperature`, a 0.1-scaled register with the controller's NaN sentinel.

Shaping the framework has no native type for (the controller's packed HHMM times
and day/month dates) stays a private raw field plus a normal ``@property`` on the
sub-system.
"""

from __future__ import annotations

from typing import Any

from modbus_connection.model import Component, RegisterField, gauge

from .ranges import COIL_RANGES, REGISTER_RANGES

NAN_INT16 = 0x7FFF  # the value the controller returns for an absent sensor


class TrovisComponent(Component):
    """A Trovis sub-system: readable ranges + the Ebene write-unlock quirk.

    Some writable values are ignored over Modbus unless their "Ebene" override
    coil is first released to 0 (= remote control). Subclasses list those in
    :attr:`ebene_coils` (``field name -> (coil address, per-index stride)``); the
    framework removed the built-in ``level_coil`` support in 3.0, so this is the
    recommended consumer-side ``write`` override.
    """

    register_ranges = REGISTER_RANGES
    coil_ranges = COIL_RANGES

    # Writable fields whose write must first release an override coil to 0.
    ebene_coils: dict[str, tuple[int, int]] = {}

    async def write(self, field: str, value: Any) -> None:
        if (override := self.ebene_coils.get(field)) is not None:
            address, stride = override
            await self._unit.write_coil(address + stride * (self._index - 1), False)
        await super().write(field, value)


def temperature(
    address: int,
    *,
    stride: int = 0,
    writable: bool = False,
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
        unit=unit,
    )
