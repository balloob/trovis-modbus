"""Trovis-specific pieces layered on the ``modbus_connection.model`` framework."""

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum
from typing import Any

from modbus_connection import ModbusError
from modbus_connection.model import (
    Component,
    RegisterField,
    coil as _modbus_coil,
    enum as _modbus_enum,
    gauge as _modbus_gauge,
    integer as _modbus_integer,
    raw_register as _modbus_raw_register,
)

from .addresses import coil_address, register_address
from .exceptions import TrovisValueValidationError, TrovisWriteAccessError
from .metadata import (
    BooleanMetadata,
    DatapointMetadata,
    EnumMetadata,
    NumberMetadata,
    OptionMetadata,
    attach_metadata,
    step_from_digits,
)
from .ranges import COIL_RANGES, REGISTER_RANGES


NAN_INT16 = 0x7FFF  # the value the controller returns for an absent sensor

DEFAULT_WRITE_ACCESS_CODE = 1732
WRITE_ACCESS_REGISTER = 40145  # HR40145 / Write-En_Modem, Modbus address 144
WRITE_ACCESS_DISABLE_CODE = 0

LEVEL_GLT = False
LEVEL_AUTARK = True


def _number_validator(
    *,
    min_value: float | int | None = None,
    max_value: float | int | None = None,
    step: float | int | None = None,
) -> Callable[[Any], Any]:
    """Return a write validator for numeric TROVIS values."""

    def validate(value: Any) -> Any:
        number = float(value)

        if min_value is not None and number < min_value:
            raise TrovisValueValidationError(
                f"Value {value} is below minimum {min_value}"
            )

        if max_value is not None and number > max_value:
            raise TrovisValueValidationError(
                f"Value {value} is above maximum {max_value}"
            )

        # Step is primarily UI metadata for now. Avoid hard float-modulo
        # validation until we see invalid writes slipping through.
        return value

    return validate


def _with_number_validator(
    writable: bool | Callable[[Any], Any],
    *,
    min_value: float | int | None,
    max_value: float | int | None,
    step: float | int | None,
) -> bool | Callable[[Any], Any]:
    """Return writable or a validator-backed writable value."""
    if not writable:
        return False

    if callable(writable):
        return writable

    if min_value is None and max_value is None and step is None:
        return True

    return _number_validator(
        min_value=min_value,
        max_value=max_value,
        step=step,
    )


def raw_register(
    hr_number: int,
    *args: Any,
    min_value: float | int | None = None,
    max_value: float | int | None = None,
    step: float | int | None = None,
    digits: int | None = None,
    unit: str | None = None,
    raw_min: float | int | None = None,
    raw_max: float | int | None = None,
    maker_key: str | None = None,
    maker_category: str | None = None,
    description: str | None = None,
    writable: bool | Callable[[Any], Any] = False,
    **kwargs: Any,
):
    """Create a raw register field from a manufacturer TROVIS HR reference."""
    effective_step = step if step is not None else step_from_digits(digits)
    effective_writable = _with_number_validator(
        writable,
        min_value=min_value,
        max_value=max_value,
        step=effective_step,
    )

    field = _modbus_raw_register(
        register_address(hr_number),
        *args,
        writable=effective_writable,
        **kwargs,
    )

    return attach_metadata(
        field,
        DatapointMetadata(
            value_kind="number",
            maker_reference=hr_number,
            maker_key=maker_key,
            maker_category=maker_category,
            description=description,
            writable=bool(writable),
            number=NumberMetadata(
                min_value=min_value,
                max_value=max_value,
                step=effective_step,
                digits=digits,
                unit=unit,
                raw_min=raw_min,
                raw_max=raw_max,
            ),
        ),
    )


