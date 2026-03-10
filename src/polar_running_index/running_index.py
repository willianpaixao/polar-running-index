"""Core Running Index (VO2max estimation) algorithm.

Implements three calculation methods based on patents US2007082789 / EP1795128:

- Formula 3: HRmax ratio method (simpler)
- Formula 4: Heart Rate Reserve method (Karvonen, more accurate)
- Formula 5: Exertion history correction (cardiac drift compensation)

References:
    - Polar Running Index White Paper (April 2021)
    - Patent US2007082789 / EP1795128
    - ACSM metabolic equations for running
    - Swain & Leutholtz (1997) — %HRR ~ %VO2R
"""

import statistics

from polar_running_index.models import (
    ActivityData,
    ActivityRecord,
    RunningIndexResult,
    SegmentResult,
)

# Constants from patent and ACSM guidelines
VO2_REST = 3.5  # ml/kg/min (1 MET, resting metabolic rate)
PATENT_RUNNING_COEFF = 3.2  # Patent's VO2-speed coefficient for running
ACSM_HORIZONTAL_COEFF = 0.2  # ml/kg per meter (ACSM horizontal O2 cost)
ACSM_VERTICAL_COEFF = 0.9  # ml/kg per meter of vertical (ACSM grade O2 cost)

# Valid time window per patent (seconds)
VALID_WINDOW_START = 180.0  # 3 minutes — HR not stabilized before this
VALID_WINDOW_END = 3600.0  # 60 minutes — cardiac drift too large after this

# Drift correction reference point per patent (seconds)
DRIFT_REFERENCE_TIME = 720.0  # 12 minutes

# Minimum speed for RI calculation (m/s) — 6 km/h per white paper
MIN_SPEED_MS = 1.667


def calculate_running_index(
    activity: ActivityData,
    hr_max: int,
    hr_rest: int,
    method: str = "hrr",
    drift_correction: bool = True,
) -> RunningIndexResult:
    """Calculate Running Index from activity data.

    Args:
        activity: Parsed activity data from a FIT file.
        hr_max: User's maximum heart rate (bpm).
        hr_rest: User's resting heart rate (bpm).
        method: Algorithm variant — "hrr" (Heart Rate Reserve) or "hrmax_ratio".
        drift_correction: Whether to apply cardiac drift correction (Formula 5).

    Returns:
        RunningIndexResult with the computed Running Index and statistics.

    Raises:
        ValueError: If parameters are invalid.
    """
    _validate_params(hr_max, hr_rest, method)

    # Filter records to valid time window and minimum speed
    valid_records = _filter_valid_records(activity.records)

    if not valid_records:
        raise ValueError(
            "No valid records in the 3-60 minute window with speed > 6 km/h. "
            "Cannot compute Running Index."
        )

    window_start = valid_records[0].elapsed_seconds
    window_end = valid_records[-1].elapsed_seconds

    # Apply drift correction if requested
    if drift_correction:
        hr_corrections = _compute_drift_corrections(valid_records)
    else:
        hr_corrections = [0.0] * len(valid_records)

    # Compute per-sample RI estimates
    per_sample = []
    for record, hr_corr in zip(valid_records, hr_corrections, strict=False):
        corrected_hr = record.heart_rate - hr_corr

        # Clamp corrected HR to valid range
        corrected_hr = max(corrected_hr, hr_rest + 1)
        corrected_hr = min(corrected_hr, hr_max)

        if method == "hrr":
            ri = _formula_hrr(record.speed, corrected_hr, hr_max, hr_rest)
        else:
            ri = _formula_hrmax_ratio(record.speed, corrected_hr, hr_max)

        per_sample.append(ri)

    # Remove outliers and compute final RI
    filtered = _remove_outliers(per_sample)

    if not filtered:
        # Fall back to all samples if outlier removal is too aggressive
        filtered = per_sample

    running_index = statistics.mean(filtered)

    # Summary statistics
    summary = {
        "mean": statistics.mean(filtered),
        "median": statistics.median(filtered),
        "stdev": statistics.stdev(filtered) if len(filtered) > 1 else 0.0,
        "min": min(filtered),
        "max": max(filtered),
        "n_total": len(per_sample),
        "n_filtered": len(filtered),
        "n_outliers": len(per_sample) - len(filtered),
    }

    return RunningIndexResult(
        running_index=running_index,
        method=method,
        drift_corrected=drift_correction,
        per_sample_estimates=per_sample,
        filtered_estimates=filtered,
        valid_window_start=window_start,
        valid_window_end=window_end,
        summary_stats=summary,
    )


