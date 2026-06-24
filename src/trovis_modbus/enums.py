"""Enumerations used across the Trovis model."""

from __future__ import annotations

from enum import IntEnum


class OperatingMode(IntEnum):
    """Operating mode of a heating circuit, hot water, or a rotary switch.

    Matches the controller's switch list (``Liste_Schalter``). The hot-water
    rotary switch only uses ``PROGRAM``..``MANUAL``.
    """

    PROGRAM = 0  # timer program ("PA")
    AUTOMATIC = 1
    STANDBY = 2
    MANUAL = 3  # "Hand"
    DAY = 4  # comfort / "Sonne"
    NIGHT = 5  # setback / "Mond"


class Weekday(IntEnum):
    """Weekday for the thermal-disinfection schedule (0 = disabled)."""

    OFF = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


def enum_or_none[E: IntEnum](raw: int | None, enum: type[E]) -> E | None:
    """Map a raw register word to ``enum``, or ``None`` if absent / out of range."""
    if raw is None:
        return None
    try:
        return enum(raw)
    except ValueError:
        return None
