"""Unit tests for the Running Index algorithm."""

from datetime import datetime, timedelta

import pytest

from polar_running_index.models import ActivityData, ActivityRecord, LapBoundary
from polar_running_index.running_index import (
    VO2_REST,
    _build_km_boundaries,
    _formula_hrmax_ratio,
    _formula_hrr,
    _linear_regression_slope,
    _remove_outliers,
    calculate_running_index,
    calculate_segment_running_index,
    predict_race_times,
    vo2_demand_acsm,
    vo2_demand_patent,
)

# --- VO2 demand tests ---


class TestVo2DemandAcsm:
    def test_flat_running_10kmh(self):
        """10 km/h on flat ground: ~36.8 ml/kg/min (ACSM)."""
        speed_ms = 10.0 / 3.6  # 10 km/h -> m/s
        vo2 = vo2_demand_acsm(speed_ms, grade=0.0)
        # 0.2 * (10000/60) + 3.5 = 0.2 * 166.67 + 3.5 = 33.33 + 3.5 = 36.83
        assert 36.5 < vo2 < 37.2

    def test_flat_running_12kmh(self):
        """12 km/h on flat ground."""
        speed_ms = 12.0 / 3.6
        vo2 = vo2_demand_acsm(speed_ms, grade=0.0)
        # 0.2 * 200 + 3.5 = 43.5
        assert 43.0 < vo2 < 44.0

    def test_uphill_running(self):
        """Running uphill should increase VO2 demand."""
        speed_ms = 10.0 / 3.6
        vo2_flat = vo2_demand_acsm(speed_ms, grade=0.0)
        vo2_uphill = vo2_demand_acsm(speed_ms, grade=0.05)
        assert vo2_uphill > vo2_flat

    def test_resting_at_zero_speed(self):
        """At zero speed, VO2 should equal resting VO2."""
        vo2 = vo2_demand_acsm(0.0, grade=0.0)
        assert vo2 == pytest.approx(VO2_REST)


class TestVo2DemandPatent:
    def test_at_10kmh(self):
        """Patent coefficient: 3.2 * 10 = 32.0 ml/kg/min (net)."""
        speed_ms = 10.0 / 3.6
        vo2_net = vo2_demand_patent(speed_ms)
        assert vo2_net == pytest.approx(32.0, abs=0.1)

    def test_at_zero(self):
        """Zero speed should give zero net VO2."""
        assert vo2_demand_patent(0.0) == pytest.approx(0.0)


# --- Formula tests ---


class TestFormulaHrmaxRatio:
    def test_basic_calculation(self):
        """Formula 3: F = (HRmax/HR) * 3.2 * v_kmh + 3.5"""
        # 10 km/h, HR=150, HRmax=190
        speed_ms = 10.0 / 3.6
        ri = _formula_hrmax_ratio(speed_ms, hr=150, hr_max=190)
        # (190/150) * 32.0 + 3.5 = 1.2667 * 32.0 + 3.5 = 40.53 + 3.5 = 44.03
        assert ri == pytest.approx(44.03, abs=0.1)

    def test_higher_fitness(self):
        """Lower HR at same speed should give higher RI."""
        speed_ms = 10.0 / 3.6
        ri_low_hr = _formula_hrmax_ratio(speed_ms, hr=130, hr_max=190)
        ri_high_hr = _formula_hrmax_ratio(speed_ms, hr=160, hr_max=190)
        assert ri_low_hr > ri_high_hr

    def test_faster_speed(self):
        """Higher speed at same HR should give higher RI."""
        ri_slow = _formula_hrmax_ratio(2.5, hr=150, hr_max=190)
        ri_fast = _formula_hrmax_ratio(3.5, hr=150, hr_max=190)
        assert ri_fast > ri_slow


