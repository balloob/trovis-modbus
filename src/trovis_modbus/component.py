"""Base classes: the self-updating ``Component`` and its field descriptors.

A ``RegisterField[T]`` / ``CoilField`` maps a Python attribute to a Modbus
register or coil; reading it returns the decoded value (typed ``T | None`` /
``bool | None``). Fields that need no post-processing are declared directly via
the typed factories below (``temperature(9)``); a value that needs shaping uses
a private field plus a normal ``@property`` so static typing stays accurate::

    _firmware_raw = gauge(2, 0.01, signed=False)

    @property
    def firmware_version(self) -> str | None:
        value = self._firmware_raw
        return f"{value:.2f}" if value is not None else None
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Iterable
from datetime import time
from typing import TYPE_CHECKING, Any, overload

from modbus_connection import ModbusExceptionError, WordOrder

from .enums import OperatingMode, Weekday

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

NAN_INT16 = 0x7FFF  # sentinel the controller returns for an absent sensor
_MAX_GAP = 8  # merge registers/coils less than this many addresses apart
_MAX_SPAN = 100  # but never read a block wider than this

UpdateListener = Callable[[], None]


def _decimals(scale: float) -> int:
    """Number of decimals implied by a scale factor (0.1 -> 1, 0.01 -> 2)."""
    if scale >= 1:
        return 0
    return max(0, len(f"{scale:.10f}".rstrip("0").split(".")[1]))


class RegisterField[T]:
    """A holding register exposed as a typed attribute (returns ``T | None``)."""

    def __init__(
        self,
        address: int,
        *,
        scale: float = 1.0,
        signed: bool = True,
        writable: bool = False,
        nan: int | None = None,
        kind: str = "number",
        count: int = 1,
        word_order: WordOrder = "big",
        stride: int = 0,
        unit: str | None = None,
        level_coil: int | None = None,
        level_coil_stride: int = 0,
    ) -> None:
        self.address = address
        self.scale = scale
        self.signed = signed
        self.writable = writable
        self.nan = nan
        self.kind = kind  # number | mode | weekday | time | raw | float
        # Number of 16-bit registers this value spans (2 for uint32/float32/...).
        self.count = count
        self.word_order = word_order
        self.stride = stride
        self.unit = unit
        # The "Ebene" override coil that must be set to 0 (remote control) before
        # this value can be written over Modbus; None if no override is needed.
        self.level_coil = level_coil
        self.level_coil_stride = level_coil_stride
        self._decimals = _decimals(scale)

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    if TYPE_CHECKING:

        @overload
        def __get__(self, obj: None, objtype: Any = ...) -> RegisterField[T]: ...

        @overload
        def __get__(self, obj: object, objtype: Any = ...) -> T | None: ...

    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        if obj is None:
            return self
        return obj._values.get(self.name)

    # -- codec ---------------------------------------------------------------

    def _combine(self, words: list[int]) -> int:
        """Pack the field's registers into one integer (per ``word_order``)."""
        ordered = words if self.word_order == "big" else list(reversed(words))
        raw = 0
        for word in ordered:
            raw = (raw << 16) | (word & 0xFFFF)
        return raw

    def decode(self, words: list[int]) -> Any:
        """Decode this field's ``count`` register words into its Python value."""
        if self.kind == "float":
            ordered = words if self.word_order == "big" else list(reversed(words))
            raw_bytes = b"".join((w & 0xFFFF).to_bytes(2, "big") for w in ordered)
            value = struct.unpack(">f", raw_bytes)[0]
            return value * self.scale if self.scale != 1.0 else value
        raw = self._combine(words)
        if self.nan is not None and raw == self.nan:
            return None
        bits = 16 * self.count
        if self.signed and raw >= 1 << (bits - 1):
            raw -= 1 << bits
        if self.kind == "raw":
            return raw
        if self.kind == "mode":
            try:
                return OperatingMode(raw)
            except ValueError:
                return None
        if self.kind == "weekday":
            return Weekday(raw) if 0 <= raw <= 7 else None
        if self.kind == "time":
            hour, minute = divmod(raw, 100)
            return time(hour=hour, minute=minute) if hour < 24 and minute < 60 else None
        value = raw * self.scale
        return int(value) if self._decimals == 0 else round(value, self._decimals)

    def encode(self, value: Any) -> list[int]:
        """Encode a Python value into this field's ``count`` register words."""
        if self.kind == "float":
            raw_bytes = struct.pack(">f", float(value))
            words = [
                int.from_bytes(raw_bytes[i : i + 2], "big")
                for i in range(0, len(raw_bytes), 2)
            ]
            return words if self.word_order == "big" else list(reversed(words))
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
        if raw < 0:
            raw += 1 << (16 * self.count)
        words = [
            (raw >> (16 * (self.count - 1 - i))) & 0xFFFF for i in range(self.count)
        ]
        return words if self.word_order == "big" else list(reversed(words))


