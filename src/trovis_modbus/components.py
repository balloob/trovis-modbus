"""The Trovis sub-systems, each a self-updating Component.

Register/coil addresses, scales and read/write flags are taken from the
canonical Samson Trovis 557x point list (the Tom-Bom-badil SmartHomeNG plugin),
verified in tests against ``tests/reference/canonical_points.json``.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import NamedTuple

from . import curve
from .component import Component
from .device_info import DeviceInfo
from .enums import OperatingMode
from .fields import CoilField, RegisterField, temperature


class MonthDay(NamedTuple):
    """A recurring day-of-year without a year (e.g. a summer-mode boundary)."""

    day: int
    month: int


class DeviceInformation(Component):
    """Controller identity and firmware/hardware versions."""

    model = RegisterField(0, signed=False, doc="Product number, e.g. 5579")
    system = RegisterField(1, scale=0.1, signed=False, doc="Hydraulic system code")
    firmware_version = RegisterField(
        2, scale=0.01, signed=False, doc="Firmware version"
    )
    hardware_version = RegisterField(
        3, scale=0.01, signed=False, doc="Hardware version"
    )
    serial_number = RegisterField(5, signed=False, doc="Internal controller ID")

    @property
    def device_info(self) -> DeviceInfo:
        """A static identity snapshot for Home Assistant."""
        model = self.model
        serial = self.serial_number
        firmware = self.firmware_version
        hardware = self.hardware_version
        return DeviceInfo(
            manufacturer="Samson",
            model=f"Trovis {model}" if model else "Trovis 557x",
            serial_number=str(serial) if serial is not None else None,
            firmware_version=f"{firmware:.2f}" if firmware is not None else None,
            hardware_version=f"{hardware:.2f}" if hardware is not None else None,
        )


class Controller(Component):
    """Overall controller state: faults, rotary switches, summer mode, locks."""

    error_status = RegisterField(149, signed=False, doc="Error status register")
    max_flow_setpoint = temperature(98, doc="Maximum flow setpoint of the controller")
    switch_top = RegisterField(102, kind="mode", doc="Rotary switch RK1")
    switch_middle = RegisterField(103, kind="mode", doc="Rotary switch RK2")
    switch_bottom = RegisterField(104, kind="mode", doc="Rotary switch hot water")
    summer_outside_limit = temperature(
        116, writable=True, doc="Outside-temp threshold for summer mode"
    )
    outside_delay = RegisterField(
        117, writable=True, unit="K/h", doc="Outside-temp adaptation delay"
    )
    frost_limit = temperature(122, writable=True, doc="Frost-protection threshold")
    station_address = RegisterField(142, signed=False, doc="Modbus station address")
    _summer_start_raw = RegisterField(112, kind="raw")
    _summer_end_raw = RegisterField(113, kind="raw")
    summer_days_on = RegisterField(114, writable=True, doc="Days to enter summer mode")
    summer_days_off = RegisterField(115, writable=True, doc="Days to leave summer mode")

    collective_fault = CoilField(0, doc="Any fault present")
    summer_active = CoilField(8, doc="Summer mode active")
    auto_daylight_saving = CoilField(136, writable=True, doc="Auto summer/winter time")
    manual_levels_locked = CoilField(149, writable=True, doc="Manual override locked")
    rotary_switch_locked = CoilField(150, writable=True, doc="Rotary switch locked")

    @staticmethod
    def _month_day(raw: int | None) -> MonthDay | None:
        if not raw:
            return None
        return MonthDay(day=raw // 100, month=raw % 100)

    @property
    def summer_start(self) -> MonthDay | None:
        """Start of the summer-mode window (day, month)."""
        return self._month_day(self._summer_start_raw)

    @property
    def summer_end(self) -> MonthDay | None:
        """End of the summer-mode window (day, month)."""
        return self._month_day(self._summer_end_raw)


class Clock(Component):
    """The controller's date and time, as native ``datetime`` objects."""

    _time_raw = RegisterField(99, kind="raw", writable=True)
    _date_raw = RegisterField(100, kind="raw", writable=True)
    _year_raw = RegisterField(101, kind="raw", writable=True)

    @property
    def time(self) -> time | None:
        """Time of day."""
        raw = self._time_raw
        if raw is None:
            return None
        hour, minute = divmod(raw, 100)
        if hour > 23 or minute > 59:
            return None
        return time(hour=hour, minute=minute)

    @property
    def date(self) -> date | None:
        """Calendar date (the controller stores day*100+month and the year)."""
        raw = self._date_raw
        year = self._year_raw
        if not raw or not year:
            return None
        try:
            return date(year=year, month=raw % 100, day=raw // 100)
        except ValueError:
            return None

    @property
    def datetime(self) -> datetime | None:
        """Combined date and time."""
        if (day := self.date) is None or (moment := self.time) is None:
            return None
        return datetime.combine(day, moment)


class Sensors(Component):
    """All temperature inputs (only those wired to a probe report a value)."""

    outside_1 = temperature(9, doc="Outside sensor AF1")
    outside_2 = temperature(10, doc="Outside sensor AF2")
    flow_1 = temperature(12, doc="Flow sensor VF1")
    flow_2 = temperature(13, doc="Flow sensor VF2")
    flow_3 = temperature(14, doc="Flow sensor VF3")
    flow_4 = temperature(15, doc="Flow sensor VF4")
    return_1 = temperature(16, doc="Return sensor RüF1")
    return_2 = temperature(17, doc="Return sensor RüF2")
    return_3 = temperature(18, doc="Return sensor RüF3")
    room_1 = temperature(19, doc="Room sensor RF1")
    room_2 = temperature(20, doc="Room sensor RF2")
    room_3 = temperature(21, doc="Room sensor RF3")
    storage_1 = temperature(22, doc="Storage sensor SF1")
    storage_2 = temperature(23, doc="Storage sensor SF2")
    storage_3 = temperature(24, doc="Storage/remote sensor SF3/FG3")
    remote_1 = temperature(25, unit="K", doc="Remote adjuster FG1")
    remote_2 = temperature(26, unit="K", doc="Remote adjuster FG2")


class HeatingCircuit(Component):
    """One space-heating circuit (RK1-3). Construct with ``index`` 1, 2 or 3.

    Addresses follow the controller's offset pattern: the 1000-block steps by
    200 per circuit, mode/control-signal by 2, pumps/manual status by 1.
    """

    mode = RegisterField(
        105, kind="mode", stride=2, writable=True, doc="Operating mode"
    )
    control_signal = RegisterField(
        106, signed=False, stride=2, unit="%", doc="Valve position 0-100%"
    )
    flow_setpoint = temperature(999, stride=200, doc="Current computed flow setpoint")
    flow_max = temperature(1000, stride=200, writable=True, doc="Maximum flow temp")
    flow_min = temperature(1001, stride=200, writable=True, doc="Minimum flow temp")
    room_setpoint_day = temperature(
        1002, stride=200, writable=True, doc="Day room setpoint"
    )
    room_setpoint_night = temperature(
        1003, stride=200, writable=True, doc="Night room setpoint"
    )
    room_setpoint_active = temperature(
        1004, stride=200, doc="Currently active room setpoint"
    )
    slope = RegisterField(
        1005, scale=0.1, stride=200, writable=True, doc="Heating curve slope"
    )
    level = RegisterField(
        1006, scale=0.1, stride=200, writable=True, unit="K", doc="Heating curve level"
    )
    return_slope = RegisterField(1008, scale=0.1, stride=200, doc="Return curve slope")
    return_level = RegisterField(
        1009, scale=0.1, stride=200, unit="K", doc="Return curve level"
    )
    return_max = temperature(1010, stride=200, writable=True, doc="Maximum return temp")
    return_base_point = temperature(1011, stride=200, doc="Return curve base point")
    return_setpoint = temperature(1032, stride=200, doc="Current return setpoint")
    flow_deviation = RegisterField(
        1062, scale=0.1, stride=200, unit="K", doc="Flow control deviation"
    )

    automatic = CoilField(999, stride=200, doc="Time-program controlled")
    day_active = CoilField(1000, stride=200, doc="Day mode active")
    night_active = CoilField(1001, stride=200, doc="Night mode active")
    hold_active = CoilField(1002, stride=200, doc="Hold mode active")
    setback_active = CoilField(1003, stride=200, doc="Setback mode active")
    heat_up_active = CoilField(1004, stride=200, doc="Heat-up mode active")
    return_limit_active = CoilField(1005, stride=200, doc="Return-temp limiting active")
    outside_shutdown = CoilField(1006, stride=200, doc="Outside-temp shutdown active")
    standby = CoilField(1007, stride=200, doc="Standby")
    frost_protection = CoilField(1008, stride=200, doc="Frost protection active")
    pump_running = CoilField(56, stride=1, writable=True, doc="Circulation pump on")
    manual_active = CoilField(4, stride=1, doc="Manual mode active")

    def heating_curve(self, mode: str = "active") -> list[float] | None:
        """Flow-temperature curve over outside temps -20..20 °C.

        ``mode``: ``"active"`` (follow day/night state), ``"day"`` or ``"night"``.
        Returns ``None`` if a required value is missing; pair with
        :data:`curve.OUTSIDE_TEMPERATURES`.
        """
        if mode == "day":
            room = self.room_setpoint_day
        elif mode == "night":
            room = self.room_setpoint_night
        elif self.day_active:
            room = self.room_setpoint_day
        else:
            room = self.room_setpoint_night
        values = (room, self.slope, self.level, self.flow_min, self.flow_max)
        if any(value is None for value in values):
            return None
        return curve.flow_temperatures(
            room_setpoint=room,
            slope=self.slope,
            level=self.level,
            flow_min=self.flow_min,
            flow_max=self.flow_max,
        )

    async def set_mode(self, mode: OperatingMode) -> None:
        """Set the operating mode."""
        await self.write("mode", mode)

    async def set_room_setpoint_day(self, celsius: float) -> None:
        """Set the day room setpoint (°C)."""
        await self.write("room_setpoint_day", celsius)

    async def set_room_setpoint_night(self, celsius: float) -> None:
        """Set the night room setpoint (°C)."""
        await self.write("room_setpoint_night", celsius)


class HotWater(Component):
    """The domestic hot water circuit (HK4 / TW): setpoints and disinfection."""

    mode = RegisterField(111, kind="mode", writable=True, doc="Operating mode")
    setpoint_day = temperature(1799, writable=True, doc="Hot-water setpoint (day)")
    setpoint_active = temperature(1807, doc="Currently active hot-water setpoint")
    setpoint_max = temperature(1800, writable=True, doc="Maximum settable setpoint")
    setpoint_min = temperature(1801, writable=True, doc="Minimum settable setpoint")
    hysteresis = RegisterField(
        1802, scale=0.1, unit="K", writable=True, doc="Switching hysteresis"
    )
    charge_overshoot = RegisterField(
        1803, scale=0.1, unit="K", writable=True, doc="Charging temp overshoot"
    )
    max_charge_temp = temperature(1805, writable=True, doc="Maximum charge temp")
    hold_value = temperature(1806, writable=True, doc="Hold (minimum) temperature")
    active_charge_setpoint = temperature(1837, doc="Active charging setpoint")
    return_max = temperature(1827, writable=True, doc="Maximum return temperature")
    disinfection_temp = temperature(1829, writable=True, doc="Disinfection temperature")
    disinfection_weekday = RegisterField(
        1830, kind="weekday", writable=True, doc="Disinfection weekday"
    )
    disinfection_start = RegisterField(
        1831, kind="time", writable=True, doc="Disinfection start time"
    )
    disinfection_stop = RegisterField(
        1832, kind="time", writable=True, doc="Disinfection stop time"
    )
    disinfection_hold = RegisterField(
        1838, unit="min", writable=True, doc="Disinfection hold duration"
    )

    automatic = CoilField(1799, doc="Time-program controlled")
    disinfection_active = CoilField(1800, doc="Thermal disinfection running")
    priority = CoilField(1801, doc="Hot-water priority active")
    max_charge_limit_active = CoilField(1802, doc="Max charge-temp limiting active")
    return_limit_active = CoilField(1803, doc="Return-temp limiting active")
    standby = CoilField(1804, doc="Standby")
    frost_protection = CoilField(1805, doc="Frost protection active")
    forced_charge = CoilField(1806, writable=True, doc="Force a storage charge")
    solar_pump_running = CoilField(1807, doc="Solar circuit pump on")
    charge_pump_running = CoilField(59, writable=True, doc="Storage charge pump on")
    circulation_pump_running = CoilField(60, writable=True, doc="Circulation pump on")
    manual_active = CoilField(7, doc="Manual mode active")

    @property
    def charging(self) -> bool | None:
        """Whether the storage is currently being charged."""
        return self.charge_pump_running

    async def set_setpoint(self, celsius: float) -> None:
        """Set the hot-water day setpoint (°C)."""
        await self.write("setpoint_day", celsius)

    async def set_mode(self, mode: OperatingMode) -> None:
        """Set the operating mode."""
        await self.write("mode", mode)

    async def start_forced_charge(self) -> None:
        """Trigger a one-off storage charge."""
        await self.write("forced_charge", True)