def calculate_segment_running_index(
    activity: ActivityData,
    hr_max: int,
    hr_rest: int,
    method: str = "hrr",
    drift_correction: bool = True,
) -> list[SegmentResult]:
    """Calculate Running Index for each segment of an activity.

    Uses lap boundaries from the FIT file if more than one lap is present.
    Otherwise, falls back to per-kilometer splits based on cumulative distance.

    Args:
        activity: Parsed activity data from a FIT file.
        hr_max: User's maximum heart rate (bpm).
        hr_rest: User's resting heart rate (bpm).
        method: Algorithm variant — "hrr" or "hrmax_ratio".
        drift_correction: Whether to apply cardiac drift correction.

    Returns:
        List of SegmentResult, one per segment.
    """
    _validate_params(hr_max, hr_rest, method)

    valid_records = _filter_valid_records(activity.records)
    if not valid_records:
        return []

    # Compute activity-wide drift correction
    if drift_correction:
        all_hr_corrections = _compute_drift_corrections(valid_records)
        # Build a lookup: elapsed_seconds -> correction
        drift_by_time = dict(
            zip(
                [r.elapsed_seconds for r in valid_records],
                all_hr_corrections,
                strict=False,
            )
        )
    else:
        drift_by_time = {}

    # Choose segmentation strategy
    if len(activity.laps) > 1:
        boundaries = [
            (f"Lap {i + 1}", lap.start_elapsed, lap.end_elapsed)
            for i, lap in enumerate(activity.laps)
        ]
    else:
        boundaries = _build_km_boundaries(activity.records)

    # Compute RI per segment
    results: list[SegmentResult] = []
    for label, seg_start, seg_end in boundaries:
        seg_records = [
            r for r in valid_records if seg_start <= r.elapsed_seconds < seg_end
        ]

        if len(seg_records) < 10:
            continue

        # Compute per-sample RI for this segment
        per_sample: list[float] = []
        for record in seg_records:
            hr_corr = drift_by_time.get(record.elapsed_seconds, 0.0)
            corrected_hr = record.heart_rate - hr_corr
            corrected_hr = max(corrected_hr, hr_rest + 1)
            corrected_hr = min(corrected_hr, hr_max)

            if method == "hrr":
                ri = _formula_hrr(record.speed, corrected_hr, hr_max, hr_rest)
            else:
                ri = _formula_hrmax_ratio(record.speed, corrected_hr, hr_max)

            per_sample.append(ri)

        filtered = _remove_outliers(per_sample)
        if not filtered:
            filtered = per_sample

        # Compute segment metrics
        hrs = [r.heart_rate for r in seg_records]
        speeds = [r.speed for r in seg_records]

        # Distance covered in this segment
        seg_dist_start = seg_records[0].distance
        seg_dist_end = seg_records[-1].distance
        seg_distance = seg_dist_end - seg_dist_start

        results.append(
            SegmentResult(
                label=label,
                start_seconds=seg_records[0].elapsed_seconds,
                end_seconds=seg_records[-1].elapsed_seconds,
                distance_meters=seg_distance,
                avg_heart_rate=sum(hrs) / len(hrs),
                max_heart_rate=max(hrs),
                avg_speed_ms=sum(speeds) / len(speeds),
                running_index=statistics.mean(filtered),
                n_samples=len(filtered),
            )
        )

    return results


