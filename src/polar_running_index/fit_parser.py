"""Parse FIT files and extract running activity data."""

from datetime import datetime
from pathlib import Path

import fitparse  # type: ignore[import-untyped,unused-ignore]

from polar_running_index.models import ActivityData, ActivityRecord


class FitParseError(Exception):
    """Raised when a FIT file cannot be parsed or validated."""


# Minimum requirements per the Polar Running Index white paper
MIN_SPEED_MS = 1.667  # 6 km/h in m/s
MIN_DURATION_S = 720  # 12 minutes in seconds


def parse_fit_file(path: str | Path) -> ActivityData:
    """Parse a FIT file and return structured activity data.

    Args:
        path: Path to the FIT file.

    Returns:
        ActivityData with all records and session metadata.

    Raises:
        FitParseError: If the file cannot be parsed or is not a running activity.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"FIT file not found: {path}")

    fitfile = fitparse.FitFile(str(path))

    # Extract session metadata
    sport, sub_sport, start_time, total_duration, total_distance = _parse_session(
        fitfile
    )

    # Validate sport
    if sport != "running":
        raise FitParseError(
            f"Activity sport is '{sport}', not 'running'. "
            "Running Index is only available for running activities."
        )

    # Extract records
    records = _parse_records(fitfile, start_time)

    if not records:
        raise FitParseError("No data records found in FIT file.")

    # Validate minimum duration
    actual_duration = records[-1].elapsed_seconds - records[0].elapsed_seconds
    if actual_duration < MIN_DURATION_S:
        raise FitParseError(
            f"Activity duration is {actual_duration:.0f}s, "
            f"minimum required is {MIN_DURATION_S}s (12 minutes)."
        )

    return ActivityData(
        records=records,
        sport=sport,
        sub_sport=sub_sport,
        start_time=start_time,
        total_duration=total_duration,
        total_distance=total_distance,
    )


def _parse_session(
    fitfile: fitparse.FitFile,
) -> tuple[str, str, datetime, float, float]:
    """Extract session-level metadata from the FIT file."""
    session = None
    for msg in fitfile.get_messages("session"):
        session = msg
        break

    if session is None:
        raise FitParseError("No session record found in FIT file.")

    fields = {f.name: f.value for f in session.fields}

    sport = fields.get("sport", "unknown")
    sub_sport = fields.get("sub_sport", "generic")
    start_time = fields.get("start_time")
    total_duration = fields.get("total_timer_time", 0.0)
    total_distance = fields.get("total_distance", 0.0)

    if start_time is None:
        raise FitParseError("Session has no start_time.")

    return sport, sub_sport, start_time, total_duration, total_distance


def _parse_records(
    fitfile: fitparse.FitFile, start_time: datetime
) -> list[ActivityRecord]:
    """Extract per-second data records from the FIT file."""
    records: list[ActivityRecord] = []

    for msg in fitfile.get_messages("record"):
        fields = {f.name: f.value for f in msg.fields}

        timestamp = fields.get("timestamp")
        heart_rate = fields.get("heart_rate")
        speed = fields.get("enhanced_speed") or fields.get("speed")
        distance = fields.get("distance")

        # Skip records with missing essential data
        if timestamp is None or heart_rate is None or speed is None:
            continue

        # Skip records with zero/invalid HR
        if heart_rate <= 0:
            continue

        elapsed = (timestamp - start_time).total_seconds()

        record = ActivityRecord(
            timestamp=timestamp,
            heart_rate=int(heart_rate),
            speed=float(speed),
            distance=float(distance) if distance is not None else 0.0,
            elapsed_seconds=elapsed,
            cadence=int(fields["cadence"])
            if fields.get("cadence") is not None
            else None,
            altitude=(
                float(fields["enhanced_altitude"])
                if fields.get("enhanced_altitude") is not None
                else (
                    float(fields["altitude"])
                    if fields.get("altitude") is not None
                    else None
                )
            ),
        )
        records.append(record)

    return records
