"""End-to-end tests that invoke the CLI as a subprocess.

These tests run the installed ``polar-running-index`` entry point against
the fixture FIT files and validate the full pipeline: file parsing,
Running Index calculation, and output formatting.

Fixture-specific test classes are ordered from shortest to longest activity:
treadmill 12 km, treadmill 15 km, outdoor half marathon 21 km, outdoor marathon 43 km.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_12KM = FIXTURES_DIR / "treadmill_12km.FIT"
FIXTURE_15KM = FIXTURES_DIR / "treadmill_15km.FIT"
FIXTURE_HALF_MARATHON = FIXTURES_DIR / "outdoor_half_marathon.FIT"
FIXTURE_MARATHON = FIXTURES_DIR / "outdoor_marathon.FIT"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI as a subprocess and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "polar_running_index.cli", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestE2eTextOutput:
    """End-to-end tests for the default text output."""

    def test_12km_default(self):
        result = run_cli(str(FIXTURE_12KM), "--hr-max", "190", "--hr-rest", "50")
        assert result.returncode == 0
        assert "Running Index Report" in result.stdout
        assert "Running Index:" in result.stdout
        assert "Method:" in result.stdout
        assert "Level:" in result.stdout
        assert "Statistics:" in result.stdout

    def test_text_output_contains_activity_info(self):
        result = run_cli(str(FIXTURE_12KM), "--hr-max", "190", "--hr-rest", "50")
        assert result.returncode == 0
        assert "Activity:" in result.stdout
        assert "Duration:" in result.stdout
        assert "Distance:" in result.stdout
        assert "Avg Speed:" in result.stdout
        assert "Avg HR:" in result.stdout
        assert "Max HR:" in result.stdout
        assert "Parameters:" in result.stdout


class TestE2eJsonOutput:
    """End-to-end tests for JSON output."""

    def test_12km_json_structure(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Top-level keys
        assert "running_index" in data
        assert "method" in data
        assert "drift_corrected" in data
        assert "performance_level" in data
        assert "activity" in data
        assert "parameters" in data
        assert "statistics" in data
        assert "valid_window" in data

        # Activity details
        assert data["activity"]["sport"] == "running"
        assert data["activity"]["sub_sport"] == "treadmill"
        assert data["activity"]["distance_meters"] > 0
        assert data["activity"]["duration_seconds"] > 0
        assert data["activity"]["avg_heart_rate"] > 0
        assert data["activity"]["max_heart_rate"] > 0

        # Parameters echoed back
        assert data["parameters"]["hr_max"] == 190
        assert data["parameters"]["hr_rest"] == 50


class TestE2eRunningIndexValues:
    """Validate that Running Index values are physiologically reasonable."""

    @pytest.fixture
    def result_12km_hrr(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--json",
        )
        assert result.returncode == 0
        return json.loads(result.stdout)

    @pytest.fixture
    def result_12km_hrmax(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--method",
            "hrmax_ratio",
            "--json",
        )
        assert result.returncode == 0
        return json.loads(result.stdout)

    def test_ri_in_plausible_range(self, result_12km_hrr):
        """RI should be in a physiologically plausible range."""
        ri = result_12km_hrr["running_index"]
        assert 25 < ri < 85, f"RI {ri} is outside plausible range"

    def test_hrr_and_hrmax_in_same_ballpark(self, result_12km_hrr, result_12km_hrmax):
        """Both methods should produce values within ~15 of each other."""
        ri_hrr = result_12km_hrr["running_index"]
        ri_hrmax = result_12km_hrmax["running_index"]
        assert abs(ri_hrr - ri_hrmax) < 15

    def test_method_field_matches(self, result_12km_hrr, result_12km_hrmax):
        assert result_12km_hrr["method"] == "hrr"
        assert result_12km_hrmax["method"] == "hrmax_ratio"

    def test_statistics_are_consistent(self, result_12km_hrr):
        stats = result_12km_hrr["statistics"]
        assert stats["min"] <= stats["mean"] <= stats["max"]
        assert stats["min"] <= stats["median"] <= stats["max"]
        assert stats["stdev"] >= 0
        assert stats["n_filtered"] > 0
        assert stats["n_filtered"] <= stats["n_total"]
        assert stats["n_outliers"] >= 0
        assert stats["n_total"] == stats["n_filtered"] + stats["n_outliers"]

    def test_performance_level_is_valid(self, result_12km_hrr):
        valid_levels = {
            "Very Low",
            "Low",
            "Fair",
            "Average",
            "Good",
            "Very Good",
            "Excellent",
            "Elite",
        }
        assert result_12km_hrr["performance_level"] in valid_levels


class TestE2eDriftCorrection:
    """Verify drift correction affects results as expected."""

    @pytest.fixture
    def result_with_drift(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--json",
        )
        assert result.returncode == 0
        return json.loads(result.stdout)

    @pytest.fixture
    def result_without_drift(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--no-drift-correction",
            "--json",
        )
        assert result.returncode == 0
        return json.loads(result.stdout)

    def test_drift_flag_reflected(self, result_with_drift, result_without_drift):
        assert result_with_drift["drift_corrected"] is True
        assert result_without_drift["drift_corrected"] is False

    def test_drift_changes_result(self, result_with_drift, result_without_drift):
        """Drift correction should produce a different RI value."""
        ri_with = result_with_drift["running_index"]
        ri_without = result_without_drift["running_index"]
        # They should differ (drift correction adjusts for HR creep)
        assert ri_with != ri_without

    def test_both_results_plausible(self, result_with_drift, result_without_drift):
        assert 25 < result_with_drift["running_index"] < 85
        assert 25 < result_without_drift["running_index"] < 85


class TestE2eComparison:
    """End-to-end tests for the --polar-ri comparison feature."""

    def test_text_output_includes_comparison(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--polar-ri",
            "50",
        )
        assert result.returncode == 0
        assert "Comparison with Polar" in result.stdout
        assert "Polar RI:" in result.stdout
        assert "Calculated:" in result.stdout
        assert "Difference:" in result.stdout

    def test_json_output_includes_comparison(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--polar-ri",
            "50",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "comparison" in data
        comp = data["comparison"]
        assert comp["polar_ri"] == 50.0
        assert isinstance(comp["delta"], (int, float))
        assert isinstance(comp["delta_percent"], (int, float))
        assert comp["calculated_ri"] == data["running_index"]

    def test_no_comparison_without_flag(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "comparison" not in data

    def test_text_no_comparison_without_flag(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
        )
        assert result.returncode == 0
        assert "Comparison with Polar" not in result.stdout

    def test_delta_sign_when_lower(self):
        """When our RI is lower than Polar's, delta should be negative."""
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--polar-ri",
            "99",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["comparison"]["delta"] < 0
        assert data["comparison"]["delta_percent"] < 0

    def test_delta_sign_when_higher(self):
        """When our RI is higher than Polar's, delta should be positive."""
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--polar-ri",
            "1",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["comparison"]["delta"] > 0
        assert data["comparison"]["delta_percent"] > 0


