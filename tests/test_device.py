"""End-to-end tests of the object model over a real Modbus server."""

from __future__ import annotations

from datetime import date, time

import pytest

from trovis_modbus import OperatingMode, Trovis557x, Weekday
from trovis_modbus.components import MonthDay


async def test_device_info(trovis: Trovis557x) -> None:
    await trovis.async_update()
    assert trovis.info.model == 5579
    assert trovis.info.firmware_version == pytest.approx(3.05)
    info = trovis.device_info
    assert info.manufacturer == "Samson"
    assert info.model == "Trovis 5579"
    assert info.serial_number == "12345"
    assert info.firmware_version == "3.05"


async def test_sensors(trovis: Trovis557x) -> None:
    await trovis.async_update()
    assert trovis.sensors.outside_1 == pytest.approx(12.3)
    assert trovis.sensors.flow_1 == pytest.approx(-5.0)  # signed
    assert trovis.sensors.storage_1 == pytest.approx(45.0)
    assert trovis.sensors.storage_2 is None  # NaN sentinel


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
