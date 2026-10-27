"""Check analysis aggregation and exported benchmark artifacts."""

import pandas as pd
import pytest

from src.parking_analysis import build_eda_tables, export_analysis
from src.parking_benchmarks import load_analysis_dataset
from tests.test_parking_benchmarks import sample_records


def analysis_records():
    """Return prepared sample readings with pipeline metadata for reporting."""
    return sample_records().assign(
        quality_flag="pass", label_status="keep_separate", capacity_source="qpass"
    )


def test_csv_loader_preserves_text_identifiers(tmp_path):
    records = analysis_records()
    records["facility"] = "001"
    path = tmp_path / "analysis.csv"
    records.to_csv(path, index=False)
    actual = load_analysis_dataset(path)
    assert actual.facility.eq("001").all()
    assert actual.level.eq("").all()
    assert len(actual) == len(records)


def test_eda_counts_and_weighting():
    records = analysis_records()
    tables = build_eda_tables(records)
    for table in tables.values():
        assert table.readings.sum() == len(records)
    assert tables["facility"].mean_available.iloc[0] == pytest.approx(0.5)


def test_export_has_same_test_ids_and_complete_metrics(tmp_path):
    records = analysis_records()
    result, _ = export_analysis(records, tmp_path)
    predictions = pd.read_csv(tmp_path / "test_predictions.csv")
    assert predictions.record_id.tolist() == result["test"].record_id.tolist()
    assert len(predictions) == 2
    metrics = pd.read_csv(tmp_path / "metrics.csv", index_col="method")
    assert set(metrics.index) == {"historical_average", "linear_regression"}
    assert metrics.test_readings.eq(len(predictions)).all()
    assert metrics.near_full_readings.eq(0).all()
    assert metrics.near_full_mae_pp.isna().all()
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "human coordination remains pending" in summary
    assert "first weeks of quarters" in summary
