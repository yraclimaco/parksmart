"""Facts the website states must match the backend they describe.

The landing page (synced into frontend/) quotes figures and rules from this repo. When
the registry, the permit rules or the evaluation change, these tests fail until the
website is updated in ParkSmart-Website and synced, instead of the site going quietly
out of date.
"""

import re
from datetime import datetime
from pathlib import Path

import pytest

from src.eligibility import (ALLOWED, NEEDS_VERIFICATION, NOT_ALLOWED,
                             check_eligibility)
from src.location_registry import load_registry

REPO = Path(__file__).resolve().parent.parent
COMPONENTS = REPO / "frontend" / "src" / "components"
EVALUATION_DOC = REPO / "docs" / "issue18_predictions.md"

pytestmark = pytest.mark.skipif(not COMPONENTS.exists(),
                                reason="frontend/ not present")

# PermitMap.tsx's example arrival times (UCSD local time), keyed as in its ACCESS table.
PERMIT_MAP_TIMES = {
    "weekday10": datetime(2026, 11, 18, 10, 0),
    "weekday18": datetime(2026, 11, 18, 18, 0),
    "sat12": datetime(2026, 11, 21, 12, 0),
}
# Column order of each ACCESS string, and the letter used for each status.
PERMIT_MAP_STALLS = ("A", "B", "S", "SR", "D", "Visitor")
PERMIT_MAP_LETTERS = {ALLOWED: "y", NEEDS_VERIFICATION: "c", NOT_ALLOWED: "n"}


def _read(name):
    return (COMPONENTS / name).read_text()


def test_landing_lot_count_matches_recommendable_locations():
    """'N campus lots and structures' is the number ParkSmart can recommend."""
    match = re.search(r"'(\d+) campus lots and structures'",
                      _read("LandingPage.tsx"))
    assert match, "lot count line not found in LandingPage.tsx"
    supported = [loc for loc in load_registry()
                 if loc["registry_status"] == "supported"]
    assert int(match.group(1)) == len(supported)


def test_permit_map_uses_the_real_permit_rules():
    """The landing permit map shows exactly what check_eligibility decides."""
    source = _read("PermitMap.tsx")
    shown = {}
    for time_key, row in re.findall(r"(\w+): \{ (A: '[^}]*') \}", source):
        shown[time_key] = dict(re.findall(r"(\w+): '([ycn]+)'", row))
    assert set(shown) == set(PERMIT_MAP_TIMES), "ACCESS table not found"
    for time_key, arrival in PERMIT_MAP_TIMES.items():
        for permit, letters in shown[time_key].items():
            expected = "".join(
                PERMIT_MAP_LETTERS[check_eligibility(permit, stall, "", arrival)
                                   .status]
                for stall in PERMIT_MAP_STALLS)
            assert letters == expected, (time_key, permit)


def _holdout_figures():
    """Supported-holdout figures from the evaluation write-up."""
    doc = EVALUATION_DOC.read_text()
    supported = re.search(
        r"Holdout supported: ([\d,]+) readings, [\d,]+ near-full; "
        r"baseline MAE ([\d.]+) pp, near-full MAE ([\d.]+) pp", doc)
    unsupported = re.search(
        r"Holdout unsupported_experimental: ([\d,]+) readings", doc)
    dataset = re.search(r"Dataset: ([\d,]+) readings", doc)
    bias = re.search(r"Holdout supported near-full bias: mean forecast ([\d.]+)% "
                     r"open vs ([\d.]+)% actual", doc)
    assert supported and unsupported and dataset and bias, \
        "figures not found in the doc"
    return {
        "tested": supported.group(1),
        "mae": round(float(supported.group(2))),
        "near_full_mae": round(float(supported.group(3))),
        "no_estimate": unsupported.group(1),
        "readings": dataset.group(1),
        "near_full_forecast": round(float(bias.group(1))),
        "near_full_actual": round(float(bias.group(2))),
    }


def test_accuracy_section_matches_the_evaluation():
    """The 'How accurate is it?' numbers are the documented holdout results."""
    figures = _holdout_figures()
    text = _read("EvidenceTest.tsx")
    # Errors are mean absolute errors in percentage points, not percentages or ranges.
    assert f"Off by {figures['mae']} points" in text
    assert f"off by {figures['mae']} percentage points" in text
    assert f"off by about {figures['near_full_mae']} points" in text
    assert f"{figures['tested']} counts in all" in text
    assert f"For {figures['no_estimate']} counts" in text
    # The holdout was inspected during development and forecasts overestimate
    # nearly full lots (docs/issue18_predictions.md); the copy must not claim otherwise.
    for claim in ("never seen", "40% to 80%", "Closer for full lots"):
        assert claim not in text, claim
    assert "look more open than they are" in text
    assert (f"about {figures['near_full_forecast']}% open against about "
            f"{figures['near_full_actual']}% in reality") in " ".join(text.split())


def test_how_it_works_reading_count_matches_the_dataset():
    assert f"{_holdout_figures()['readings']} readings" in _read("Pipeline.tsx")
