"""End-to-end tests of the object model over the in-memory mock backend."""

from __future__ import annotations

from datetime import date, time

import pytest
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from trovis_modbus import MonthDay, OperatingMode, Trovis557x, Weekday
from trovis_modbus.ranges import REGISTER_RANGES

from .conftest import COILS, HOLDING


class _CountingUnit:
    """Wraps a ModbusUnit and records read calls; delegates everything else."""

    def __init__(self, inner: MockModbusUnit) -> None:
        self._inner = inner
        self.register_blocks: list[tuple[int, int]] = []
        self.coil_blocks: list[tuple[int, int]] = []

    @property
    def register_reads(self) -> int:
        return len(self.register_blocks)

    @property
    def coil_reads(self) -> int:
        return len(self.coil_blocks)

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        self.register_blocks.append((address, count))
        return await self._inner.read_holding_registers(address, count)

    async def read_coils(self, address: int, count: int) -> list[bool]:
        self.coil_blocks.append((address, count))
        return await self._inner.read_coils(address, count)

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


async def test_device_info(trovis: Trovis557x) -> None:
    await trovis.async_update()
    info = trovis.info
    assert info.manufacturer == "Samson"
    assert info.model == "Trovis 5579"  # shaped inline by the property
    assert info.serial_number == "12345"
    assert info.firmware_version == "3.05"


async def test_sensors(trovis: Trovis557x) -> None:
    await trovis.async_update()
    assert trovis.sensors.outside_1 == pytest.approx(12.3)
    # Per-circuit / storage sensors live on their components now.
    assert trovis.heating_circuit_1.flow_temperature == pytest.approx(-5.0)  # signed
    assert trovis.heating_circuit_1.room_temperature == pytest.approx(20.0)
    assert trovis.hot_water.storage_temperature == pytest.approx(45.0)
    assert trovis.hot_water.storage_temperature_lower is None  # NaN sentinel


async def test_clock(trovis: Trovis557x) -> None:
    await trovis.async_update()
    assert trovis.clock.time == time(14, 30)
    assert trovis.clock.date == date(2026, 6, 21)
    assert trovis.clock.datetime.isoformat() == "2026-06-21T14:30:00"


async def test_controller(trovis: Trovis557x) -> None:
    await trovis.async_update()
    assert trovis.controller.switch_top is OperatingMode.AUTOMATIC
    assert trovis.controller.max_flow_setpoint == pytest.approx(90.0)
    assert trovis.controller.summer_start == MonthDay(day=15, month=5)


async def test_heating_circuit_reads(trovis: Trovis557x) -> None:
    await trovis.async_update()
    hc1 = trovis.heating_circuit_1
    assert hc1.mode is OperatingMode.AUTOMATIC
    assert hc1.control_signal == 42
    assert hc1.flow_setpoint == pytest.approx(55.0)
    assert hc1.room_setpoint_active == pytest.approx(21.0)
    assert hc1.pump_running is True
    assert hc1.day_active is True
    assert hc1.automatic is True


async def test_circuit_offset_pattern(trovis: Trovis557x) -> None:
    """Circuit 2 reads its own (+200) registers."""
    await trovis.async_update()
    assert trovis.heating_circuit_2.flow_setpoint == pytest.approx(48.0)
    assert trovis.heating_circuit_1.flow_setpoint == pytest.approx(55.0)


async def test_heating_curve(trovis: Trovis557x) -> None:
    await trovis.async_update()
    curve = trovis.heating_circuit_1.heating_curve()
    assert curve is not None and len(curve) == 41
    # day active, room 21, slope 1.2, level 0, clamp [20, 80]
    assert curve[-1] == pytest.approx(26.4)  # outside +20 °C
    assert trovis.heating_circuit_1.heating_curve("night") is not None


async def test_hot_water(trovis: Trovis557x) -> None:
    await trovis.async_update()
    hw = trovis.hot_water
    assert hw.setpoint_day == pytest.approx(50.0)
    assert hw.setpoint_active == pytest.approx(50.0)
    assert hw.active_charge_setpoint == pytest.approx(67.0)
    assert hw.disinfection_weekday is Weekday.WEDNESDAY
    assert hw.disinfection_start == time(19, 0)
    assert hw.automatic is True
    assert hw.charging is True  # charge pump running


async def test_independent_component_update(trovis: Trovis557x) -> None:
    """A sub-system refreshes on its own, without the rest."""
    await trovis.hot_water.async_update()
    assert trovis.hot_water.setpoint_day == pytest.approx(50.0)
    assert trovis.heating_circuit_1.flow_setpoint is None  # not updated yet


