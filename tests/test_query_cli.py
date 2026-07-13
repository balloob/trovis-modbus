"""Light tests for the script/query.py CLI (no real backend needed)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from modbus_connection.cli_helper import field_rows
from modbus_connection.mock import MockModbusUnit

from trovis_modbus import MonthDay, Trovis557x

_SPEC = importlib.util.spec_from_file_location(
    "trovis_query", Path(__file__).resolve().parents[1] / "script" / "query.py"
)
assert _SPEC and _SPEC.loader
query = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(query)


def test_month_day_renders_as_day_dot_month() -> None:
    """The dump prints values with str(), so MonthDay carries its own format."""
    assert str(MonthDay(day=15, month=5)) == "15.05"


def test_parse_args_tcp() -> None:
    args = query._parse_args(["tcp", "1.2.3.4", "--unit", "246"])
    assert args.transport == "tcp"
    assert args.host == "1.2.3.4"
    assert args.unit == 246
    assert args.port == 502
    assert args.framer == "rtu"  # RTU-over-TCP default for Trovis gateways


def test_parse_args_serial() -> None:
    args = query._parse_args(["serial", "/dev/ttyUSB0", "--unit", "1"])
    assert args.transport == "serial"
    assert args.device == "/dev/ttyUSB0"
    assert args.unit == 1
    assert args.baudrate == 19200  # Trovis serial default


def test_values_lists_every_subsystem_field(mock_modbus_unit: MockModbusUnit) -> None:
    """Each sub-system's public fields are enumerated, methods excluded."""
    device = Trovis557x(mock_modbus_unit)

    circuit_rows = field_rows(device.heating_circuit_1)
    circuit_names = {name for name, _value in circuit_rows}

    assert {"mode", "pump_running", "room_setpoint_active"} <= circuit_names
    assert "flow_temperature" not in circuit_names
    assert "return_temperature" not in circuit_names
    assert "room_temperature" not in circuit_names

    sensor_rows = field_rows(device.sensors)
    sensor_names = {name for name, _value in sensor_rows}

    assert {
        "af1",
        "af2",
        "vf1",
        "vf2",
        "vf3",
        "vf4",
        "ruef1",
        "ruef2",
        "ruef3",
        "rf1",
        "rf2",
        "rf3",
        "sf1",
        "sf2",
        "sf3_fg3",
        "fg1",
        "fg2",
    } <= sensor_names

    # Methods / private helpers are not data rows.
    assert "heating_curve" not in circuit_names
    assert "async_update" not in circuit_names
    assert all(not n.startswith("_") for n in circuit_names)
    assert all(not n.startswith("_") for n in sensor_names)


def test_print_runs(
    capsys: pytest.CaptureFixture[str], mock_modbus_unit: MockModbusUnit
) -> None:
    device = Trovis557x(mock_modbus_unit)
    query._print(device)
    out = capsys.readouterr().out
    assert "Device" in out
    assert "Heating circuit 1" in out
    assert "Hot water" in out
