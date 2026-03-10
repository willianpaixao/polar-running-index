"""Tests for FIT file parsing."""

from pathlib import Path

import pytest

from polar_running_index.fit_parser import parse_fit_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_FIT = FIXTURES_DIR / "treadmill_12km.FIT"


@pytest.fixture
def sample_activity():
    """Parse the sample FIT file."""
    return parse_fit_file(SAMPLE_FIT)


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
