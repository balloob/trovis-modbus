# trovis-modbus

A standalone Python library that reads a **Samson Trovis 557x** heating
controller over Modbus, exposed as a normal, object-oriented Python API.

Addresses, scales and data types are taken from the canonical Trovis 557x point
list (the [Tom-Bom-badil](https://github.com/Tom-Bom-badil/samson_trovis_557x)
SmartHomeNG plugin) and **verified in tests** against a vendored copy of that
table (`tests/reference/canonical_points.json`).

## Design

- It **consumes the connection abstraction**, not a backend: the API takes a
  [`modbus_connection.ModbusUnit`](../modbus-connection) and reads/writes through
  it. You choose the backend (pymodbus, tmodbus, …).
- A `Trovis557x` is a tree of independently-updatable **sub-systems**, each a
  `Component` that knows its own registers:

  | Attribute | What |
  | --- | --- |
  | `info` | model, firmware/hardware version, serial → `DeviceInfo` |
  | `controller` | faults, rotary switches, summer mode, frost limit, locks |
  | `clock` | date/time as native `datetime` objects |
  | `sensors` | every temperature input (outside, flow, return, room, storage, remote) |
  | `heating_circuit_1` / `_2` / `_3` | space-heating circuits (RK1-3) |
  | `hot_water` | domestic hot water (HK4): setpoints, charging, disinfection |

- Each sub-system can refresh on its own and has its **own update listeners**, so
  a single Home Assistant entity can subscribe to just the part it shows
  (e.g. one climate entity per heating circuit).
- Units of measurement live in each property's docstring, not in the value.

## Use

```python
import asyncio
from modbus_connection.pymodbus import connect_tcp
from trovis_modbus import Trovis557x, OperatingMode


async def main() -> None:
    conn = await connect_tcp("192.168.1.50", port=502)
    try:
        trovis = Trovis557x(conn.for_unit(1))     # unit 1 = the controller's Modbus address
        await trovis.async_update()

        print("Outside:", trovis.sensors.outside_1, "°C")
        print("HK1 mode:", trovis.heating_circuit_1.mode)
        print("HK1 target:", trovis.heating_circuit_1.room_setpoint_active, "°C")
        print("HK1 pump:", trovis.heating_circuit_1.pump_running)
        print("HK1 curve:", trovis.heating_circuit_1.heating_curve())
        print("Hot water:", trovis.hot_water.setpoint_active, "charging:", trovis.hot_water.charging)
        print("Clock:", trovis.clock.datetime)

        # Writes (reverse the scaling/encoding automatically)
        await trovis.heating_circuit_1.set_room_setpoint_day(21.5)
        await trovis.heating_circuit_1.set_mode(OperatingMode.DAY)
        await trovis.hot_water.start_forced_charge()
    finally:
        await conn.close()


asyncio.run(main())
```

### Updating just one sub-system

```python
await trovis.hot_water.async_update()              # only reads the HK4 registers
unsub = trovis.hot_water.add_update_listener(refresh_my_entity)
```

## Develop / test

```bash
uv sync
uv run pytest
```

The suite cross-checks every field against the canonical point list and
exercises decoding, the heating curve, writes and listeners against a real
in-process Modbus server.

Formatting/linting is [ruff](https://docs.astral.sh/ruff/); install the commit
hook with [prek](https://github.com/j178/prek):

```bash
uvx prek install
uvx prek run --all-files
```
