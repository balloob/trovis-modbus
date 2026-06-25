"""Global temperature inputs."""

from __future__ import annotations

from .model import TrovisComponent, temperature


class Sensors(TrovisComponent):
    """
    Physical sensor inputs, e.g. Pt1000.
    Naming follows the manual abbreviations.
    """

    af1 = temperature(9)  # AußenFühler 1 - outside_1
    af2 = temperature(10)  # AußenFühler 2 - outside_2

    vf1 = temperature(12)  # VorlaufFühler 1 - flow_1
    vf2 = temperature(13)  # VorlaufFühler 2 - flow_2
    vf3 = temperature(14)  # VorlaufFühler 3 - flow_3
    vf4 = temperature(15)  # VorlaufFühler 4 - flow_4

    ruef1 = temperature(16)  # RücklaufFühler 1 - return_1
    ruef2 = temperature(17)  # RücklaufFühler 2 - return_2
    ruef3 = temperature(18)  # RücklaufFühler 3 - return_3

    rf1 = temperature(19)  # RaumFühler 1 - room_1
    rf2 = temperature(20)  # RaumFühler 2 - room_2
    rf3 = temperature(21)  # RaumFühler 3 - room_3

    sf1 = temperature(22)  # SpeicherFühler 1 - water_storage_1
    sf2 = temperature(23)  # SpeicherFühler 2 - water_storage_2
    sf3_fg3 = temperature(24)  # SpeicherFühler/FernGeber 3 - water_storage_or_remote_3

    fg1 = temperature(25, unit="K")  # FernGeber 1 - remote_1
    fg2 = temperature(26, unit="K")  # FernGeber 2 - remote_2
