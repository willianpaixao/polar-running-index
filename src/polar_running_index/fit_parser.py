"""Parse FIT files and extract running activity data."""

from datetime import datetime
from pathlib import Path

import fitdecode  # type: ignore[import-untyped,unused-ignore]

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

    sport: str | None = None
    sub_sport: str | None = None
    start_time: datetime | None = None
    total_duration: float = 0.0
    total_distance: float = 0.0
    raw_records: list[tuple[datetime, int, float, float, int | None, float | None]] = []

    with fitdecode.FitReader(str(path)) as fit:
        for frame in fit:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue

            if frame.name == "session" and sport is None:
                sport, sub_sport, start_time, total_duration, total_distance = (
                    _extract_session(frame)
                )

            elif frame.name == "record":
                parsed = _extract_record(frame)
                if parsed is not None:
                    raw_records.append(parsed)

    # Validate session was found
    if sport is None or start_time is None:
        raise FitParseError("No session record found in FIT file.")

    # Validate sport
    if sport != "running":
        raise FitParseError(
            f"Activity sport is '{sport}', not 'running'. "
            "Running Index is only available for running activities."
        )

    # Build ActivityRecord objects now that we have start_time
    records = _build_records(raw_records, start_time)

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
        sub_sport=sub_sport or "generic",
        start_time=start_time,
        total_duration=total_duration,
        total_distance=total_distance,
    )


def _extract_session(
    frame: fitdecode.FitDataMessage,
) -> tuple[str, str, datetime | None, float, float]:
    """Extract session-level metadata from a session frame."""
    sport = frame.get_value("sport", fallback="unknown")
    sub_sport = frame.get_value("sub_sport", fallback="generic")
    start_time = frame.get_value("start_time", fallback=None)
    total_duration = frame.get_value("total_timer_time", fallback=0.0)
    total_distance = frame.get_value("total_distance", fallback=0.0)

    return sport, sub_sport, start_time, total_duration, total_distance


def _extract_record(
    frame: fitdecode.FitDataMessage,
) -> tuple[datetime, int, float, float, int | None, float | None] | None:
    """Extract a single data record from a record frame.

    Returns a tuple of (timestamp, hr, speed, distance, cadence, altitude)
    or None if essential fields are missing.
    """
    timestamp = frame.get_value("timestamp", fallback=None)
    heart_rate = frame.get_value("heart_rate", fallback=None)
    speed = frame.get_value("enhanced_speed", fallback=None) or frame.get_value(
        "speed", fallback=None
    )

    if timestamp is None or heart_rate is None or speed is None:
        return None

    if heart_rate <= 0:
        return None

    distance = frame.get_value("distance", fallback=0.0)
    cadence = frame.get_value("cadence", fallback=None)
    altitude = frame.get_value("enhanced_altitude", fallback=None) or frame.get_value(
        "altitude", fallback=None
    )

    return (
        timestamp,
        int(heart_rate),
        float(speed),
        float(distance),
        int(cadence) if cadence is not None else None,
        float(altitude) if altitude is not None else None,
    )


def _build_records(
    raw_records: list[tuple[datetime, int, float, float, int | None, float | None]],
    start_time: datetime,
) -> list[ActivityRecord]:
    """Convert raw extracted tuples into ActivityRecord objects."""
    return [
        ActivityRecord(
            timestamp=ts,
            heart_rate=hr,
            speed=spd,
            distance=dist,
            elapsed_seconds=(ts - start_time).total_seconds(),
            cadence=cad,
            altitude=alt,
        )
        for ts, hr, spd, dist, cad, alt in raw_records
    ]