class CoilField:
    """A coil exposed as a ``bool | None`` attribute."""

    def __init__(
        self,
        address: int,
        *,
        writable: bool = False,
        stride: int = 0,
        level_coil: int | None = None,
        level_coil_stride: int = 0,
    ) -> None:
        self.address = address
        self.writable = writable
        self.stride = stride
        self.level_coil = level_coil
        self.level_coil_stride = level_coil_stride

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    if TYPE_CHECKING:

        @overload
        def __get__(self, obj: None, objtype: Any = ...) -> CoilField: ...

        @overload
        def __get__(self, obj: object, objtype: Any = ...) -> bool | None: ...

    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        if obj is None:
            return self
        return obj._coils.get(self.name)


# -- typed field factories ----------------------------------------------------


def temperature(
    address: int,
    *,
    stride: int = 0,
    writable: bool = False,
    level_coil: int | None = None,
    level_coil_stride: int = 0,
    unit: str = "°C",
) -> RegisterField[float]:
    """A signed 0.1-scaled temperature register with the NaN sentinel."""
    return RegisterField(
        address,
        scale=0.1,
        signed=True,
        nan=NAN_INT16,
        stride=stride,
        writable=writable,
        level_coil=level_coil,
        level_coil_stride=level_coil_stride,
        unit=unit,
    )


def gauge(
    address: int,
    scale: float,
    *,
    signed: bool = True,
    stride: int = 0,
    writable: bool = False,
    unit: str | None = None,
) -> RegisterField[float]:
    """A scaled numeric register (slope, level, hysteresis, ...)."""
    return RegisterField(
        address,
        scale=scale,
        signed=signed,
        stride=stride,
        writable=writable,
        unit=unit,
    )


def integer(
    address: int,
    *,
    signed: bool = True,
    stride: int = 0,
    writable: bool = False,
    unit: str | None = None,
) -> RegisterField[int]:
    """An unscaled integer register (counts, percentages, addresses)."""
    return RegisterField(
        address,
        scale=1.0,
        signed=signed,
        stride=stride,
        writable=writable,
        unit=unit,
    )


def operating_mode(
    address: int,
    *,
    stride: int = 0,
    writable: bool = False,
    level_coil: int | None = None,
    level_coil_stride: int = 0,
) -> RegisterField[OperatingMode]:
    """An operating-mode register (``Liste_Schalter``)."""
    return RegisterField(
        address,
        kind="mode",
        stride=stride,
        writable=writable,
        level_coil=level_coil,
        level_coil_stride=level_coil_stride,
    )


def weekday_value(address: int, *, writable: bool = False) -> RegisterField[Weekday]:
    """A weekday register (0 = off)."""
    return RegisterField(address, kind="weekday", writable=writable)


def time_value(address: int, *, writable: bool = False) -> RegisterField[time]:
    """A time-of-day register (HHMM)."""
    return RegisterField(address, kind="time", writable=writable)


def raw_register(address: int, *, writable: bool = False) -> RegisterField[int]:
    """A raw register word (no scaling/sign handling)."""
    return RegisterField(address, kind="raw", writable=writable)


def uint32(
    address: int,
    *,
    scale: float = 1.0,
    word_order: WordOrder = "big",
    stride: int = 0,
    writable: bool = False,
    unit: str | None = None,
    doc: str = "",
) -> RegisterField[int]:
    """An unsigned 32-bit value over two consecutive registers."""
    return RegisterField(
        address,
        count=2,
        word_order=word_order,
        scale=scale,
        signed=False,
        stride=stride,
        writable=writable,
        unit=unit,
        doc=doc,
    )


def int32(
    address: int,
    *,
    scale: float = 1.0,
    word_order: WordOrder = "big",
    stride: int = 0,
    writable: bool = False,
    unit: str | None = None,
    doc: str = "",
) -> RegisterField[int]:
    """A signed 32-bit value over two consecutive registers."""
    return RegisterField(
        address,
        count=2,
        word_order=word_order,
        scale=scale,
        signed=True,
        stride=stride,
        writable=writable,
        unit=unit,
        doc=doc,
    )


