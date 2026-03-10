"""Integration tests for the CLI."""

import json
from pathlib import Path

from polar_running_index.cli import main

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_FIT = FIXTURES_DIR / "treadmill_12km.FIT"


class TestCli:
    def test_text_output(self, capsys):
        """CLI should produce text output by default."""
        exit_code = main([str(SAMPLE_FIT), "--hr-max", "190", "--hr-rest", "50"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Running Index" in captured.out
        assert "Running" in captured.out

    def test_json_output(self, capsys):
        """CLI with --json should produce valid JSON."""
        exit_code = main(
            [str(SAMPLE_FIT), "--hr-max", "190", "--hr-rest", "50", "--json"]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "running_index" in data
        assert isinstance(data["running_index"], (int, float))
        assert data["running_index"] > 0
        assert "method" in data
        assert "statistics" in data

    def test_hrmax_ratio_method(self, capsys):
        """CLI with --method hrmax_ratio should work."""
        exit_code = main(
            [
                str(SAMPLE_FIT),
                "--hr-max",
                "190",
                "--hr-rest",
                "50",
                "--method",
                "hrmax_ratio",
                "--json",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["method"] == "hrmax_ratio"

    def test_no_drift_correction(self, capsys):
        """CLI with --no-drift-correction should work."""
        exit_code = main(
            [
                str(SAMPLE_FIT),
                "--hr-max",
                "190",
                "--hr-rest",
                "50",
                "--no-drift-correction",
                "--json",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["drift_corrected"] is False

    def test_polar_ri_text(self, capsys):
        """CLI with --polar-ri should show comparison in text output."""
        exit_code = main(
            [str(SAMPLE_FIT), "--hr-max", "190", "--hr-rest", "50", "--polar-ri", "50"]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Comparison with Polar" in captured.out
        assert "Polar RI:" in captured.out
        assert "Difference:" in captured.out

    def test_polar_ri_json(self, capsys):
        """CLI with --polar-ri should include comparison in JSON."""
        exit_code = main(
            [
                str(SAMPLE_FIT),
                "--hr-max",
                "190",
                "--hr-rest",
                "50",
                "--polar-ri",
                "50",
                "--json",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "comparison" in data
        assert data["comparison"]["polar_ri"] == 50.0
        assert "delta" in data["comparison"]
        assert "delta_percent" in data["comparison"]

    def test_no_polar_ri_no_comparison(self, capsys):
        """Without --polar-ri, no comparison section should appear."""
        exit_code = main(
            [str(SAMPLE_FIT), "--hr-max", "190", "--hr-rest", "50", "--json"]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "comparison" not in data

    def test_segments_text(self, capsys):
        """CLI with --segments should show segment breakdown in text."""
        exit_code = main(
            [str(SAMPLE_FIT), "--hr-max", "190", "--hr-rest", "50", "--segments"]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Segments:" in captured.out
        assert "Km 1" in captured.out

    def test_segments_json(self, capsys):
        """CLI with --segments --json should include segments array."""
        exit_code = main(
            [
                str(SAMPLE_FIT),
                "--hr-max",
                "190",
                "--hr-rest",
                "50",
                "--segments",
                "--json",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "segments" in data
        assert isinstance(data["segments"], list)
        assert len(data["segments"]) > 0
        seg = data["segments"][0]
        assert "label" in seg
        assert "running_index" in seg
        assert "pace_min_per_km" in seg

    def test_no_segments_without_flag(self, capsys):
        """Without --segments, no segments section should appear."""
        exit_code = main(
            [str(SAMPLE_FIT), "--hr-max", "190", "--hr-rest", "50", "--json"]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "segments" not in data

    def test_file_not_found(self, capsys):
        """CLI should return 1 for missing file."""
        exit_code = main(["/nonexistent.fit", "--hr-max", "190", "--hr-rest", "50"])
        assert exit_code == 1
