#!/usr/bin/env python3
"""Query a Samson Trovis 557x over Modbus and print every value.

Connects over Modbus TCP (a network gateway) or a serial/USB port, reads the
whole device once, and dumps every sub-system's values to the terminal. Handy for
checking a real controller without Home Assistant.

The library only needs the connection *protocol*; ``connect_from_args`` uses
whichever backend is installed (tmodbus, else pymodbus), so run it with the
``cli`` extra to pull in pymodbus::

    uv run --extra cli python script/query.py 192.168.1.50 --unit 246
    uv run --extra cli python script/query.py /dev/ttyUSB0 --transport serial --unit 246
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import sys
import time
from enum import IntEnum

from modbus_connection import ModbusError
from modbus_connection.cli_helper import (
    CountingUnit,
    add_connection_args,
    connect_from_args,
)
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
    # Trovis controllers are RS-485 RTU devices, reached directly or through a
    # transparent (RTU-over-TCP) gateway; 'socket' framing covers a protocol-
    # converting gateway that presents native Modbus TCP.
    add_connection_args(
        parser,
        connections=(("tcp", "rtu"), ("tcp", "socket"), ("serial", "rtu")),
    )
    # The unit id is per-device, not part of connecting, so the CLI adds it.
    parser.add_argument(
        "--unit",
        type=int,
        default=246,
        help="Modbus unit/station address (default: 246)",
    )
    # Override the helper's generic defaults with the Trovis line settings: RTU
    # framing (the gateway default) and 19200 baud on serial.
    parser.set_defaults(framer="rtu", baudrate=19200)
    return parser.parse_args(argv)


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
        connection = await connect_from_args(args)
    except ModbusError as err:
        print(f"Could not connect: {err}", file=sys.stderr)
        return 1
    counting = CountingUnit(connection.for_unit(args.unit))
    try:
        device = Trovis557x(counting)
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
