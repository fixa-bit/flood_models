"""Unit tests for the coverage logic. Uses small in-memory test series, never project data."""
import pandas as pd

from audit_data_readiness import coverage


def test_counts_gaps_without_filling():
    dates = pd.date_range("2020-01-01", "2020-01-10", freq="D")
    values = [1, 2, None, None, None, 6, 7, 8, 9, 10]
    result = coverage(pd.Series(dates), pd.Series(values))
    assert result["n_valid_days"] == 7
    assert result["span_days"] == 10
    assert result["longest_internal_gap_days"] == 3
    assert result["completeness_within_span"] == 0.7


def test_flood_season_only_and_complete_years():
    dates = pd.date_range("2024-06-01", "2024-09-30", freq="D")
    result = coverage(pd.Series(dates), pd.Series(range(len(dates))))
    assert result["flood_season_only"] is True
    assert result["years_at_least_90pct_complete"] == []

    full = pd.date_range("2016-01-01", "2016-12-31", freq="D")
    result = coverage(pd.Series(full), pd.Series(1.0, index=range(len(full))))
    assert result["years_at_least_90pct_complete"] == [2016]
    assert result["flood_season_only"] is False


def test_duplicate_dates_counted_once_and_windows():
    dates = pd.Series(["2014-12-31", "2014-12-31", "2015-01-01"])
    result = coverage(dates, pd.Series([1.0, 1.0, 2.0]))
    assert result["n_valid_days"] == 2
    assert result["valid_days_in_window"]["cmip6_historical_reference_1985_2014"] == 1
    assert result["valid_days_in_window"]["observed_validation_2015_2025"] == 1
