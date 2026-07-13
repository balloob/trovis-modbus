"""Device identity: the controller's model, versions and serial number.

Exposes the fields Home Assistant's ``DeviceInfo`` wants (manufacturer, model,
sw_version, hw_version, serial_number) directly on the component.
"""

from __future__ import annotations

from .model import TrovisComponent, gauge, integer


class DeviceInformation(TrovisComponent):
    """Controller identity and firmware/hardware versions."""

    _model_raw = integer(40001, signed=False)
    system = gauge(40002, 0.1, signed=False)  # hydraulic-system / "Anlage" code
    _firmware_raw = gauge(40003, 0.01, signed=False)
    _hardware_raw = gauge(40004, 0.01, signed=False)
    _serial_raw = integer(40006, signed=False)

    @property
    def manufacturer(self) -> str:
        """Controller manufacturer."""
        return "Samson"

    @property
    def model(self) -> str:
        """Model name, e.g. 'Trovis 5579'."""
        value = self._model_raw
        return f"Trovis {value}" if value else "Trovis 557x"

    @property
    def firmware_version(self) -> str | None:
        """Firmware version, e.g. '3.05'."""
        value = self._firmware_raw
        return f"{value:.2f}" if value is not None else None

    @property
    def hardware_version(self) -> str | None:
        """Hardware version."""
        value = self._hardware_raw
        return f"{value:.2f}" if value is not None else None

    @property
    def serial_number(self) -> str | None:
        """Internal controller ID / serial number."""
        value = self._serial_raw
        return str(value) if value is not None else None
