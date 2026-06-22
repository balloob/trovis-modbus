"""Field descriptors that map Python attributes to Modbus registers/coils.

A field knows the register address, how to decode the raw word into a Python
value, and (for writable fields) how to encode it back. Reading a field on an
instance returns the value cached by the component's last update.

Per-circuit components reuse one class for circuits 1-3: a field's effective
address is ``address + stride * (index - 1)`` (stride 200 for the 1000-block,
2 for mode/control-signal, 1 for pumps; 0 for single-instance components).
"""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, Any

from .enums import OperatingMode, Weekday

if TYPE_CHECKING:
    from .component import Component

NAN_INT16 = 0x7FFF  # sentinel the controller returns for an absent sensor


def _decimals(scale: float) -> int:
    """Number of decimals implied by a scale factor (0.1 -> 1, 0.01 -> 2)."""
    if scale >= 1:
        return 0
    return max(0, len(f"{scale:.10f}".rstrip("0").split(".")[1]))


class RegisterField:
    """A holding register exposed as a typed attribute on a component."""

    def __init__(
        self,
        address: int,
        *,
        scale: float = 1.0,
        signed: bool = True,
        writable: bool = False,
        nan: int | None = None,
        kind: str = "number",
        stride: int = 0,
        unit: str | None = None,
        doc: str = "",
    ) -> None:
        self.address = address
        self.scale = scale
        self.signed = signed
        self.writable = writable
        self.nan = nan
        self.kind = kind  # number | mode | weekday | time | raw
        self.stride = stride
        self.unit = unit
        self._decimals = _decimals(scale)
        suffix = f" ({unit})" if unit else ""
        self.__doc__ = f"{doc}{suffix}".strip() or None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: Component | None, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        return obj._values.get(self.name)

    # -- codec ---------------------------------------------------------------

    def decode(self, raw: int) -> Any:
        if self.nan is not None and raw == self.nan:
            return None
        if self.signed and raw >= 0x8000:
            raw -= 0x10000
        if self.kind == "raw":
            return raw
        if self.kind == "mode":
            return OperatingMode(raw) if raw in iter(OperatingMode) else None
        if self.kind == "weekday":
            return Weekday(raw) if 0 <= raw <= 7 else None
        if self.kind == "time":
            hour, minute = divmod(raw, 100)
            if hour > 23 or minute > 59:
                return None
            return time(hour=hour, minute=minute)
        value = raw * self.scale
        if self._decimals == 0:
            return int(value)
        return round(value, self._decimals)

    def encode(self, value: Any) -> int:
        if self.kind == "mode":
            raw = int(OperatingMode(value))
        elif self.kind == "weekday":
            raw = int(Weekday(value))
        elif self.kind == "time":
            raw = value.hour * 100 + value.minute
        elif self.scale != 1.0:
            raw = round(value / self.scale)
        else:
            raw = int(value)
        return raw & 0xFFFF if raw < 0 else raw


class CoilField:
    """A coil exposed as a boolean attribute on a component."""

    def __init__(
        self, address: int, *, writable: bool = False, stride: int = 0, doc: str = ""
    ) -> None:
        self.address = address
        self.writable = writable
        self.stride = stride
        self.__doc__ = doc or None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: Component | None, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        return obj._coils.get(self.name)


def temperature(address: int, **kwargs: Any) -> RegisterField:
    """A signed 0.1-scaled temperature register with the NaN sentinel."""
    kwargs.setdefault("unit", "°C")
    return RegisterField(address, scale=0.1, signed=True, nan=NAN_INT16, **kwargs)