def _build_km_boundaries(
    records: list[ActivityRecord],
) -> list[tuple[str, float, float]]:
    """Build per-kilometer segment boundaries from record distance data.

    Returns a list of (label, start_elapsed, end_elapsed) tuples.
    """
    if not records:
        return []

    boundaries: list[tuple[str, float, float]] = []
    km_num = 1
    seg_start = records[0].elapsed_seconds

    for record in records:
        if record.distance >= km_num * 1000.0:
            boundaries.append((f"Km {km_num}", seg_start, record.elapsed_seconds))
            seg_start = record.elapsed_seconds
            km_num += 1

    # Final partial segment (less than 1 km)
    if seg_start < records[-1].elapsed_seconds:
        boundaries.append((f"Km {km_num}", seg_start, records[-1].elapsed_seconds + 1))

    return boundaries


def vo2_demand_acsm(speed_ms: float, grade: float = 0.0) -> float:
    """Calculate oxygen demand using the ACSM running metabolic equation.

    Args:
        speed_ms: Running speed in m/s.
        grade: Fractional grade (0.0 = flat, 0.05 = 5% incline).

    Returns:
        VO2 in ml/kg/min.
    """
    speed_m_min = speed_ms * 60.0
    return (
        ACSM_HORIZONTAL_COEFF * speed_m_min
        + ACSM_VERTICAL_COEFF * speed_m_min * grade
        + VO2_REST
    )


def vo2_demand_patent(speed_ms: float) -> float:
    """Calculate oxygen demand using the patent coefficient.

    The patent uses VO2 = 3.2 * v where v appears to be in km/h.

    Args:
        speed_ms: Running speed in m/s.

    Returns:
        VO2 demand (net, excluding resting) in ml/kg/min.
    """
    speed_kmh = speed_ms * 3.6
    return PATENT_RUNNING_COEFF * speed_kmh


def _formula_hrmax_ratio(speed_ms: float, hr: float, hr_max: int) -> float:
    """Formula 3 from patent: HRmax ratio method.

    F = (HRmax / HR) * VO2_demand + D

    Args:
        speed_ms: Running speed in m/s.
        hr: Current heart rate (bpm), possibly drift-corrected.
        hr_max: Maximum heart rate (bpm).

    Returns:
        Estimated VO2max (Running Index) in ml/kg/min.
    """
    vo2_net = vo2_demand_patent(speed_ms)
    return (hr_max / hr) * vo2_net + VO2_REST


def _formula_hrr(speed_ms: float, hr: float, hr_max: int, hr_rest: int) -> float:
    """Formula 4 from patent: Heart Rate Reserve (Karvonen) method.

    F = ((HRmax - HRrest) / (HR - HRrest)) * VO2_demand + D

    This uses the relationship %HRR ~ %VO2R (Swain & Leutholtz, 1997).

    Args:
        speed_ms: Running speed in m/s.
        hr: Current heart rate (bpm), possibly drift-corrected.
        hr_max: Maximum heart rate (bpm).
        hr_rest: Resting heart rate (bpm).

    Returns:
        Estimated VO2max (Running Index) in ml/kg/min.
    """
    vo2_net = vo2_demand_patent(speed_ms)
    hrr_ratio = (hr_max - hr_rest) / (hr - hr_rest)
    return hrr_ratio * vo2_net + VO2_REST


def _filter_valid_records(records: list[ActivityRecord]) -> list[ActivityRecord]:
    """Filter records to the valid time window and minimum speed.

    Per the patent:
    - Only use data between 3 and 60 minutes
    - Speed must exceed 6 km/h (1.667 m/s)
    """
    return [
        r
        for r in records
        if VALID_WINDOW_START <= r.elapsed_seconds <= VALID_WINDOW_END
        and r.speed >= MIN_SPEED_MS
        and r.heart_rate > 0
    ]


