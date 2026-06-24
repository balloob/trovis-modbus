"""Verify every field against the canonical Samson Trovis 557x point list.

The reference (``tests/reference/canonical_points.json``) is the address/scale
table from the Tom-Bom-badil SmartHomeNG plugin — the authoritative consolidated
Modbus point list for the 557x family. This test catches any wrong address,
scale, or read-only/writable mislabel.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from modbus_connection.model import CoilField, RegisterField

from trovis_modbus import Trovis557x

_REF = json.loads(
    (Path(__file__).parent / "reference" / "canonical_points.json").read_text()
)
CANON_REG: dict[int, dict[str, Any]] = {e["id"]: e for e in _REF["registers"].values()}
CANON_COIL: dict[int, dict[str, Any]] = {e["id"]: e for e in _REF["coils"].values()}

# Scales confirmed on real hardware that differ from the canonical table (whose
# factors are not perfectly reliable). Tom-Bom-badil's Trovis 5578 reads register
# 117 (AT adaptation rate) as 3.0 K/h, i.e. scale 0.1 — the table lists factor 1.
HARDWARE_VERIFIED_SCALE: dict[int, float] = {117: 0.1}


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
        for field in {**component._register_fields, **component._coil_fields}.values():
            out.append((label, component._address(field), field))
    return out


def _override_cases() -> list[Any]:
    """(label, effective override-coil address, field) for fields with an Ebene coil."""
    device = Trovis557x(unit=None)  # type: ignore[arg-type]
    cases: list[Any] = []
    for component in device.components:
        index = component._index
        label = type(component).__name__ + (f"[{index}]" if index != 1 else "")
        for field in {**component._register_fields, **component._coil_fields}.values():
            if field.level_coil is None:
                continue
            address = field.level_coil + field.level_coil_stride * (index - 1)
            cases.append(
                pytest.param(label, address, field, id=f"{label}.{field.name}")
            )
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
    if field.kind == "number":
        if address in HARDWARE_VERIFIED_SCALE:
            expected = HARDWARE_VERIFIED_SCALE[address]
        else:
            expected = _canonical_scale(entry)
        if expected is not None:
            assert field.scale == pytest.approx(expected), (
                f"{label}.{field.name} scale {field.scale} != spec {expected} "
                f"({entry['name']})"
            )
    if field.writable:
        assert entry["art"] == "rw", f"{label}.{field.name} is read-only in the spec"


@pytest.mark.parametrize(("label", "address", "field"), _override_cases())
def test_override_coil_matches_canonical(
    label: str, address: int, field: RegisterField | CoilField
) -> None:
    """Every 'Ebene' override coil is an rw remote/autonomous (Liste_FA) coil."""
    # Circuit-3 override coils (92/93/97) are absent from the 5576-based
    # reference; they follow the +2/+1 pattern verified on circuits 1 and 2.
    if "[3]" in label and address in (92, 93, 97):
        pytest.skip("circuit-3 override coils absent from reference table")
    assert address in CANON_COIL, f"{label}.{field.name} override {address} not in spec"
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
    assert address in CANON_COIL, f"{label}.{field.name} address {address} not in spec"
    if field.writable:
        assert CANON_COIL[address]["art"] == "rw", (
            f"{label}.{field.name} is read-only in the spec"
        )
