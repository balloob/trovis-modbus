"""Overall controller state: faults, rotary switches, summer mode, locks."""

from __future__ import annotations

from modbus_connection.model import coil, gauge, integer, raw_register

from .enums import OperatingMode, enum_or_none
from .model import TrovisComponent, temperature
from .utils import MonthDay


class Controller(TrovisComponent):
    """Controller-wide status and settings."""

    error_status = integer(149, signed=False)
    max_flow_setpoint = temperature(98)
    # The three front-panel rotary switches, top to bottom (RK1 / RK2 / hot water).
    _switch_top_raw = integer(102, signed=False)
    _switch_middle_raw = integer(103, signed=False)
    _switch_bottom_raw = integer(104, signed=False)
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
    def switch_top(self) -> OperatingMode | None:
        """Top rotary switch (RK1)."""
        return enum_or_none(self._switch_top_raw, OperatingMode)

    @property
    def switch_middle(self) -> OperatingMode | None:
        """Middle rotary switch (RK2)."""
        return enum_or_none(self._switch_middle_raw, OperatingMode)

    @property
    def switch_bottom(self) -> OperatingMode | None:
        """Bottom rotary switch (hot water)."""
        return enum_or_none(self._switch_bottom_raw, OperatingMode)

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