def float32(
    address: int,
    *,
    scale: float = 1.0,
    word_order: WordOrder = "big",
    stride: int = 0,
    writable: bool = False,
    unit: str | None = None,
    doc: str = "",
) -> RegisterField[float]:
    """An IEEE-754 single-precision float over two consecutive registers."""
    return RegisterField(
        address,
        count=2,
        word_order=word_order,
        kind="float",
        scale=scale,
        stride=stride,
        writable=writable,
        unit=unit,
        doc=doc,
    )


def coil(
    address: int,
    *,
    writable: bool = False,
    stride: int = 0,
    level_coil: int | None = None,
    level_coil_stride: int = 0,
) -> CoilField:
    """A coil."""
    return CoilField(
        address,
        writable=writable,
        stride=stride,
        level_coil=level_coil,
        level_coil_stride=level_coil_stride,
    )


# A read target: (absolute address, field, the component store to write into).
RegisterItem = tuple[int, "RegisterField[Any]", dict[str, Any]]
CoilItem = tuple[int, "CoilField", dict[str, Any]]


Range = tuple[int, int]  # an inclusive (low, high) readable address range


def _range_of(address: int, ranges: tuple[Range, ...] | None) -> Range | None:
    """The readable range containing ``address``, or ``None``."""
    if ranges is None:
        return None
    for low, high in ranges:
        if low <= address <= high:
            return (low, high)
    return None


def _plan_blocks(
    spans: Iterable[tuple[int, int]],
    ranges: tuple[Range, ...] | None = None,
) -> list[tuple[int, int]]:
    """Group ``(start_address, width)`` spans into ``(start, count)`` read blocks.

    A multi-register value is never split across blocks (each span is placed
    whole) and a block never grows past ``_MAX_SPAN`` registers.

    Without ``ranges`` (the generic default), spans no more than ``_MAX_GAP``
    apart share a block. With ``ranges`` — the controller's readable address
    ranges — spans merge only when they sit in the *same* range (the gap between
    them is then readable too), and never across a range boundary; reads are
    still clipped to the addresses actually used.
    """
    ordered = sorted(set(spans))
    if not ordered:
        return []
    blocks: list[tuple[int, int]] = []
    block_start, width = ordered[0]
    block_end = block_start + width - 1  # last (inclusive) address covered so far
    block_range = _range_of(block_start, ranges)
    for address, width in ordered[1:]:
        end = address + width - 1
        if ranges is None:
            mergeable = address - block_end <= _MAX_GAP
        else:
            address_range = _range_of(address, ranges)
            mergeable = address_range is not None and address_range == block_range
        if mergeable and end - block_start + 1 <= _MAX_SPAN:
            block_end = max(block_end, end)
        else:
            blocks.append((block_start, block_end - block_start + 1))
            block_start, block_end = address, end
            block_range = _range_of(address, ranges)
    blocks.append((block_start, block_end - block_start + 1))
    return blocks


async def _bulk_read_registers(
    unit: ModbusUnit,
    items: list[RegisterItem],
    ranges: tuple[Range, ...] | None = None,
) -> None:
    """Read every ``(address, field, store)`` in as few Modbus calls as possible.

    Targets are pooled across whatever components are passed in, so adjacent
    registers — even ones belonging to different sub-systems — are fetched
    together, and a multi-register value is always kept within one block.
    ``ranges`` (the device's readable address ranges) keeps reads from crossing an
    unreadable gap. Each field's decoded value lands in its ``store`` under
    ``field.name``; a Modbus exception covering a block sets those fields to
    ``None`` (other errors propagate so the caller can mark the device down).
    """
    if not items:
        return
    by_address: dict[int, list[tuple[RegisterField[Any], dict[str, Any]]]] = {}
    spans: list[tuple[int, int]] = []
    for address, field, store in items:
        by_address.setdefault(address, []).append((field, store))
        spans.append((address, field.count))
    for start, count in _plan_blocks(spans, ranges):
        try:
            words = await unit.read_holding_registers(start, count)
        except ModbusExceptionError:
            for offset in range(count):
                for field, store in by_address.get(start + offset, ()):
                    store[field.name] = None
            continue
        for offset in range(count):
            for field, store in by_address.get(start + offset, ()):
                store[field.name] = field.decode(words[offset : offset + field.count])


