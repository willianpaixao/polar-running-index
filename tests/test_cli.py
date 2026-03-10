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

    def test_file_not_found(self, capsys):
        """CLI should return 1 for missing file."""
        exit_code = main(["/nonexistent.fit", "--hr-max", "190", "--hr-rest", "50"])
        assert exit_code == 1
