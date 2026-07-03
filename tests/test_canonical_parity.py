"""Verify modeled fields against the Samson Trovis 557x reference point list.

The reference (``tests/reference/canonical_points.json``) is the address/scale
table from the Tom-Bom-badil SmartHomeNG plugin. It is used as a known reference
for modeled fields, but it is not treated as a complete list of everything the
library must expose.

This test catches wrong addresses, scales, or read-only/writable labels for
fields that are currently modeled.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from modbus_connection.model import CoilField, RegisterField

from trovis_modbus import Trovis557x
from trovis_modbus.addresses import coil_address

_REF = json.loads(
    (Path(__file__).parent / "reference" / "canonical_points.json").read_text()
)
CANON_REG: dict[int, dict[str, Any]] = {e["id"]: e for e in _REF["registers"].values()}
CANON_COIL: dict[int, dict[str, Any]] = {e["id"]: e for e in _REF["coils"].values()}

# Scales confirmed on real hardware that differ from the canonical table (whose
# factors are not perfectly reliable). Tom-Bom-badil's Trovis 5578 reads register
# 117 (AT adaptation rate) as 3.0 K/h, i.e. scale 0.1 — the table lists factor 1.
HARDWARE_VERIFIED_SCALE: dict[int, float] = {117: 0.1}

# Manufacturer-documented points that are modeled by the library but are not
# present in the older SmartHomeNG/5576-derived canonical reference file.
KNOWN_NON_CANONICAL_COILS = {
    coil_address(cl_number)
    for cl_number in (
        407,  # Hot-water intermediate heating operation
        703,
        704,
        705,  # Room control unit Rk1-Rk3
        2107,
        2207,
        2307,  # Optimization Rk1-Rk3
        2108,
        2208,
        2308,  # Adaptation Rk1-Rk3
    )
}


def _canonical_scale(entry: dict[str, Any]) -> float | None:
    """Effective value scale of a canonical entry (None = special/non-numeric)."""
    typ = entry["typ"]
    if typ == "Version":
        return 10 ** (-entry["digits"])
    if typ.startswith("Liste") or typ in ("Datum", "Uhrzeit"):
        return None
    if typ == "Zahl":
        return float(entry["factor"])
    return None  # "???" and similar: don't assert a scale


def _fields() -> list[tuple[str, int, RegisterField | CoilField]]:
    """Every (component, effective address, field) across all components."""
    device = Trovis557x(unit=None)  # type: ignore[arg-type]
    out: list[tuple[str, int, RegisterField | CoilField]] = []
    for component in device.components:
        label = type(component).__name__ + (
            f"[{component._index}]" if component._index != 1 else ""
        )
        for field in {**component._register_fields, **component._bit_fields}.values():
            out.append((label, component._address(field), field))
    return out


def _override_cases() -> list[Any]:
    """(label, effective override-coil address, field name) for Ebene-gated fields."""
    device = Trovis557x(unit=None)  # type: ignore[arg-type]
    cases: list[Any] = []
    for component in device.components:
        index = component._index
        label = type(component).__name__ + (f"[{index}]" if index != 1 else "")
        for name, (cl_number, stride) in getattr(
            component, "ebene_coils", {}
        ).items():
            address = coil_address(cl_number + stride * (index - 1))
            cases.append(pytest.param(label, address, name, id=f"{label}.{name}"))
    return cases


REGISTER_CASES = [
    pytest.param(label, addr, field, id=f"{label}.{field.name}")
    for label, addr, field in _fields()
    if isinstance(field, RegisterField)
]
COIL_CASES = [
    pytest.param(label, addr, field, id=f"{label}.{field.name}")
    for label, addr, field in _fields()
    if isinstance(field, CoilField)
]


@pytest.mark.parametrize(("label", "address", "field"), REGISTER_CASES)
def test_register_matches_canonical(
    label: str, address: int, field: RegisterField
) -> None:
    assert address in CANON_REG, f"{label}.{field.name} address {address} not in spec"
    entry = CANON_REG[address]
    # Plain scaled numbers (not enum-mapped) must match the canonical scale.
    scale = getattr(field, "scale", None)
    if scale is not None and getattr(field, "enum_type", None) is None:
        if address in HARDWARE_VERIFIED_SCALE:
            expected = HARDWARE_VERIFIED_SCALE[address]
        else:
            expected = _canonical_scale(entry)
        if expected is not None:
            assert scale == pytest.approx(expected), (
                f"{label}.{field.name} scale {scale} != spec {expected} "
                f"({entry['name']})"
            )
    if field.writable:
        assert entry["art"] == "rw", f"{label}.{field.name} is read-only in the spec"


@pytest.mark.parametrize(("label", "address", "field"), _override_cases())
def test_override_coil_matches_canonical(label: str, address: int, field: str) -> None:
    """Every 'Ebene' override coil is an rw remote/autonomous (Liste_FA) coil."""
    # Circuit-3 override coils (92/93/97) are absent from the 5576-based
    # reference; they follow the +2/+1 pattern verified on circuits 1 and 2.
    if "[3]" in label and address in (92, 93, 97):
        pytest.skip("circuit-3 override coils absent from reference table")
    assert address in CANON_COIL, f"{label}.{field} override {address} not in spec"
    entry = CANON_COIL[address]
    assert entry["art"] == "rw"
    assert entry["typ"] == "Liste_FA", (
        f"override {address} is {entry['typ']}, not Liste_FA"
    )


@pytest.mark.parametrize(("label", "address", "field"), COIL_CASES)
def test_coil_matches_canonical(label: str, address: int, field: CoilField) -> None:
    # Heating-circuit 3 status coils (1399-1408) are not in the 5576-based
    # reference; they follow the +200 pattern verified on circuits 1 and 2.
    if "HeatingCircuit[3]" in label and 1399 <= address <= 1408:
        pytest.skip("circuit-3 status coils absent from reference table")

    if address in KNOWN_NON_CANONICAL_COILS:
        assert field.writable, (
            f"{label}.{field.name} is expected to be a writable manufacturer point"
        )
        return

    assert address in CANON_COIL, f"{label}.{field.name} address {address} not in spec"
    if field.writable:
        assert CANON_COIL[address]["art"] == "rw", (
            f"{label}.{field.name} is read-only in the spec"
        )