async def _bulk_read_coils(
    unit: ModbusUnit,
    items: list[CoilItem],
    ranges: tuple[Range, ...] | None = None,
) -> None:
    """Read coil ``(address, field, store)`` targets in as few calls as possible."""
    if not items:
        return
    by_address: dict[int, list[tuple[CoilField, dict[str, Any]]]] = {}
    for address, field, store in items:
        by_address.setdefault(address, []).append((field, store))
    for start, count in _plan_blocks(((address, 1) for address in by_address), ranges):
        try:
            bits = await unit.read_coils(start, count)
        except ModbusExceptionError:
            for offset in range(count):
                for field, store in by_address.get(start + offset, ()):
                    store[field.name] = None
            continue
        for offset in range(count):
            bit = bool(bits[offset])
            for field, store in by_address.get(start + offset, ()):
                store[field.name] = bit


class Component:
    """A device sub-system whose attributes map to registers and coils.

    Subclasses declare ``RegisterField`` / ``CoilField`` descriptors (usually via
    the typed factories). Each component reads only its own registers, so it can
    refresh independently; listeners registered via :meth:`add_update_listener`
    fire after each update (one entity in Home Assistant can subscribe per
    component).
    """

    _register_fields: dict[str, RegisterField[Any]] = {}
    _coil_fields: dict[str, CoilField] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        registers: dict[str, RegisterField[Any]] = {}
        coils: dict[str, CoilField] = {}
        for klass in reversed(cls.__mro__):
            for name, value in vars(klass).items():
                if isinstance(value, RegisterField):
                    registers[name] = value
                elif isinstance(value, CoilField):
                    coils[name] = value
        cls._register_fields = registers
        cls._coil_fields = coils

    def __init__(self, unit: ModbusUnit, index: int = 1) -> None:
        self._unit = unit
        self._index = index
        self._values: dict[str, Any] = {}
        self._coils: dict[str, bool | None] = {}
        self._listeners: list[UpdateListener] = []
        # The device's readable address ranges, set by the owning device so reads
        # don't cross an unreadable gap; None falls back to gap-based planning.
        self._register_ranges: tuple[Range, ...] | None = None
        self._coil_ranges: tuple[Range, ...] | None = None

    def _address(self, field: RegisterField[Any] | CoilField) -> int:
        return field.address + field.stride * (self._index - 1)

    # -- listeners -----------------------------------------------------------

    def add_update_listener(self, listener: UpdateListener) -> Callable[[], None]:
        """Register a callback fired after each update; returns an unsubscribe."""
        self._listeners.append(listener)

        def remove() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return remove

    # -- update --------------------------------------------------------------

    def _register_items(self) -> list[RegisterItem]:
        """This component's register read targets (absolute address, field, store)."""
        return [
            (self._address(f), f, self._values) for f in self._register_fields.values()
        ]

    def _coil_items(self) -> list[CoilItem]:
        """This component's coil read targets (absolute address, field, store)."""
        return [(self._address(f), f, self._coils) for f in self._coil_fields.values()]

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def async_update(self) -> None:
        """Read this component's registers and coils, then notify listeners.

        Reads only this sub-system's own registers, so it can refresh on its own.
        :meth:`Trovis557x.async_update` pools every sub-system's reads instead, to
        fetch the whole device in as few Modbus calls as possible.
        """
        await _bulk_read_registers(
            self._unit, self._register_items(), self._register_ranges
        )
        await _bulk_read_coils(self._unit, self._coil_items(), self._coil_ranges)
        self._notify()

    # -- writes --------------------------------------------------------------

    async def write(self, field: str, value: Any) -> None:
        """Write a writable register or coil by attribute name.

        If the field has an override ("Ebene") coil, it is first set to 0
        (remote control) so the controller accepts the write — a documented
        Trovis quirk: e.g. the operating mode is ignored over Modbus unless its
        Ebene coil is released first.
        """
        if field in self._register_fields:
            register = self._register_fields[field]
            if not register.writable:
                raise AttributeError(f"{field} is read-only")
            await self._enable_remote_control(register)
            address = self._address(register)
            words = register.encode(value)
            if len(words) == 1:
                await self._unit.write_register(address, words[0])
            else:
                await self._unit.write_registers(address, words)
        elif field in self._coil_fields:
            coil_field = self._coil_fields[field]
            if not coil_field.writable:
                raise AttributeError(f"{field} is read-only")
            await self._enable_remote_control(coil_field)
            await self._unit.write_coil(self._address(coil_field), bool(value))
        else:
            raise AttributeError(f"unknown field {field!r}")

    async def _enable_remote_control(
        self, field: RegisterField[Any] | CoilField
    ) -> None:
        """Release the field's override coil (set it to 0 = remote control)."""
        if field.level_coil is None:
            return
        address = field.level_coil + field.level_coil_stride * (self._index - 1)
        await self._unit.write_coil(address, False)