def integer(
    hr_number: int,
    *args: Any,
    min_value: float | int | None = None,
    max_value: float | int | None = None,
    step: float | int | None = None,
    digits: int | None = None,
    unit: str | None = None,
    raw_min: float | int | None = None,
    raw_max: float | int | None = None,
    maker_key: str | None = None,
    maker_category: str | None = None,
    description: str | None = None,
    writable: bool | Callable[[Any], Any] = False,
    **kwargs: Any,
):
    """Create an integer field from a manufacturer TROVIS HR reference."""
    effective_step = step if step is not None else step_from_digits(digits)
    effective_writable = _with_number_validator(
        writable,
        min_value=min_value,
        max_value=max_value,
        step=effective_step,
    )

    field = _modbus_integer(
        register_address(hr_number),
        *args,
        writable=effective_writable,
        unit=unit,
        **kwargs,
    )

    return attach_metadata(
        field,
        DatapointMetadata(
            value_kind="number",
            maker_reference=hr_number,
            maker_key=maker_key,
            maker_category=maker_category,
            description=description,
            writable=bool(writable),
            number=NumberMetadata(
                min_value=min_value,
                max_value=max_value,
                step=effective_step,
                digits=digits,
                unit=unit,
                raw_min=raw_min,
                raw_max=raw_max,
            ),
        ),
    )


def gauge(
    hr_number: int,
    scale: float,
    *args: Any,
    min_value: float | int | None = None,
    max_value: float | int | None = None,
    step: float | int | None = None,
    digits: int | None = None,
    unit: str | None = None,
    raw_min: float | int | None = None,
    raw_max: float | int | None = None,
    maker_key: str | None = None,
    maker_category: str | None = None,
    description: str | None = None,
    writable: bool | Callable[[Any], Any] = False,
    **kwargs: Any,
):
    """Create a gauge field from a manufacturer TROVIS HR reference."""
    effective_step = step if step is not None else step_from_digits(digits)
    effective_writable = _with_number_validator(
        writable,
        min_value=min_value,
        max_value=max_value,
        step=effective_step,
    )

    field = _modbus_gauge(
        register_address(hr_number),
        scale,
        *args,
        writable=effective_writable,
        unit=unit,
        **kwargs,
    )

    return attach_metadata(
        field,
        DatapointMetadata(
            value_kind="number",
            maker_reference=hr_number,
            maker_key=maker_key,
            maker_category=maker_category,
            description=description,
            writable=bool(writable),
            number=NumberMetadata(
                min_value=min_value,
                max_value=max_value,
                step=effective_step,
                digits=digits,
                unit=unit,
                raw_min=raw_min,
                raw_max=raw_max,
            ),
        ),
    )


def enum(
    hr_number: int,
    enum_type: type[IntEnum],
    *args: Any,
    options: tuple[OptionMetadata, ...] | None = None,
    maker_key: str | None = None,
    maker_category: str | None = None,
    description: str | None = None,
    writable: bool | Callable[[Any], Any] = False,
    **kwargs: Any,
):
    """Create an enum field from a manufacturer TROVIS HR reference."""
    field = _modbus_enum(
        register_address(hr_number),
        enum_type,
        *args,
        writable=writable,
        **kwargs,
    )

    resolved_options = options or tuple(
        OptionMetadata(member.name.lower(), int(member), member.name)
        for member in enum_type
    )

    return attach_metadata(
        field,
        DatapointMetadata(
            value_kind="enum",
            maker_reference=hr_number,
            maker_key=maker_key,
            maker_category=maker_category,
            description=description,
            writable=bool(writable),
            enum=EnumMetadata(enum_type=enum_type, options=resolved_options),
        ),
    )


def coil(
    cl_number: int,
    *,
    stride: int = 0,
    writable: bool = False,
    false_key: str = "off",
    true_key: str = "on",
    false_label: str | None = None,
    true_label: str | None = None,
    inverted: bool = False,
    maker_key: str | None = None,
    maker_category: str | None = None,
    description: str | None = None,
):
    """Create a coil field from a manufacturer TROVIS CL number."""
    field = _modbus_coil(
        coil_address(cl_number),
        stride=stride,
        writable=writable,
    )

    return attach_metadata(
        field,
        DatapointMetadata(
            value_kind="boolean",
            maker_reference=cl_number,
            maker_key=maker_key,
            maker_category=maker_category,
            description=description,
            writable=writable,
            boolean=BooleanMetadata(
                false_key=false_key,
                true_key=true_key,
                false_label=false_label,
                true_label=true_label,
                inverted=inverted,
            ),
        ),
    )


