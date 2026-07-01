"""Reusable TROVIS option metadata."""

from __future__ import annotations

from .enums import OperatingMode, Weekday
from .metadata import OptionMetadata


# Writable operating-mode fields currently expose the proven user-facing subset.
# PROGRAM/AUTOMATIC are still part of OperatingMode for read-only rotary-switch
# values, but are not offered as writable select options here.
OPERATING_MODE_OPTIONS = (
    OptionMetadata("standby", int(OperatingMode.STANDBY), "Standby"),
    OptionMetadata("manual", int(OperatingMode.MANUAL), "Hand"),
    OptionMetadata("day", int(OperatingMode.DAY), "Sonne"),
    OptionMetadata("night", int(OperatingMode.NIGHT), "Mond"),
)


WEEKDAY_OPTIONS = (
    OptionMetadata("off", int(Weekday.OFF), "Aus"),
    OptionMetadata("monday", int(Weekday.MONDAY), "Montag"),
    OptionMetadata("tuesday", int(Weekday.TUESDAY), "Dienstag"),
    OptionMetadata("wednesday", int(Weekday.WEDNESDAY), "Mittwoch"),
    OptionMetadata("thursday", int(Weekday.THURSDAY), "Donnerstag"),
    OptionMetadata("friday", int(Weekday.FRIDAY), "Freitag"),
    OptionMetadata("saturday", int(Weekday.SATURDAY), "Samstag"),
    OptionMetadata("sunday", int(Weekday.SUNDAY), "Sonntag"),
)