class TestFormulaHrr:
    def test_basic_calculation(self):
        """Formula 4: F = ((HRmax-HRrest)/(HR-HRrest)) * 3.2 * v_kmh + 3.5"""
        # 10 km/h, HR=150, HRmax=190, HRrest=50
        speed_ms = 10.0 / 3.6
        ri = _formula_hrr(speed_ms, hr=150, hr_max=190, hr_rest=50)
        # ((190-50)/(150-50)) * 32.0 + 3.5 = 1.4 * 32.0 + 3.5 = 44.8 + 3.5 = 48.3
        assert ri == pytest.approx(48.3, abs=0.1)

    def test_higher_fitness(self):
        """Lower HR at same speed should give higher RI."""
        speed_ms = 10.0 / 3.6
        ri_low = _formula_hrr(speed_ms, hr=130, hr_max=190, hr_rest=50)
        ri_high = _formula_hrr(speed_ms, hr=160, hr_max=190, hr_rest=50)
        assert ri_low > ri_high

    def test_hrr_accounts_for_resting_hr(self):
        """HRR method should give different results for different resting HRs.

        With formula ((HRmax-HRrest)/(HR-HRrest)) * VO2_net + 3.5:
        A higher resting HR makes (HR-HRrest) smaller relative to the reserve,
        meaning the runner is using a larger fraction of their reserve at the
        same exercise HR — so the extrapolated VO2max is higher.
        """
        speed_ms = 10.0 / 3.6
        ri_low_rest = _formula_hrr(speed_ms, hr=150, hr_max=190, hr_rest=40)
        ri_high_rest = _formula_hrr(speed_ms, hr=150, hr_max=190, hr_rest=60)
        # Different resting HRs should produce different RI values
        assert ri_low_rest != ri_high_rest
        # Higher resting HR -> higher extrapolated VO2max at same exercise HR
        assert ri_high_rest > ri_low_rest


# --- Utility function tests ---