def temperature(
    hr_number: int,
    *,
    stride: int = 0,
    writable: bool = False,
    unit: str = "°C",
    min_value: float | int | None = None,
    max_value: float | int | None = None,
    step: float | int | None = None,
    digits: int | None = None,
    raw_min: float | int | None = None,
    raw_max: float | int | None = None,
    maker_key: str | None = None,
    maker_category: str | None = None,
    description: str | None = None,
) -> RegisterField[float]:
    """A signed 0.1-scaled temperature register with the Trovis NaN sentinel."""
    return gauge(
        hr_number,
        0.1,
        signed=True,
        nan=NAN_INT16,
        stride=stride,
        writable=writable,
        unit=unit,
        min_value=min_value,
        max_value=max_value,
        step=step,
        digits=digits,
        raw_min=raw_min,
        raw_max=raw_max,
        maker_key=maker_key,
        maker_category=maker_category,
        description=description,
    )


async def async_read_writing_enabled(unit: Any) -> bool:
    """Return whether TROVIS write access appears to be active."""
    try:
        return (
            await unit.read_holding_registers(
                register_address(WRITE_ACCESS_REGISTER),
                1,
            )
        )[0] != WRITE_ACCESS_DISABLE_CODE
    except ModbusError as err:
        raise TrovisWriteAccessError(
            "Could not read TROVIS write access state"
        ) from err


async def async_enable_writing(
    unit: Any,
    access_code: int = DEFAULT_WRITE_ACCESS_CODE,
) -> None:
    """Enable TROVIS writing globally."""
    try:
        await unit.write_register(register_address(WRITE_ACCESS_REGISTER), access_code)
    except ModbusError as err:
        raise TrovisWriteAccessError(
            "Could not enable TROVIS write access"
        ) from err


async def async_disable_writing(unit: Any) -> None:
    """Disable TROVIS writing globally."""
    try:
        await unit.write_register(
            register_address(WRITE_ACCESS_REGISTER),
            WRITE_ACCESS_DISABLE_CODE,
        )
    except ModbusError as err:
        raise TrovisWriteAccessError(
            "Could not reset TROVIS write access"
        ) from err


async def async_ensure_writing_enabled(
    unit: Any,
    access_code: int = DEFAULT_WRITE_ACCESS_CODE,
) -> None:
    """Ensure that the TROVIS access code is active for the next write."""
    try:
        await unit.write_register(register_address(WRITE_ACCESS_REGISTER), access_code)
    except ModbusError as err:
        raise TrovisWriteAccessError(
            "Could not refresh TROVIS write access"
        ) from err


class TrovisComponent(Component):
    """A Trovis sub-system: readable ranges + the Ebene write-unlock quirk.

    Some writable values are ignored over Modbus unless their "Ebene" override
    coil is first released to 0 (= GLT / remote control). Subclasses list those
    in :attr:`ebene_coils`.
    """

    register_ranges = REGISTER_RANGES
    coil_ranges = COIL_RANGES

    # Writable fields whose write must first release an override coil to 0.
    ebene_coils: dict[str, tuple[int, int]] = {}

    def metadata_for(self, field: str) -> DatapointMetadata | None:
        """Return neutral TROVIS metadata for a field."""
        descriptor = self._register_fields.get(field)
        if descriptor is None:
            descriptor = self._coil_fields.get(field)

        if descriptor is None:
            return None

        return getattr(descriptor, "trovis_metadata", None)

    def require_metadata_for(self, field: str) -> DatapointMetadata:
        """Return TROVIS metadata for a field or raise."""
        metadata = self.metadata_for(field)
        if metadata is None:
            raise AttributeError(f"unknown or untyped TROVIS field {field!r}")
        return metadata

    async def write(self, field: str, value: Any) -> None:
        """Write a field, applying field-specific TROVIS preconditions."""
        if (override := self.ebene_coils.get(field)) is not None:
            address, stride = override
            await self._unit.write_coil(
                coil_address(address + stride * (self._index - 1)),
                LEVEL_GLT,
            )

        await super().write(field, value)

    async def async_write_datapoint(
        self,
        field: str,
        value: Any,
        *,
        access_code: int = DEFAULT_WRITE_ACCESS_CODE,
    ) -> None:
        """Write a TROVIS data point.

        This is the public write entry point for integrations. It refreshes the
        access code and then delegates to the generic component write path.
        """
        await async_ensure_writing_enabled(self._unit, access_code)
        await self.write(field, value)