"""Data classes for activity records and Running Index results."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ActivityRecord:
    """A single per-second measurement from a running activity."""

    timestamp: datetime
    heart_rate: int  # bpm
    speed: float  # m/s
    distance: float  # cumulative meters
    elapsed_seconds: float  # seconds since activity start
    cadence: int | None = None  # strides/min
    altitude: float | None = None  # meters


@dataclass
class ActivityData:
    """Parsed activity data from a FIT file."""

    records: list[ActivityRecord]
    sport: str
    sub_sport: str
    start_time: datetime
    total_duration: float  # seconds (timer time)
    total_distance: float  # meters

    @property
    def avg_heart_rate(self) -> float:
        hr_values = [r.heart_rate for r in self.records if r.heart_rate > 0]
        return sum(hr_values) / len(hr_values) if hr_values else 0.0

    @property
    def max_heart_rate(self) -> int:
        hr_values = [r.heart_rate for r in self.records if r.heart_rate > 0]
        return max(hr_values) if hr_values else 0

    @property
    def avg_speed(self) -> float:
        """Average speed in m/s."""
        spd_values = [r.speed for r in self.records if r.speed > 0]
        return sum(spd_values) / len(spd_values) if spd_values else 0.0

    @property
    def avg_speed_kmh(self) -> float:
        return self.avg_speed * 3.6

    @property
    def pace_min_per_km(self) -> str:
        """Average pace as 'M:SS' string."""
        avg = self.avg_speed
        if avg <= 0:
            return "--:--"
        secs_per_km = 1000.0 / avg
        mins = int(secs_per_km // 60)
        secs = int(secs_per_km % 60)
        return f"{mins}:{secs:02d}"

    @property
    def duration_str(self) -> str:
        """Duration as 'Xh Ym Zs' or 'Ym Zs' string."""
        total = int(self.total_duration)
        hours = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        if hours > 0:
            return f"{hours}h {mins}m {secs}s"
        return f"{mins}m {secs}s"


@dataclass
class RunningIndexResult:
    """Result of a Running Index calculation."""

    running_index: float  # Final RI (VO2max estimate, ml/kg/min)
    method: str  # "hrr" or "hrmax_ratio"
    drift_corrected: bool
    per_sample_estimates: list[float]  # Raw per-second RI values
    filtered_estimates: list[float]  # After outlier removal
    valid_window_start: float  # seconds
    valid_window_end: float  # seconds
    summary_stats: dict[str, float] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Comparison between calculated and official Polar Running Index."""

    polar_ri: float  # Official value from Polar Flow
    calculated_ri: float  # Our computed value
    delta: float  # calculated - polar
    delta_percent: float  # (delta / polar) * 100


@dataclass
class RaceTimePrediction:
    """Predicted race time for a given distance."""

    distance_name: str  # e.g. "5K", "10K", "Half Marathon", "Marathon"
    distance_meters: float
    predicted_seconds: float

    @property
    def predicted_time_str(self) -> str:
        """Format as H:MM:SS or M:SS."""
        total = int(self.predicted_seconds)
        hours = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"
