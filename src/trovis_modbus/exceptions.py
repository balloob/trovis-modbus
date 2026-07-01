"""Exceptions raised by trovis-modbus."""

from __future__ import annotations


class TrovisWriteNotImplementedError(NotImplementedError):
    """Raised when writing to TROVIS register/coil is not implemented yet."""


class TrovisWriteAccessDisabledError(RuntimeError):
    """Raised when a write is attempted while TROVIS writing is disabled."""


class TrovisWriteAccessError(RuntimeError):
    """Raised when TROVIS write access could not be changed or verified."""

class TrovisValueValidationError(ValueError):
    """Raised when a TROVIS value is outside its allowed domain."""