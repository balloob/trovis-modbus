# trovis-modbus

> [!IMPORTANT]
> Additional documentation and instructions for contributors are available in the [project wiki](https://github.com/Tom-Bom-badil/trovis-modbus/wiki).

`trovis-modbus` is an asynchronous Python library for reading and writing Samson TROVIS 557x heating controllers over Modbus.

The library is backend-neutral: it consumes a [`modbus_connection.ModbusUnit`](https://github.com/home-assistant-libs/modbus-connection) and does not create or own the transport itself. Applications can therefore use `tmodbus`, `pymodbus`, or another backend supported by `modbus-connection`.

The Home Assistant integration using this library is maintained separately in [`trovis-modbus-hass`](https://github.com/Tom-Bom-badil/trovis-modbus-hass).

## Features

- Object-oriented access to controller subsystems
- Automatic controller-model probe
- Automatic detection of connected physical sensors
- Model-aware heating-circuit support
- Model-specific readable register and coil ranges
- Grouped and range-aware Modbus reads
- Maximum read span of 50 registers or coils per request
- Read and write support for registers and coils
- TROVIS write-access handling
- Field-specific write validation
- Neutral metadata for units, limits, steps, enums, and writable flags
- TROVIS-specific invalid-value handling

## Supported model profiles

The current implementation uses two conservative manufacturer-derived profiles:

| Models | Heating circuits | Register and coil profile |
| --- | ---: | --- |
| TROVIS 5573, 5573-1, 5575, 5576 | 2 | TROVIS 5573 Rev. 2.54 |
| TROVIS 5578, 5578-E, 5579 | 3 | TROVIS 5578 Rev. 2.62 final |

Known gaps and manufacturer block boundaries are preserved. Reads are never planned across those boundaries.

## Device structure

A `Trovis557x` object exposes the following subsystems:

| Attribute | Description |
| --- | --- |
| `info` | Model, firmware, hardware version, and serial information |
| `controller` | Controller-wide status and settings |
| `clock` | Controller date and time |
| `sensors` | Physical temperature and remote-control inputs |
| `heating_circuit_1` | Heating circuit Rk1 |
| `heating_circuit_2` | Heating circuit Rk2 |
| `heating_circuit_3` | Heating circuit Rk3 on supported models |
| `hot_water` | Domestic-hot-water circuit Rk4 |

`device.heating_circuits` contains only the heating circuits supported by the detected model.

## Basic usage

Install the library together with the desired `modbus-connection` backend.

Example using `tmodbus` and transparent RTU over TCP:

```python
import asyncio

from modbus_connection.tmodbus import connect_tcp
from trovis_modbus import Trovis557x


async def main() -> None:
    connection = await connect_tcp(
        "192.168.1.50",
        port=502,
        framer="rtu",
    )

    try:
        unit = connection.for_unit(246)

        probe = await Trovis557x.async_probe(unit)

        device = Trovis557x(
            unit,
            model=probe.model,
            detected_sensors=probe.detected_sensors,
        )

        await device.async_update()

        print("Model:", device.model)
        print("Detected sensors:", sorted(device.detected_sensors))
        print("Outside temperature AF1:", device.sensors.af1)
        print(
            "Rk1 day setpoint:",
            device.heating_circuit_1.room_setpoint_day,
        )

        await device.async_enable_writing()
        try:
            await device.heating_circuit_1.set_room_setpoint_day(21.5)
        finally:
            await device.async_disable_writing()
    finally:
        await connection.close()


asyncio.run(main())
```

For native Modbus TCP with MBAP framing, use:

```python
connection = await connect_tcp(
    "192.168.1.50",
    port=502,
    framer="socket",
)
```

Serial transports are opened through the selected backend and may include local serial ports or supported serial URLs.

## Metadata and writes

The library is the source of truth for neutral TROVIS datapoint metadata:

- register or coil reference
- value type
- scaling
- invalid values
- unit
- minimum and maximum
- step
- enum options
- writable state

Writes use:

```python
await component.async_write_datapoint(field, value)
```

The library refreshes the TROVIS write-access code before the write, applies field validation, and performs required TROVIS-specific preconditions such as releasing an `Ebene` override coil.

## Address conventions

Catalog definitions use manufacturer references:

- holding registers such as `HR40145`
- coils such as `CL137`

Conversion to zero-based Modbus addresses is centralized in the library.

## Command-line query tool

The repository contains `script/query.py` for querying a controller without Home Assistant.

Install the CLI backend:

```bash
python -m pip install -e ".[cli]"
```

Examples:

```bash
python script/query.py tcp 192.168.1.50 --unit 246
python script/query.py serial /dev/ttyUSB0 --unit 246
```

Use `--framer rtu` for transparent RTU over TCP or `--framer socket` for native Modbus TCP.

## Development and tests

Install the project in editable mode and run the test suite:

```bash
python -m pip install -e .
uv sync
uv run pytest
uvx prek run --all-files
```

If `uv` is not available, alternatively run:

```bash
python -m pip install -e .
python -m pip install pytest pytest-asyncio
python -m compileall src tests
python -m pytest
```

The test suite uses the in-memory mock backend provided by `modbus-connection`; no physical controller or external Modbus server is required for the normal unit tests.

The current release 1.0.1 was tested with modbus-connection 3.6.0.

Please read the [contributor instructions](https://github.com/Tom-Bom-badil/trovis-modbus/wiki) before opening a pull request.