class TestLinearRegressionSlope:
    def test_positive_slope(self):
        slope = _linear_regression_slope([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert slope == pytest.approx(2.0)

    def test_zero_slope(self):
        slope = _linear_regression_slope([1, 2, 3], [5, 5, 5])
        assert slope == pytest.approx(0.0)

    def test_negative_slope(self):
        slope = _linear_regression_slope([1, 2, 3], [6, 4, 2])
        assert slope == pytest.approx(-2.0)

    def test_single_point(self):
        slope = _linear_regression_slope([1], [5])
        assert slope == pytest.approx(0.0)

    def test_empty(self):
        slope = _linear_regression_slope([], [])
        assert slope == pytest.approx(0.0)


class TestRemoveOutliers:
    def test_no_outliers(self):
        values = [48, 49, 50, 51, 52]
        result = _remove_outliers(values)
        assert len(result) == 5

    def test_removes_extreme_outlier(self):
        values = [48, 49, 50, 51, 52, 150]
        result = _remove_outliers(values)
        assert 150 not in result

    def test_preserves_small_list(self):
        values = [48, 49, 50]
        result = _remove_outliers(values)
        assert result == values

    def test_empty_list(self):
        assert _remove_outliers([]) == []


# --- Integration: calculate_running_index ---


def _make_activity(
    n_records: int = 3000,
    speed_ms: float = 3.1,
    hr_start: int = 140,
    hr_end: int = 165,
    start_elapsed: float = 0.0,
) -> ActivityData:
    """Create a synthetic activity for testing."""
    start = datetime(2026, 3, 4, 18, 0, 0)
    records = []
    for i in range(n_records):
        t = start_elapsed + float(i)
        # Linear HR progression
        frac = i / max(n_records - 1, 1)
        hr = int(hr_start + frac * (hr_end - hr_start))
        records.append(
            ActivityRecord(
                timestamp=start + timedelta(seconds=t),
                heart_rate=hr,
                speed=speed_ms,
                distance=speed_ms * t,
                elapsed_seconds=t,
            )
        )
    return ActivityData(
        records=records,
        sport="running",
        sub_sport="treadmill",
        start_time=start,
        total_duration=float(n_records),
        total_distance=speed_ms * n_records,
    )


class TestCalculateRunningIndex:
    def test_basic_hrr(self):
        """Basic HRR calculation should produce a reasonable RI."""
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        result = calculate_running_index(
            activity, hr_max=190, hr_rest=50, method="hrr", drift_correction=False
        )
        # 3.1 m/s = 11.16 km/h, avg HR ~152, should give RI around 40-60
        assert 30 < result.running_index < 70
        assert result.method == "hrr"
        assert not result.drift_corrected

    def test_basic_hrmax_ratio(self):
        """Basic HRmax ratio calculation."""
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        result = calculate_running_index(
            activity,
            hr_max=190,
            hr_rest=50,
            method="hrmax_ratio",
            drift_correction=False,
        )
        assert 30 < result.running_index < 70
        assert result.method == "hrmax_ratio"

    def test_drift_correction_reduces_variance(self):
        """Drift correction should reduce variance in RI estimates."""
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        result_no_drift = calculate_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        result_drift = calculate_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=True
        )
        # With drift correction, stdev should be lower or comparable
        assert (
            result_drift.summary_stats["stdev"]
            <= result_no_drift.summary_stats["stdev"] + 1.0
        )

    def test_faster_runner_higher_ri(self):
        """Faster speed at same HR should give higher RI."""
        slow = _make_activity(speed_ms=2.8, hr_start=155, hr_end=165)
        fast = _make_activity(speed_ms=3.5, hr_start=155, hr_end=165)
        ri_slow = calculate_running_index(
            slow, hr_max=190, hr_rest=50, drift_correction=False
        )
        ri_fast = calculate_running_index(
            fast, hr_max=190, hr_rest=50, drift_correction=False
        )
        assert ri_fast.running_index > ri_slow.running_index

    def test_invalid_method(self):
        activity = _make_activity()
        with pytest.raises(ValueError, match="method"):
            calculate_running_index(activity, hr_max=190, hr_rest=50, method="invalid")

    def test_invalid_hr_params(self):
        activity = _make_activity()
        with pytest.raises(ValueError):
            calculate_running_index(activity, hr_max=50, hr_rest=60)

    def test_no_valid_records(self):
        """Activity with all records outside the valid window should fail."""
        # All records in first 2 minutes (before the 3-min window)
        activity = _make_activity(n_records=120, start_elapsed=0.0)
        with pytest.raises(ValueError, match="No valid records"):
            calculate_running_index(activity, hr_max=190, hr_rest=50)

    def test_summary_stats_populated(self):
        activity = _make_activity()
        result = calculate_running_index(activity, hr_max=190, hr_rest=50)
        assert "mean" in result.summary_stats
        assert "median" in result.summary_stats
        assert "stdev" in result.summary_stats
        assert "n_total" in result.summary_stats
        assert "n_filtered" in result.summary_stats
        assert "n_outliers" in result.summary_stats


# --- Race time prediction ---


class TestPredictRaceTimes:
    def test_returns_four_distances(self):
        preds = predict_race_times(50.0)
        assert len(preds) == 4
        names = [p[0] for p in preds]
        assert "5K" in names
        assert "10K" in names
        assert "Half Marathon" in names
        assert "Marathon" in names

    def test_longer_distances_take_more_time(self):
        preds = predict_race_times(50.0)
        times = [p[2] for p in preds]
        assert times == sorted(times)

    def test_higher_ri_means_faster_times(self):
        preds_low = predict_race_times(40.0)
        preds_high = predict_race_times(60.0)
        for (_, _, t_low), (_, _, t_high) in zip(preds_low, preds_high, strict=False):
            assert t_high < t_low

    def test_zero_ri_returns_empty(self):
        assert predict_race_times(0.0) == []

    def test_reasonable_5k_time(self):
        """VO2max of 50 should give a ~24-28 min 5K."""
        preds = predict_race_times(50.0)
        five_k = next(p for p in preds if p[0] == "5K")
        assert 20 * 60 < five_k[2] < 35 * 60


# --- Segment analysis ---


class TestBuildKmBoundaries:
    def test_produces_correct_number(self):
        """3 km activity should produce 3 km boundaries."""
        activity = _make_activity(n_records=1200, speed_ms=3.0, start_elapsed=0.0)
        boundaries = _build_km_boundaries(activity.records)
        # 1200s * 3.0 m/s = 3600m -> 3 full km + partial
        assert len(boundaries) == 4  # Km 1, 2, 3, partial Km 4

    def test_labels_are_sequential(self):
        activity = _make_activity(n_records=1200, speed_ms=3.0, start_elapsed=0.0)
        boundaries = _build_km_boundaries(activity.records)
        labels = [b[0] for b in boundaries]
        assert labels[0] == "Km 1"
        assert labels[1] == "Km 2"
        assert labels[2] == "Km 3"

    def test_empty_records(self):
        assert _build_km_boundaries([]) == []


class TestCalculateSegmentRunningIndex:
    def test_km_fallback_when_single_lap(self):
        """With no laps (or 1 lap), should use per-km segmentation."""
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        segments = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        assert len(segments) > 0
        assert all(s.label.startswith("Km") for s in segments)

    def test_lap_segmentation_when_multiple_laps(self):
        """With multiple laps, should use lap boundaries."""
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        activity.laps = [
            LapBoundary(start_elapsed=180.0, end_elapsed=600.0),
            LapBoundary(start_elapsed=600.0, end_elapsed=1200.0),
            LapBoundary(start_elapsed=1200.0, end_elapsed=1800.0),
        ]
        segments = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        assert len(segments) == 3
        assert segments[0].label == "Lap 1"
        assert segments[1].label == "Lap 2"
        assert segments[2].label == "Lap 3"

    def test_segment_ri_in_plausible_range(self):
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        segments = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        for seg in segments:
            assert 25 < seg.running_index < 85, (
                f"{seg.label}: RI {seg.running_index} out of range"
            )

    def test_segment_has_positive_distance(self):
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        segments = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        for seg in segments:
            assert seg.distance_meters > 0, f"{seg.label}: zero distance"

    def test_segments_cover_valid_window(self):
        """Segment time ranges should be within the valid window."""
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        segments = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        assert segments[0].start_seconds >= 180.0  # valid window start

    def test_skips_segments_with_few_records(self):
        """Segments with < 10 records should be skipped."""
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        # Create laps where one is very short (5 seconds)
        activity.laps = [
            LapBoundary(start_elapsed=180.0, end_elapsed=185.0),
            LapBoundary(start_elapsed=185.0, end_elapsed=1000.0),
        ]
        segments = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        # First lap is too short, should be skipped
        assert len(segments) == 1
        assert segments[0].label == "Lap 2"

    def test_empty_when_no_valid_records(self):
        """Activity with all records outside valid window should return []."""
        activity = _make_activity(
            n_records=100, speed_ms=3.1, hr_start=140, hr_end=165, start_elapsed=0.0
        )
        # Only 100 records starting at 0s -- all before 180s valid window
        segments = calculate_segment_running_index(activity, hr_max=190, hr_rest=50)
        assert segments == []

    def test_drift_correction_applied(self):
        """Segments with drift correction should differ from without."""
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        seg_drift = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=True
        )
        seg_no_drift = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        # At least one segment should differ
        assert any(
            abs(a.running_index - b.running_index) > 0.01
            for a, b in zip(seg_drift, seg_no_drift, strict=False)
        )

    def test_pace_min_per_km_format(self):
        activity = _make_activity(
            n_records=3000, speed_ms=3.1, hr_start=140, hr_end=165
        )
        segments = calculate_segment_running_index(
            activity, hr_max=190, hr_rest=50, drift_correction=False
        )
        for seg in segments:
            assert ":" in seg.pace_min_per_km
