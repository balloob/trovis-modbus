#!/usr/bin/env python3
"""Query a Samson Trovis 557x over Modbus and print every value.

Connects over Modbus TCP (a network gateway) or a serial/USB port, reads the
whole device once, and dumps every sub-system's values to the terminal. Handy for
checking a real controller without Home Assistant.

The library only needs the connection *protocol*; this script picks the pymodbus
backend, so run it with the ``cli`` extra::

    uv run --extra cli python script/query.py tcp 192.168.1.50 --unit 246
    uv run --extra cli python script/query.py serial /dev/ttyUSB0 --unit 246
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import sys
import time
from enum import IntEnum
from typing import cast

from modbus_connection import ModbusConnection, ModbusError, ModbusUnit
from modbus_connection.model import Component, RegisterField

from trovis_modbus import MonthDay, Trovis557x

# (label, attribute name on Trovis557x) — the order things are printed.
SECTIONS: list[tuple[str, str]] = [
    ("Device", "info"),
    ("Controller", "controller"),
    ("Clock", "clock"),
    ("Sensors", "sensors"),
    ("Heating circuit 1", "heating_circuit_1"),
    ("Heating circuit 2", "heating_circuit_2"),
    ("Heating circuit 3", "heating_circuit_3"),
    ("Hot water", "hot_water"),
]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="transport", required=True)

    # Shared options available on each transport (so `--unit` can follow the host).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--unit",
        type=int,
        default=246,
        help="Modbus unit/station address (default: 246)",
    )

    tcp = sub.add_parser(
        "tcp", parents=[common], help="connect over Modbus TCP (network gateway)"
    )
    tcp.add_argument("host", help="hostname or IP of the gateway/device")
    tcp.add_argument("--port", type=int, default=502, help="TCP port (default: 502)")
    tcp.add_argument(
        "--framer",
        choices=("rtu", "socket"),
        default="rtu",
        help=(
            "wire framing: 'rtu' for RTU-over-TCP (transparent serial gateways, "
            "the Trovis default) or 'socket' for native Modbus TCP (default: rtu)"
        ),
    )

    serial = sub.add_parser(
        "serial", parents=[common], help="connect over a serial/USB port"
    )
    serial.add_argument("device", help="serial device, e.g. /dev/ttyUSB0")
    serial.add_argument("--baudrate", type=int, default=19200, help="default: 19200")
    serial.add_argument("--parity", choices=("N", "E", "O"), default="N")
    serial.add_argument("--stopbits", type=int, choices=(1, 2), default=1)
    serial.add_argument("--bytesize", type=int, choices=(7, 8), default=8)

    return parser.parse_args(argv)


async def _open(args: argparse.Namespace) -> ModbusConnection:
    # Imported here so the module loads (and --help works) without a backend.
    from modbus_connection.pymodbus import connect_serial, connect_tcp

    if args.transport == "serial":
        return await connect_serial(
            args.device,
            baudrate=args.baudrate,
            parity=args.parity,
            stopbits=args.stopbits,
            bytesize=args.bytesize,
        )
    return await connect_tcp(args.host, port=args.port, framer=args.framer)


class _CountingUnit:
    """Wraps a ModbusUnit to count the Modbus reads it performs."""

    def __init__(self, unit: ModbusUnit) -> None:
        self._unit = unit
        self.reads = 0

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        self.reads += 1
        return await self._unit.read_input_registers(address, count)

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        self.reads += 1
        return await self._unit.read_holding_registers(address, count)

    async def read_coils(self, address: int, count: int) -> list[bool]:
        self.reads += 1
        return await self._unit.read_coils(address, count)

    async def read_discrete_inputs(self, address: int, count: int) -> list[bool]:
        self.reads += 1
        return await self._unit.read_discrete_inputs(address, count)

    def __getattr__(self, name: str) -> object:
        return getattr(self._unit, name)


def _format(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, MonthDay):
        return f"{value.day:02d}.{value.month:02d}"
    if isinstance(value, IntEnum):
        return value.name.lower()
    return str(value)


def _values(component: Component) -> list[tuple[str, str, str]]:
    """Public (name, value, unit) rows for a sub-system."""
    rows: list[tuple[str, str, str]] = []
    cls = type(component)
    for name in dir(component):
        if name.startswith("_"):
            continue
        static = inspect.getattr_static(cls, name, None)
        # Skip methods/coroutines; keep RegisterField/CoilField descriptors,
        # properties, and plain class constants (e.g. manufacturer).
        if callable(static) and not isinstance(static, property):
            continue
        value = getattr(component, name)
        if callable(value):
            continue
        unit = static.unit or "" if isinstance(static, RegisterField) else ""
        rows.append((name, _format(value), unit))
    return rows


def _print(device: Trovis557x) -> None:
    for label, attr in SECTIONS:
        component = getattr(device, attr)
        rows = _values(component)
        print(f"\n{label}")
        print("-" * len(label))
        width = max((len(name) for name, _, _ in rows), default=0)
        for name, value, unit in rows:
            suffix = f" {unit}" if unit and value != "—" else ""
            print(f"  {name:<{width}}  {value}{suffix}")


async def _run(args: argparse.Namespace) -> int:
    try:
        connection = await _open(args)
    except ModbusError as err:
        print(f"Could not connect: {err}", file=sys.stderr)
        return 1
    counting = _CountingUnit(connection.for_unit(args.unit))
    try:
        device = Trovis557x(cast(ModbusUnit, counting))
        start = time.monotonic()
        await device.async_update()
        elapsed = time.monotonic() - start
    except ModbusError as err:
        print(f"Error reading device: {err}", file=sys.stderr)
        return 1
    finally:
        await connection.close()
    _print(device)
    print(f"\nQueried in {elapsed * 1000:.0f} ms ({counting.reads} Modbus reads)")
    return 0


def main() -> int:
    return asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
