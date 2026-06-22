"""Fixtures: a real Modbus TCP server preloaded with Trovis-shaped values."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator

import pytest
from modbus_connection.pymodbus import connect_tcp
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
from pymodbus.server import ModbusTcpServer

from trovis_modbus import Trovis557x

UNIT_ID = 1

# Raw register words keyed by address (decoded view documented inline).
HOLDING: dict[int, int] = {
    0: 5579,  # model
    1: 21,  # system -> 2.1
    2: 305,  # firmware -> 3.05
    3: 110,  # hardware -> 1.10
    5: 12345,  # serial
    9: 123,  # outside_1 -> 12.3
    12: 0x10000 - 50,  # flow_1 -> -5.0 (signed)
    22: 450,  # storage_1 -> 45.0
    23: 0x7FFF,  # storage_2 -> NaN -> None
    98: 900,  # max flow setpoint -> 90.0
    99: 1430,  # time -> 14:30
    100: 2106,  # date -> 21.06
    101: 2026,  # year
    102: 1,  # switch_top -> AUTOMATIC
    105: 1,  # hc1 mode -> AUTOMATIC
    106: 42,  # hc1 control signal -> 42 %
    112: 1505,  # summer start -> 15.05
    149: 0,  # error status
    999: 550,  # hc1 flow_setpoint -> 55.0
    1000: 800,  # hc1 flow_max -> 80.0
    1001: 200,  # hc1 flow_min -> 20.0
    1002: 210,  # hc1 room_setpoint_day -> 21.0
    1003: 180,  # hc1 room_setpoint_night -> 18.0
    1004: 210,  # hc1 room_setpoint_active -> 21.0
    1005: 12,  # hc1 slope -> 1.2
    1006: 0,  # hc1 level -> 0.0
    1199: 480,  # hc2 flow_setpoint -> 48.0
    1799: 500,  # hot_water setpoint_day -> 50.0
    1807: 500,  # hot_water setpoint_active -> 50.0
    1837: 670,  # hot_water active_charge_setpoint -> 67.0
    1830: 3,  # disinfection weekday -> WEDNESDAY
    1831: 1900,  # disinfection start -> 19:00
}

COILS: dict[int, bool] = {
    56: True,  # hc1 pump
    999: True,  # hc1 automatic
    1000: True,  # hc1 day active
    1799: True,  # hot_water automatic
    59: True,  # hot_water charge pump
}


def _block(
    mapping: dict[int, int | bool], size: int = 2100
) -> ModbusSequentialDataBlock:
    values = [0] * (size + 1)
    for address, value in mapping.items():
        values[address + 1] = int(value)  # pymodbus datastore is 1-based
    return ModbusSequentialDataBlock(0, values)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def trovis() -> AsyncIterator[Trovis557x]:
    device = ModbusDeviceContext(
        co=_block(COILS), hr=_block(HOLDING), di=_block({}), ir=_block({})
    )
    context = ModbusServerContext(devices={UNIT_ID: device}, single=False)
    host, port = "127.0.0.1", _free_port()
    server = ModbusTcpServer(context, address=(host, port))
    task = asyncio.create_task(server.serve_forever())
    for _ in range(100):
        try:
            _, writer = await asyncio.open_connection(host, port)
        except OSError:
            await asyncio.sleep(0.02)
            continue
        writer.close()
        await writer.wait_closed()
        break

    conn = await connect_tcp(host, port=port)
    try:
        yield Trovis557x(conn.for_unit(UNIT_ID))
    finally:
        await conn.close()
        await server.shutdown()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