def _compute_drift_corrections(records: list[ActivityRecord]) -> list[float]:
    """Estimate cardiac drift and compute per-record HR corrections.

    Since we don't have the patent's proprietary exertion curves, we estimate
    drift from the data itself:

    1. Identify segments of relatively constant speed
    2. Fit a linear trend of HR vs. elapsed time in those segments
    3. Correct each HR to the reference time point (12 min per patent)

    The correction for each record is:
        HR_correction = drift_rate * (elapsed_seconds - DRIFT_REFERENCE_TIME)

    where drift_rate is the estimated bpm/second increase due to cardiac drift.
    """
    if len(records) < 10:
        return [0.0] * len(records)

    # Use the median speed as the "target" speed
    speeds = [r.speed for r in records]
    median_speed = statistics.median(speeds)

    # Select records within 5% of median speed (relatively constant pace)
    speed_tolerance = median_speed * 0.05
    steady_records = [
        r for r in records if abs(r.speed - median_speed) <= speed_tolerance
    ]

    if len(steady_records) < 20:
        # Not enough steady-state data — skip drift correction
        return [0.0] * len(records)

    # Fit linear regression: HR = a * elapsed_seconds + b
    drift_rate = _linear_regression_slope(
        x=[r.elapsed_seconds for r in steady_records],
        y=[float(r.heart_rate) for r in steady_records],
    )

    # Only correct if drift is positive (HR increasing over time, as expected)
    # and not unreasonably large (> 0.1 bpm/s = 6 bpm/min would be extreme)
    if drift_rate <= 0.0 or drift_rate > 0.1:
        return [0.0] * len(records)

    # Compute corrections: shift each HR to what it would be at t=12 min
    corrections = [
        drift_rate * (r.elapsed_seconds - DRIFT_REFERENCE_TIME) for r in records
    ]

    return corrections


def _linear_regression_slope(x: list[float], y: list[float]) -> float:
    """Compute the slope of a simple linear regression y = a*x + b.

    Returns the slope 'a'.
    """
    n = len(x)
    if n < 2:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y, strict=False))
    denominator = sum((xi - mean_x) ** 2 for xi in x)

    if denominator == 0.0:
        return 0.0

    return numerator / denominator


def _remove_outliers(values: list[float]) -> list[float]:
    """Remove statistical outliers using the IQR method.

    Values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR] are removed.
    """
    if len(values) < 4:
        return values

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[3 * n // 4]
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    return [v for v in values if lower <= v <= upper]


def predict_race_times(running_index: float) -> list[tuple[str, float, float]]:
    """Predict race times from Running Index (VO2max estimate).

    Uses the relationship between VO2max and sustainable running speed,
    combined with the Riegel formula for distance scaling.

    The approach:
    1. Estimate the speed sustainable at ~75% VO2max for a 10K reference
    2. Scale to other distances using Riegel's formula: T2 = T1 * (D2/D1)^1.06

    Args:
        running_index: VO2max estimate in ml/kg/min.

    Returns:
        List of (distance_name, distance_meters, predicted_seconds) tuples.
    """
    # At race effort, runners typically sustain ~75-85% VO2max depending on distance
    # Using the ACSM equation in reverse: speed = (VO2 - 3.5) / (0.2 * 60)
    # For 10K effort (~80% VO2max):
    vo2_at_race = running_index * 0.80
    speed_m_min = (vo2_at_race - VO2_REST) / ACSM_HORIZONTAL_COEFF
    speed_ms = speed_m_min / 60.0

    if speed_ms <= 0:
        return []

    # Reference: 10K time
    ref_distance = 10000.0
    ref_time = ref_distance / speed_ms

    # Riegel formula: T2 = T1 * (D2/D1)^1.06
    distances = [
        ("5K", 5000.0),
        ("10K", 10000.0),
        ("Half Marathon", 21097.5),
        ("Marathon", 42195.0),
    ]

    predictions = []
    for name, dist in distances:
        time = ref_time * (dist / ref_distance) ** 1.06
        predictions.append((name, dist, time))

    return predictions


def _validate_params(hr_max: int, hr_rest: int, method: str) -> None:
    """Validate input parameters."""
    if hr_max <= 0:
        raise ValueError(f"hr_max must be positive, got {hr_max}")
    if hr_rest <= 0:
        raise ValueError(f"hr_rest must be positive, got {hr_rest}")
    if hr_rest >= hr_max:
        raise ValueError(f"hr_rest ({hr_rest}) must be less than hr_max ({hr_max})")
    if method not in ("hrr", "hrmax_ratio"):
        raise ValueError(f"method must be 'hrr' or 'hrmax_ratio', got '{method}'")
