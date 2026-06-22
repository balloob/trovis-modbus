"""trovis-modbus — read a Samson Trovis 557x heating controller over Modbus.

Construct ``Trovis557x(unit)`` with a ``modbus_connection.ModbusUnit``, call
``await device.async_update()``, then read its sub-systems as normal Python
objects::

    device.sensors.outside_1
    device.heating_circuit_1.room_setpoint_active
    device.hot_water.charging
"""

from .component import Component
from .components import (
    Clock,
    Controller,
    DeviceInformation,
    HeatingCircuit,
    HotWater,
    MonthDay,
    Sensors,
)
from .curve import OUTSIDE_TEMPERATURES, flow_temperatures
from .device_info import DeviceInfo
from .enums import OperatingMode, Weekday
from .fields import CoilField, RegisterField
from .trovis import Trovis557x

__all__ = [
    "OUTSIDE_TEMPERATURES",
    "Clock",
    "CoilField",
    "Component",
    "Controller",
    "DeviceInfo",
    "DeviceInformation",
    "HeatingCircuit",
    "HotWater",
    "MonthDay",
    "OperatingMode",
    "RegisterField",
    "Sensors",
    "Trovis557x",
    "Weekday",
    "flow_temperatures",
]
