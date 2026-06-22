"""The Component base class: a self-updating group of registers and coils."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from modbus_connection import ModbusExceptionError

from .fields import CoilField, RegisterField

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

_MAX_GAP = 8  # merge registers/coils less than this many addresses apart
_MAX_SPAN = 100  # but never read a block wider than this

UpdateListener = Callable[[], None]


def _blocks(items: Iterable[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Group (address, name) pairs into contiguous read blocks."""
    ordered = sorted(items)
    blocks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for address, name in ordered:
        if current and (
            address - current[-1][0] > _MAX_GAP or address - current[0][0] >= _MAX_SPAN
        ):
            blocks.append(current)
            current = []
        current.append((address, name))
    if current:
        blocks.append(current)
    return blocks


class Component:
    """A device sub-system whose attributes map to registers and coils.

    Subclasses declare ``RegisterField`` / ``CoilField`` descriptors. Each
    component reads only its own registers, so it can refresh independently;
    listeners registered via :meth:`add_update_listener` fire after each update
    (one entity in Home Assistant can subscribe per component).
    """

    _register_fields: dict[str, RegisterField] = {}
    _coil_fields: dict[str, CoilField] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        registers: dict[str, RegisterField] = {}
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

    # -- address helper ------------------------------------------------------

    def _address(self, field: RegisterField | CoilField) -> int:
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

    async def async_update(self) -> None:
        """Read this component's registers and coils, then notify listeners."""
        await self._update_registers()
        await self._update_coils()
        for listener in list(self._listeners):
            listener()

    async def _update_registers(self) -> None:
        fields = self._register_fields
        if not fields:
            return
        addr_to_name = {self._address(f): name for name, f in fields.items()}
        for block in _blocks(addr_to_name.items()):
            start = block[0][0]
            count = block[-1][0] - start + 1
            try:
                words = await self._unit.read_holding_registers(start, count)
            except ModbusExceptionError:
                for _addr, name in block:
                    self._values[name] = None
                continue
            for address, name in block:
                self._values[name] = fields[name].decode(words[address - start])

    async def _update_coils(self) -> None:
        fields = self._coil_fields
        if not fields:
            return
        addr_to_name = {self._address(f): name for name, f in fields.items()}
        for block in _blocks(addr_to_name.items()):
            start = block[0][0]
            count = block[-1][0] - start + 1
            try:
                bits = await self._unit.read_coils(start, count)
            except ModbusExceptionError:
                for _addr, name in block:
                    self._coils[name] = None
                continue
            for address, name in block:
                self._coils[name] = bool(bits[address - start])

    # -- writes --------------------------------------------------------------

    async def write(self, field: str, value: Any) -> None:
        """Write a writable register or coil by attribute name."""
        if field in self._register_fields:
            register = self._register_fields[field]
            if not register.writable:
                raise AttributeError(f"{field} is read-only")
            await self._unit.write_register(
                self._address(register), register.encode(value)
            )
        elif field in self._coil_fields:
            coil = self._coil_fields[field]
            if not coil.writable:
                raise AttributeError(f"{field} is read-only")
            await self._unit.write_coil(self._address(coil), bool(value))
        else:
            raise AttributeError(f"unknown field {field!r}")
