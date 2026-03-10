"""Tests for FIT file parsing."""

from pathlib import Path

import pytest

from polar_running_index.fit_parser import parse_fit_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"
HALF_MARATHON_FIT = FIXTURES_DIR / "outdoor_half_marathon.FIT"
MARATHON_FIT = FIXTURES_DIR / "outdoor_marathon.FIT"
SAMPLE_FIT = FIXTURES_DIR / "treadmill_12km.FIT"


@pytest.fixture
def sample_activity():
    """Parse the sample FIT file."""
    return parse_fit_file(SAMPLE_FIT)


@pytest.fixture
def marathon_activity():
    """Parse the marathon FIT file."""
    return parse_fit_file(MARATHON_FIT)


@pytest.fixture
def half_marathon_activity():
    """Parse the half marathon FIT file."""
    return parse_fit_file(HALF_MARATHON_FIT)


class TestParseFitFile:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_fit_file("/nonexistent/file.fit")

    def test_parses_sport(self, sample_activity):
        assert sample_activity.sport == "running"

    def test_parses_sub_sport(self, sample_activity):
        assert sample_activity.sub_sport == "treadmill"

    def test_record_count(self, sample_activity):
        """The sample file has 3862 records."""
        assert len(sample_activity.records) == 3862

    def test_total_distance(self, sample_activity):
        """Total distance should be ~12016 meters."""
        assert 12000 < sample_activity.total_distance < 12100

    def test_total_duration(self, sample_activity):
        """Total timer time should be ~3861 seconds."""
        assert 3800 < sample_activity.total_duration < 3900

    def test_heart_rate_range(self, sample_activity):
        """HR should range from ~112 to ~167 bpm."""
        assert sample_activity.avg_heart_rate > 150
        assert sample_activity.max_heart_rate <= 170
        min_hr = min(r.heart_rate for r in sample_activity.records)
        assert min_hr >= 100

    def test_speed_values(self, sample_activity):
        """Average speed should be ~3.1 m/s."""
        assert 2.5 < sample_activity.avg_speed < 3.5

    def test_records_have_elapsed_seconds(self, sample_activity):
        """All records should have elapsed_seconds set."""
        for r in sample_activity.records:
            assert r.elapsed_seconds >= 0

    def test_records_sorted_by_time(self, sample_activity):
        """Records should be sorted by elapsed_seconds."""
        elapsed = [r.elapsed_seconds for r in sample_activity.records]
        assert elapsed == sorted(elapsed)

    def test_pace_format(self, sample_activity):
        """Pace string should be formatted as M:SS."""
        pace = sample_activity.pace_min_per_km
        assert ":" in pace
        parts = pace.split(":")
        assert len(parts) == 2

    def test_duration_str(self, sample_activity):
        """Duration string should be formatted."""
        dur = sample_activity.duration_str
        assert "m" in dur


class TestParseMarathonFit:
    """Tests for the outdoor marathon FIT fixture."""

    def test_parses_sport(self, marathon_activity):
        assert marathon_activity.sport == "running"

    def test_parses_sub_sport(self, marathon_activity):
        assert marathon_activity.sub_sport == "generic"

    def test_record_count(self, marathon_activity):
        """The marathon file has 16337 records."""
        assert len(marathon_activity.records) == 16337

    def test_total_distance(self, marathon_activity):
        """Total distance should be ~43111 meters."""
        assert 43000 < marathon_activity.total_distance < 43200

    def test_total_duration(self, marathon_activity):
        """Total timer time should be ~16337 seconds (~4h 32m)."""
        assert 16300 < marathon_activity.total_duration < 16400

    def test_heart_rate_range(self, marathon_activity):
        """Avg HR ~161, max HR 169."""
        assert 155 < marathon_activity.avg_heart_rate < 165
        assert marathon_activity.max_heart_rate == 169

    def test_speed_values(self, marathon_activity):
        """Average speed should be ~2.6 m/s (~9.5 km/h)."""
        assert 2.4 < marathon_activity.avg_speed < 2.9

    def test_duration_str_has_hours(self, marathon_activity):
        """Marathon duration should include hours."""
        dur = marathon_activity.duration_str
        assert "h" in dur

    def test_no_gps_data(self, marathon_activity):
        """Anonymized fixture should have no GPS fields (None or missing)."""
        # GPS is stripped during PII removal — records should not have lat/lon
        for r in marathon_activity.records:
            assert not hasattr(r, "position_lat")
            assert not hasattr(r, "position_long")


class TestParseHalfMarathonFit:
    """Tests for the outdoor half marathon FIT fixture."""

    def test_parses_sport(self, half_marathon_activity):
        assert half_marathon_activity.sport == "running"

    def test_parses_sub_sport(self, half_marathon_activity):
        assert half_marathon_activity.sub_sport == "generic"

    def test_record_count(self, half_marathon_activity):
        """The half marathon file has 8051 valid records (8062 total, 11 filtered)."""
        assert len(half_marathon_activity.records) == 8051

    def test_total_distance(self, half_marathon_activity):
        """Total distance should be ~21513 meters."""
        assert 21400 < half_marathon_activity.total_distance < 21600

    def test_total_duration(self, half_marathon_activity):
        """Total timer time should be ~8062 seconds (~2h 14m)."""
        assert 8000 < half_marathon_activity.total_duration < 8100

    def test_heart_rate_range(self, half_marathon_activity):
        """Avg HR ~171, max HR 179."""
        assert 168 < half_marathon_activity.avg_heart_rate < 175
        assert half_marathon_activity.max_heart_rate == 179

    def test_speed_values(self, half_marathon_activity):
        """Average speed should be ~2.67 m/s (~9.6 km/h)."""
        assert 2.4 < half_marathon_activity.avg_speed < 2.9

    def test_duration_str_has_hours(self, half_marathon_activity):
        """Half marathon duration should include hours."""
        dur = half_marathon_activity.duration_str
        assert "h" in dur

    def test_no_gps_data(self, half_marathon_activity):
        """Anonymized fixture should have no GPS fields."""
        for r in half_marathon_activity.records:
            assert not hasattr(r, "position_lat")
            assert not hasattr(r, "position_long")
