"""Tests für die Farbschemata (themen.py)."""

from dataclasses import fields
from datetime import datetime

import pytest

from uni_dashboard import themen


@pytest.mark.parametrize(("stunde", "erwartet"), [
    (6, "Nacht"), (7, "Tag"), (12, "Tag"), (18, "Tag"), (19, "Nacht"), (23, "Nacht"), (0, "Nacht"),
])
def test_nach_uhrzeit(stunde: int, erwartet: str) -> None:
    assert themen.nach_uhrzeit(datetime(2026, 11, 5, stunde, 30)).name == erwartet


def test_themen_nach_name() -> None:
    assert list(themen.THEMEN) == ["Tag", "Nacht"]
    assert themen.THEMEN["Nacht"] is themen.NACHT


@pytest.mark.parametrize("thema", [themen.TAG, themen.NACHT])
def test_css_enthaelt_alle_farben(thema: themen.Thema) -> None:
    css = thema.css()
    assert css.startswith(":root {") and css.endswith("}")
    for feld in fields(thema):
        if feld.name not in ("name", "balken_offen"):
            assert getattr(thema, feld.name) in css, feld.name


@pytest.mark.parametrize("thema", [themen.TAG, themen.NACHT])
def test_akzent_ist_hexfarbe(thema: themen.Thema) -> None:
    # grafiken._rgba erwartet #rrggbb
    assert len(thema.akzent) == 7 and thema.akzent.startswith("#")
    int(thema.akzent[1:], 16)
