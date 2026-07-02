"""Global temperature inputs."""

from __future__ import annotations

from .model import TrovisComponent, temperature


class Sensors(TrovisComponent):
    """Physical sensor inputs, e.g. Pt1000.

    Naming follows the manual abbreviations.
    """

    af1 = temperature(40010)  # Außenfühler 1
    af2 = temperature(40011)  # Außenfühler 2

    vf1 = temperature(40013)  # Vorlauffühler 1
    vf2 = temperature(40014)  # Vorlauffühler 2
    vf3 = temperature(40015)  # Vorlauffühler 3
    vf4 = temperature(40016)  # Vorlauffühler 4

    ruef1 = temperature(40017)  # Rücklauffühler 1
    ruef2 = temperature(40018)  # Rücklauffühler 2
    ruef3 = temperature(40019)  # Rücklauffühler 3

    rf1 = temperature(40020)  # Raumfühler 1
    rf2 = temperature(40021)  # Raumfühler 2
    rf3 = temperature(40022)  # Raumfühler 3

    sf1 = temperature(40023)  # Speicherfühler 1
    sf2 = temperature(40024)  # Speicherfühler 2
    sf3_fg3 = temperature(40025)  # Speicherfühler/Ferngeber 3

    fg1 = temperature(40026, unit="K")  # Ferngeber 1
    fg2 = temperature(40027, unit="K")  # Ferngeber 2

    @property
    def detected_sensor_names(self) -> tuple[str, ...]:
        """Return sensor fields that currently have a valid value."""
        return tuple(
            name
            for name in self._register_fields
            if getattr(self, name) is not None
        )