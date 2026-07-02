"""The top-level Trovis557x device object."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from modbus_connection.model import Component, ComponentGroup

from .addresses import register_address
from .clock import Clock
from .controller import Controller
from .device_info import DeviceInformation
from .heating_circuit import HeatingCircuit
from .hot_water import HotWater
from .model import (
    DEFAULT_WRITE_ACCESS_CODE,
    async_disable_writing,
    async_enable_writing,
    async_read_writing_enabled,
)
from .ranges import heating_circuit_count, ranges_for_model
from .sensors import Sensors

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit


@dataclass(frozen=True)
class TrovisProbe:
    """Result of the safe setup probe."""

    model: int
    detected_sensors: tuple[str, ...]

    @property
    def model_name(self) -> str:
        """Return the user-facing model name."""
        return f"Trovis {self.model}"


class Trovis557x:
    """A Samson TROVIS 557x heating controller."""

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        model: int = 5578,
        detected_sensors: Iterable[str] = (),
    ) -> None:
        self._unit = unit
        self.model = model
        self.detected_sensors = frozenset(detected_sensors)

        self.info = DeviceInformation(unit)
        self.controller = Controller(unit)
        self.clock = Clock(unit)
        self.sensors = Sensors(unit)

        self.heating_circuit_1 = HeatingCircuit(unit, index=1)
        self.heating_circuit_2 = HeatingCircuit(unit, index=2)
        self.heating_circuit_3 = HeatingCircuit(unit, index=3)

        self.hot_water = HotWater(unit)
        self._writing_enabled = False

        all_components = (
            self.info,
            self.controller,
            self.clock,
            self.sensors,
            self.heating_circuit_1,
            self.heating_circuit_2,
            self.heating_circuit_3,
            self.hot_water,
        )

        register_ranges, coil_ranges = ranges_for_model(model)
        for component in all_components:
            component.register_ranges = register_ranges
            component.coil_ranges = coil_ranges

        self._heating_circuits = (
            self.heating_circuit_1,
            self.heating_circuit_2,
            self.heating_circuit_3,
        )[:heating_circuit_count(model)]

        self._group = ComponentGroup(unit, self.components)

    @classmethod
    async def async_probe(cls, unit: ModbusUnit) -> TrovisProbe:
        """Read only safe identity and sensor data for setup."""
        model = int(
            (
                await unit.read_holding_registers(
                    register_address(40001),
                    1,
                )
            )[0]
        )

        register_ranges, coil_ranges = ranges_for_model(model)

        sensors = Sensors(unit)
        sensors.register_ranges = register_ranges
        sensors.coil_ranges = coil_ranges
        await sensors.async_update()

        return TrovisProbe(
            model=model,
            detected_sensors=sensors.detected_sensor_names,
        )

    @property
    def heating_circuits(self) -> tuple[HeatingCircuit, ...]:
        """Return the built-in heating circuits for this model."""
        return self._heating_circuits

    @property
    def heating_circuit_indices(self) -> tuple[int, ...]:
        """Return the available heating-circuit indices."""
        return tuple(range(1, len(self._heating_circuits) + 1))

    @property
    def components(self) -> tuple[Component, ...]:
        """Return every actively polled subsystem."""
        return (
            self.info,
            self.controller,
            self.clock,
            self.sensors,
            *self.heating_circuits,
            self.hot_water,
        )

    @property
    def writing_enabled(self) -> bool:
        """Whether writing is enabled by the integration safety switch."""
        return self._writing_enabled

    async def async_update(self) -> None:
        """Refresh all active subsystems in pooled Modbus reads."""
        await self._group.async_update()

    async def async_read_writing_enabled(self) -> bool:
        """Read the current write-enabled state directly from the controller."""
        return await async_read_writing_enabled(self._unit)

    async def async_enable_writing(
        self,
        access_code: int = DEFAULT_WRITE_ACCESS_CODE,
    ) -> None:
        """Enable TROVIS writing globally."""
        await async_enable_writing(self._unit, access_code)
        self._writing_enabled = True

    async def async_disable_writing(self) -> None:
        """Disable TROVIS writing globally."""
        try:
            await async_disable_writing(self._unit)
        finally:
            self._writing_enabled = False