class TestE2eTreadmill15km:
    """End-to-end tests for the treadmill 15 km fixture."""

    def test_15km_text(self):
        result = run_cli(str(FIXTURE_15KM), "--hr-max", "185", "--hr-rest", "48")
        assert result.returncode == 0
        assert "Running Index Report" in result.stdout
        assert "Treadmill" in result.stdout

    def test_15km_json_structure(self):
        result = run_cli(
            str(FIXTURE_15KM),
            "--hr-max",
            "185",
            "--hr-rest",
            "48",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["parameters"]["hr_max"] == 185
        assert data["parameters"]["hr_rest"] == 48
        assert data["activity"]["distance_meters"] > 14000

    def test_15km_ri_in_plausible_range(self):
        result = run_cli(
            str(FIXTURE_15KM),
            "--hr-max",
            "185",
            "--hr-rest",
            "48",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        ri = data["running_index"]
        assert 25 < ri < 85, f"RI {ri} is outside plausible range"


class TestE2eHalfMarathon:
    """End-to-end tests for the outdoor half marathon fixture."""

    def test_half_marathon_text(self):
        result = run_cli(
            str(FIXTURE_HALF_MARATHON), "--hr-max", "190", "--hr-rest", "55"
        )
        assert result.returncode == 0
        assert "Running Index Report" in result.stdout
        assert "21.51" in result.stdout  # distance in km

    def test_half_marathon_json_structure(self):
        result = run_cli(
            str(FIXTURE_HALF_MARATHON),
            "--hr-max",
            "190",
            "--hr-rest",
            "55",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["activity"]["sport"] == "running"
        assert data["activity"]["sub_sport"] == "generic"
        assert data["activity"]["distance_meters"] > 21000
        assert data["activity"]["duration_seconds"] > 8000

    def test_half_marathon_ri_in_plausible_range(self):
        result = run_cli(
            str(FIXTURE_HALF_MARATHON),
            "--hr-max",
            "190",
            "--hr-rest",
            "55",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        ri = data["running_index"]
        assert 25 < ri < 85, f"RI {ri} is outside plausible range"


class TestE2eMarathon:
    """End-to-end tests for the outdoor marathon fixture."""

    def test_marathon_text(self):
        result = run_cli(str(FIXTURE_MARATHON), "--hr-max", "190", "--hr-rest", "55")
        assert result.returncode == 0
        assert "Running Index Report" in result.stdout
        assert "Running" in result.stdout
        assert "43.11" in result.stdout  # distance in km

    def test_marathon_json_structure(self):
        result = run_cli(
            str(FIXTURE_MARATHON),
            "--hr-max",
            "190",
            "--hr-rest",
            "55",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["activity"]["sport"] == "running"
        assert data["activity"]["sub_sport"] == "generic"
        assert data["activity"]["distance_meters"] > 43000
        assert data["activity"]["duration_seconds"] > 16000

    def test_marathon_ri_in_plausible_range(self):
        result = run_cli(
            str(FIXTURE_MARATHON),
            "--hr-max",
            "190",
            "--hr-rest",
            "55",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        ri = data["running_index"]
        assert 25 < ri < 85, f"RI {ri} is outside plausible range"

    def test_marathon_with_polar_ri(self):
        """Compare calculated RI against official Polar RI of 52."""
        result = run_cli(
            str(FIXTURE_MARATHON),
            "--hr-max",
            "190",
            "--hr-rest",
            "55",
            "--polar-ri",
            "52",
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "comparison" in data
        assert data["comparison"]["polar_ri"] == 52.0
        # Our algorithm underestimates — delta should be negative
        assert data["comparison"]["delta"] < 0


class TestE2eErrorHandling:
    """Test error cases via the subprocess interface."""

    def test_missing_file(self):
        result = run_cli(
            "/nonexistent/file.fit",
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
        )
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_missing_required_args(self):
        result = run_cli(str(FIXTURE_12KM))
        assert result.returncode != 0

    def test_invalid_method(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "190",
            "--hr-rest",
            "50",
            "--method",
            "invalid",
        )
        assert result.returncode != 0

    def test_hr_rest_greater_than_max(self):
        result = run_cli(
            str(FIXTURE_12KM),
            "--hr-max",
            "50",
            "--hr-rest",
            "100",
        )
        assert result.returncode == 1
        assert "Error" in result.stderr
