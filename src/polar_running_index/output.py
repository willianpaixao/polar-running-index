"""Output formatting for Running Index results."""

import json
from typing import Any

from polar_running_index.models import (
    ActivityData,
    ComparisonResult,
    RunningIndexResult,
    SegmentResult,
)

# Performance level classification based on VO2max (ml/kg/min)
# From Shvartz & Reibold (1990) — the reference used by Polar
# Simplified categories for general use
_PERFORMANCE_LEVELS = [
    (28, "Very Low"),
    (34, "Low"),
    (40, "Fair"),
    (47, "Average"),
    (54, "Good"),
    (61, "Very Good"),
    (68, "Excellent"),
    (float("inf"), "Elite"),
]


def get_performance_level(running_index: float) -> str:
    """Classify performance level based on Running Index value."""
    for threshold, label in _PERFORMANCE_LEVELS:
        if running_index < threshold:
            return label
    return "Elite"


def format_text_report(
    activity: ActivityData,
    result: RunningIndexResult,
    hr_max: int,
    hr_rest: int,
    comparison: ComparisonResult | None = None,
    segments: list[SegmentResult] | None = None,
) -> str:
    """Format a human-readable text report.

    Args:
        activity: Parsed activity data.
        result: Running Index calculation result.
        hr_max: User's maximum heart rate.
        hr_rest: User's resting heart rate.
        comparison: Optional comparison with official Polar RI.
        segments: Optional per-segment Running Index breakdown.

    Returns:
        Formatted multi-line string.
    """
    method_label = {
        "hrr": "Heart Rate Reserve",
        "hrmax_ratio": "HRmax Ratio",
    }.get(result.method, result.method)

    if result.drift_corrected:
        method_label += " + Drift Correction"

    level = get_performance_level(result.running_index)
    stats = result.summary_stats

    lines = [
        "",
        "=" * 50,
        "  Running Index Report",
        "=" * 50,
        "",
        (
            f"  Activity:    {activity.sport.title()}"
            f" ({activity.sub_sport.replace('_', ' ').title()})"
        ),
        f"  Date:        {activity.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"  Duration:    {activity.duration_str}",
        f"  Distance:    {activity.total_distance / 1000:.2f} km",
        (
            f"  Avg Speed:   {activity.avg_speed_kmh:.1f} km/h"
            f" ({activity.pace_min_per_km} min/km)"
        ),
        f"  Avg HR:      {activity.avg_heart_rate:.0f} bpm",
        f"  Max HR:      {activity.max_heart_rate} bpm",
        "",
        f"  Parameters:  HRmax={hr_max}, HRrest={hr_rest}",
        "",
        "-" * 50,
        "",
        f"  Running Index:  {result.running_index:.1f}",
        f"  Method:         {method_label}",
        f"  Level:          {level}",
        "",
        "-" * 50,
        "",
        "  Statistics:",
        f"    Mean:      {stats.get('mean', 0):.1f}",
        f"    Median:    {stats.get('median', 0):.1f}",
        f"    Std Dev:   {stats.get('stdev', 0):.1f}",
        f"    Min:       {stats.get('min', 0):.1f}",
        f"    Max:       {stats.get('max', 0):.1f}",
        f"    Samples:   {stats.get('n_filtered', 0):.0f} used, "
        f"{stats.get('n_outliers', 0):.0f} outliers removed",
    ]

    if segments:
        lines.extend(
            [
                "",
                "-" * 50,
                "",
                "  Segments:",
            ]
        )
        for seg in segments:
            duration = seg.end_seconds - seg.start_seconds
            lines.append(
                f"    {seg.label:>6s}:  RI {seg.running_index:5.1f}"
                f"  |  {seg.pace_min_per_km} /km"
                f"  |  HR {seg.avg_heart_rate:.0f}"
                f"  |  {duration:.0f}s"
            )

    if comparison is not None:
        direction = "lower" if comparison.delta < 0 else "higher"
        lines.extend(
            [
                "",
                "-" * 50,
                "",
                "  Comparison with Polar:",
                f"    Polar RI:      {comparison.polar_ri:.1f}",
                f"    Calculated:    {comparison.calculated_ri:.1f}",
                (
                    f"    Difference:    {comparison.delta:+.1f}"
                    f" ({abs(comparison.delta_percent):.1f}% {direction})"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "=" * 50,
            "",
        ]
    )

    return "\n".join(lines)


def format_json_report(
    activity: ActivityData,
    result: RunningIndexResult,
    hr_max: int,
    hr_rest: int,
    comparison: ComparisonResult | None = None,
    segments: list[SegmentResult] | None = None,
) -> str:
    """Format a machine-readable JSON report.

    Args:
        activity: Parsed activity data.
        result: Running Index calculation result.
        hr_max: User's maximum heart rate.
        hr_rest: User's resting heart rate.
        comparison: Optional comparison with official Polar RI.
        segments: Optional per-segment Running Index breakdown.

    Returns:
        JSON string.
    """
    data: dict[str, Any] = {
        "running_index": round(result.running_index, 1),
        "method": result.method,
        "drift_corrected": result.drift_corrected,
        "performance_level": get_performance_level(result.running_index),
        "activity": {
            "sport": activity.sport,
            "sub_sport": activity.sub_sport,
            "start_time": activity.start_time.isoformat(),
            "duration_seconds": activity.total_duration,
            "distance_meters": activity.total_distance,
            "avg_speed_ms": round(activity.avg_speed, 3),
            "avg_speed_kmh": round(activity.avg_speed_kmh, 1),
            "avg_heart_rate": round(activity.avg_heart_rate),
            "max_heart_rate": activity.max_heart_rate,
        },
        "parameters": {
            "hr_max": hr_max,
            "hr_rest": hr_rest,
        },
        "statistics": {
            k: round(v, 2) if isinstance(v, float) else v
            for k, v in result.summary_stats.items()
        },
        "valid_window": {
            "start_seconds": result.valid_window_start,
            "end_seconds": result.valid_window_end,
        },
    }

    if segments:
        data["segments"] = [
            {
                "label": seg.label,
                "start_seconds": round(seg.start_seconds, 1),
                "end_seconds": round(seg.end_seconds, 1),
                "distance_meters": round(seg.distance_meters, 1),
                "avg_heart_rate": round(seg.avg_heart_rate),
                "max_heart_rate": seg.max_heart_rate,
                "avg_speed_kmh": round(seg.avg_speed_ms * 3.6, 1),
                "pace_min_per_km": seg.pace_min_per_km,
                "running_index": round(seg.running_index, 1),
                "n_samples": seg.n_samples,
            }
            for seg in segments
        ]

    if comparison is not None:
        data["comparison"] = {
            "polar_ri": comparison.polar_ri,
            "calculated_ri": round(comparison.calculated_ri, 1),
            "delta": round(comparison.delta, 1),
            "delta_percent": round(comparison.delta_percent, 1),
        }

    return json.dumps(data, indent=2)
