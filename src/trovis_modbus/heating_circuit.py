"""A space-heating circuit (RK1-3)."""

from __future__ import annotations

from . import utils
from .enums import OperatingMode
from .model import TrovisComponent, coil, enum, gauge, integer, temperature
from .options import OPERATING_MODE_OPTIONS


class HeatingCircuit(TrovisComponent):
    """One heating circuit.

    Construct with ``index`` 1, 2 or 3. Addresses follow the controller's offset
    pattern: the 1000-block steps by 200 per circuit, mode/control-signal by 2,
    pumps/manual status by 1.
    """

    ### registers

    mode = enum(
        40106,
        OperatingMode,
        stride=2,
        writable=True,
        options=OPERATING_MODE_OPTIONS,
        maker_key="BetriebsArt_Rk1",
        maker_category="ALG-BTR",
        description="Betriebsart Rk",
    )

    valve_setpoint = integer(
        40107,
        signed=False,
        stride=2,
        unit="%",
        maker_key="Stellsignal_Rk1",
        maker_category="ALG-BTR",
        description="Stellsignal Rk",
    )

    flow_setpoint = temperature(41000, stride=200)
    flow_max = temperature(41001, stride=200, writable=True)
    flow_min = temperature(41002, stride=200, writable=True)

    room_setpoint_day = temperature(
        41003,
        stride=200,
        writable=True,
        min_value=0,
        max_value=40,
        digits=1,
        maker_key="Tag_Soll_Rk1",
        maker_category="SOL-RT",
        description="Raumsollwert Tag",
    )

    room_setpoint_night = temperature(
        41004,
        stride=200,
        writable=True,
        min_value=0,
        max_value=40,
        digits=1,
        maker_key="Nacht_Soll_Rk1",
        maker_category="SOL-RT",
        description="Raumsollwert Nacht",
    )

    room_setpoint_active = temperature(41005, stride=200)

    slope = gauge(
        41006,
        0.1,
        stride=200,
        writable=True,
        min_value=0.2,
        max_value=3.2,
        digits=1,
        maker_key="Steig_HeizKL_Rk1",
        maker_category="KNL-VL",
        description="Steigung VL Heizkennlinie",
    )

    level = gauge(
        41007,
        0.1,
        stride=200,
        writable=True,
        min_value=-30,
        max_value=30,
        digits=1,
        unit="K",
        maker_key="Niv_HeizKL_Rk1",
        maker_category="KNL-VL",
        description="Niveau VL Heizkennlinie",
    )

    return_slope = gauge(41009, 0.1, stride=200)
    return_level = gauge(41010, 0.1, stride=200, unit="K")
    return_max = temperature(41011, stride=200, writable=True)
    return_base_point = temperature(41012, stride=200)
    return_setpoint = temperature(41033, stride=200)

    flow_deviation = gauge(41063, 0.1, stride=200, unit="K")

    ### coils

    manual_active = coil(5, stride=1)
    pump_running = coil(57, stride=1, writable=True)
    room_control_unit = coil(703, stride=1, writable=True)

    automatic = coil(1000, stride=200)
    day_active = coil(1001, stride=200)
    night_active = coil(1002, stride=200)
    hold_active = coil(1003, stride=200)
    setback_active = coil(1004, stride=200)
    heat_up_active = coil(1005, stride=200)
    return_limit_active = coil(1006, stride=200)
    outside_shutdown = coil(1007, stride=200)
    standby = coil(1008, stride=200)
    frost_protection = coil(1009, stride=200)

    optimization = coil(
        2107,
        stride=100,
        writable=True,
        maker_key="FB07_Optimierung_Rk1",
        description="Optimierung Rk",
    )
    adaptation = coil(
        2108,
        stride=100,
        writable=True,
        maker_key="FB08_Adaption_Rk1",
        description="Adaption Rk",
    )

    # Override coils (mode 89+2n, pump 96+1n) released before a write.
    ebene_coils = {"mode": (89, 2), "pump_running": (96, 1)}

    def heating_curve(self, mode: str = "active") -> list[float] | None:
        """Flow-temperature curve over outside temps -20..20 °C.

        ``mode``: ``"active"`` (follow day/night state), ``"day"`` or
        ``"night"``. Returns ``None`` if a required value is missing.
        """
        if mode == "day" or (mode == "active" and self.day_active):
            room = self.room_setpoint_day
        else:
            room = self.room_setpoint_night

        slope, level = self.slope, self.level
        flow_min, flow_max = self.flow_min, self.flow_max

        if None in (room, slope, level, flow_min, flow_max):
            return None

        return utils.heating_curve(
            room_setpoint=room,  # type: ignore[arg-type]
            slope=slope,  # type: ignore[arg-type]
            level=level,  # type: ignore[arg-type]
            flow_min=flow_min,  # type: ignore[arg-type]
            flow_max=flow_max,  # type: ignore[arg-type]
        )

    async def set_mode(self, mode: OperatingMode) -> None:
        """Set the operating mode."""
        await self.async_write_datapoint("mode", mode)

    async def set_room_setpoint_day(self, celsius: float) -> None:
        """Set the day room setpoint (°C)."""
        await self.async_write_datapoint("room_setpoint_day", celsius)

    async def set_room_setpoint_night(self, celsius: float) -> None:
        """Set the night room setpoint (°C)."""
        await self.async_write_datapoint("room_setpoint_night", celsius)