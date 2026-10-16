"""Tests for Inventory capacity validation."""

import pandas as pd
import pytest

from src.clean_inventory import capacity_status


@pytest.mark.parametrize(
    "raw_values, expected_capacity, expected_status",
    [
        ([None, None], None, "missing"),
        ([34, None], 34, "positive_unverified"),
        ([34, 34], None, "multiple_totals_review"),
        ([34, 40], None, "multiple_totals_review"),
        ([0], 0, "zero_review"),
        ([-2], None, "invalid_capacity"),
        ([3.5], None, "invalid_capacity"),
        (["bad"], None, "invalid_numeric"),
        (["34"], 34, "positive_unverified"),
    ],
)
def test_capacity_status(
    raw_values,
    expected_capacity,
    expected_status,
):
    """Reject uncertain totals and preserve valid numeric candidates."""
    values = pd.Series(raw_values, dtype=object)

    capacity, status = capacity_status(values)

    assert status == expected_status

    if expected_capacity is None:
        assert pd.isna(capacity)
    else:
        assert capacity == expected_capacity