async def test_full_update_consolidates_reads() -> None:
    """A full device update pools all sub-systems into a few block reads."""
    inner = MockModbusConnection().for_unit(1)
    inner.holding.update(HOLDING)
    inner.coils.update(COILS)
    unit = _CountingUnit(inner)
    device = Trovis557x(unit)  # type: ignore[arg-type]

    field_count = sum(
        len(c._register_fields) + len(c._coil_fields) for c in device.components
    )
    await device.async_update()

    # 155 fields collapse into ~18 range-aware block reads — far fewer than the
    # field count, and well under the ~40 a per-component update would issue.
    total_reads = unit.register_reads + unit.coil_reads
    assert total_reads < field_count // 4
    assert unit.register_reads <= 12
    assert unit.coil_reads <= 8


async def test_full_update_never_reads_across_an_unreadable_gap() -> None:
    """Every block stays inside the controller's readable ranges (no NAK risk)."""
    inner = MockModbusConnection().for_unit(1)
    unit = _CountingUnit(inner)
    device = Trovis557x(unit)  # type: ignore[arg-type]
    await device.async_update()

    def readable(address: int) -> bool:
        return any(low <= address <= high for low, high in REGISTER_RANGES)

    for start, count in unit.register_blocks:
        assert all(readable(start + i) for i in range(count)), (
            f"block {start}..{start + count - 1} crosses an unreadable gap"
        )
    # Addresses 7-8 (between ranges [0,6] and [9,40]) are never read — the low
    # registers split there instead of being merged into one 0..26 block.
    read = {start + i for start, count in unit.register_blocks for i in range(count)}
    assert 7 not in read and 8 not in read


async def test_consolidated_reads_decode_correctly() -> None:
    """Interleaved per-circuit registers decode to the right circuit after pooling."""
    inner = MockModbusConnection().for_unit(1)
    # flow sensors VF1/VF2/VF3 are at adjacent addresses 12/13/14 — fetched in one
    # block, then distributed to circuits 1/2/3.
    inner.holding.update({12: 100, 13: 200, 14: 300})
    unit = _CountingUnit(inner)
    device = Trovis557x(unit)  # type: ignore[arg-type]

    await device.async_update()

    assert device.heating_circuit_1.flow_temperature == pytest.approx(10.0)
    assert device.heating_circuit_2.flow_temperature == pytest.approx(20.0)
    assert device.heating_circuit_3.flow_temperature == pytest.approx(30.0)


async def test_update_listener(trovis: Trovis557x) -> None:
    calls: list[int] = []
    unsubscribe = trovis.hot_water.add_update_listener(lambda: calls.append(1))
    await trovis.hot_water.async_update()
    await trovis.hot_water.async_update()
    assert len(calls) == 2
    unsubscribe()
    await trovis.hot_water.async_update()
    assert len(calls) == 2  # no longer notified


async def test_write_roundtrip(trovis: Trovis557x) -> None:
    await trovis.async_update()
    await trovis.heating_circuit_1.set_room_setpoint_day(21.5)
    await trovis.hot_water.set_setpoint(52.0)
    await trovis.heating_circuit_1.async_update()
    await trovis.hot_water.async_update()
    assert trovis.heating_circuit_1.room_setpoint_day == pytest.approx(21.5)
    assert trovis.hot_water.setpoint_day == pytest.approx(52.0)


async def test_write_rejects_readonly(trovis: Trovis557x) -> None:
    with pytest.raises(AttributeError):
        await trovis.heating_circuit_1.write("flow_setpoint", 50.0)


async def test_mode_write_releases_override_coil(trovis: Trovis557x) -> None:
    """Setting the mode first releases the Ebene coil (0 = remote control)."""
    unit = trovis.heating_circuit_1._unit
    await unit.write_coil(88, True)  # start "autonomous" (controller-controlled)

    await trovis.heating_circuit_1.set_mode(OperatingMode.DAY)

    # Override coil 88 (EBNBetrArtRk1) released to 0, then mode register written.
    assert (await unit.read_coils(88, 1))[0] is False
    assert (await unit.read_holding_registers(105, 1))[0] == int(OperatingMode.DAY)


async def test_circuit2_mode_uses_strided_override(trovis: Trovis557x) -> None:
    """Circuit 2's override coil follows the +2 stride (90, not 88)."""
    unit = trovis.heating_circuit_2._unit
    await unit.write_coil(90, True)
    await trovis.heating_circuit_2.set_mode(OperatingMode.NIGHT)
    assert (await unit.read_coils(90, 1))[0] is False
    assert (await unit.read_holding_registers(107, 1))[0] == int(OperatingMode.NIGHT)
