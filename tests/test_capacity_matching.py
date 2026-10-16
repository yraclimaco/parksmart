"""Check that capacity candidates require all four matching keys."""

import pandas as pd
import pytest

import src.compare_capacities as comparison


@pytest.mark.parametrize(
    "year, quarter, facility, category, should_match",
    [
        ("2025-2026", "Fall", "P100", "A", True),
        ("2025-2026", "Winter", "P100", "A", False),
        ("2024-2025", "Fall", "P100", "A", False),
        ("2025-2026", "Fall", "P200", "A", False),
        ("2025-2026", "Fall", "P100", "B", False),
    ],
)
def test_capacity_requires_all_four_keys(
    tmp_path,
    monkeypatch,
    year,
    quarter,
    facility,
    category,
    should_match,
):
    """Keep mismatched periods, facilities, and categories unmatched."""
    inventory_path = tmp_path / "inventory.csv"

    pd.DataFrame([{
        "academic_year": "2025-2026",
        "quarter": "Fall",
        "facility_raw": "P100",
        "category_raw": "A",
        "capacity": 25,
        "source_file": "inventory_example.xlsm",
        "source_rows": "5",
    }]).to_csv(inventory_path, index=False)

    qpass = pd.DataFrame([{
        "academic_year": year,
        "quarter": quarter,
        "location": facility,
        "type": category,
        "sub_type": None,
        "level": None,
        "date": pd.Timestamp("2025-09-29"),
        "open_8am": 5,
        "open_10am": 4,
        "open_12pm": 3,
        "open_2pm": 2,
        "total_stall_count": 0,
        "source_file": "qpass_example.xlsm",
        "sheet_name": "Example",
        "source_row": 3,
    }])

    # Use controlled loader output and write reports in a temporary folder.
    monkeypatch.setattr(
        comparison,
        "load_qpass",
        lambda path: qpass.copy(),
    )
    monkeypatch.chdir(tmp_path)

    comparison.compare_capacities(
        inventory_path,
        tmp_path / "qpass_example.xlsm",
    )

    result = pd.read_csv(
        tmp_path
        / "results"
        / "capacity_matching"
        / "capacity_comparison.csv"
    )

    assert len(result) == 4

    if should_match:
        assert result["_merge"].eq("both").all()
        assert result["candidate_capacity"].eq(25).all()
    else:
        assert result["_merge"].eq("left_only").all()
        assert result["candidate_capacity"].isna().all()

    # Finding a candidate does not establish historical verification.
    assert result["matched_capacity"].isna().all()