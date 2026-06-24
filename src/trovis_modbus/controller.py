"""Overall controller state: faults, rotary switches, summer mode, locks."""

from __future__ import annotations

from .component import (
    Component,
    coil,
    gauge,
    integer,
    operating_mode,
    raw_register,
    temperature,
)
from .utils import MonthDay


class Controller(Component):
    """Controller-wide status and settings."""

    error_status = integer(149, signed=False)
    max_flow_setpoint = temperature(98)
    # The three front-panel rotary switches, top to bottom.
    switch_top = operating_mode(102)  # RK1
    switch_middle = operating_mode(103)  # RK2
    switch_bottom = operating_mode(104)  # hot water
    summer_outside_limit = temperature(116, writable=True)
    outside_delay = gauge(117, 0.1, writable=True, unit="K/h")  # AT adaptation rate
    frost_limit = temperature(122, writable=True)
    station_address = integer(142, signed=False)
    summer_days_on = integer(114, writable=True)  # days above limit to enter summer
    summer_days_off = integer(115, writable=True)  # days below limit to leave summer

    collective_fault = coil(0)
    summer_active = coil(8)
    auto_daylight_saving = coil(136, writable=True)
    manual_levels_locked = coil(149, writable=True)
    rotary_switch_locked = coil(150, writable=True)

    _summer_start_raw = raw_register(112)
    _summer_end_raw = raw_register(113)

    @property
    def summer_start(self) -> MonthDay | None:
        """Start of the summer-mode window (day, month)."""
        raw = self._summer_start_raw
        return MonthDay(raw // 100, raw % 100) if raw else None

    @property
    def summer_end(self) -> MonthDay | None:
        """End of the summer-mode window (day, month)."""
        raw = self._summer_end_raw
        return MonthDay(raw // 100, raw % 100) if raw else None
