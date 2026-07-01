"""Overall controller state: faults, rotary switches, summer mode, locks."""

from __future__ import annotations

from modbus_connection.model import enum, gauge, integer, raw_register

from .enums import OperatingMode
from .model import TrovisComponent, coil, enum, gauge, integer, raw_register, temperature
from .utils import MonthDay


class Controller(TrovisComponent):
    """Controller-wide status and settings."""

    ##### registers

    max_flow_setpoint = temperature(40099)

    # The three front-panel rotary switches, top to bottom (RK1 / RK2 / hot water).
    switch_top = enum(40103, OperatingMode)
    switch_middle = enum(40104, OperatingMode)
    switch_bottom = enum(40105, OperatingMode)

    _summer_start_raw = raw_register(40113)
    _summer_end_raw = raw_register(40114)
    summer_days_on = integer(40115, writable=True)  # days above limit to enter summer
    summer_days_off = integer(40116, writable=True)  # days below limit to leave summer
    summer_outside_limit = temperature(40117, writable=True)

    outside_delay = gauge(40118, 0.1, writable=True, unit="K/h")  # AT adaptation rate
    frost_limit = temperature(40123, writable=True)
    station_address = integer(40143, signed=False)
    error_status = integer(40150, signed=False)

    ##### coils

    general_fault = coil(1)
    data_entry_active = coil(2)  # CL2 / Dateneing_aktiv
    data_entry_performed = coil(3)  # CL3 / Dateneing_stattg
    global_level_autark = coil(4)  # CL4 / Sammel_Ebenenbit
    summer_active = coil(9)

    delayed_outside_temp_adjustment_falling = coil(134, writable=True)  # CL134 / FB05
    delayed_outside_temp_adjustment_rising = coil(135, writable=True)  # CL135 / FB06

    auto_daylight_saving = coil(  # CL137 / FB08
        137,
        writable=True,
        false_key="inactive",
        true_key="active",
        false_label="Inaktiv",
        true_label="Aktiv",
        maker_key="FB08_AutSommZeit",
        description="Automatische Sommer-/Winterzeitumschaltung",
    )

    manual_levels_locked = coil(150, writable=True)  # CL150 / FB21
    rotary_switch_locked = coil(151, writable=True)  # CL151 / FB22


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
