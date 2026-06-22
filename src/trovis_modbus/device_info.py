"""A backend-neutral device-identity value object."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Static identity of a Trovis controller.

    Maps cleanly onto Home Assistant's ``DeviceInfo`` (manufacturer, model,
    sw_version, hw_version, serial_number).
    """

    manufacturer: str
    model: str
    serial_number: str | None
    firmware_version: str | None
    hardware_version: str | None
