# Polar Running Index

Calculate [Polar Running Index](https://www.polar.com/en/smart-coaching/running-index) (VO2max estimate) from FIT files.

Running Index estimates your maximal oxygen uptake (VO2max) from heart rate and
speed data recorded during a run. It is based on the algorithms described in
Polar's patents [US2007082789](https://patents.google.com/patent/US20070082789A1/en)
/ [EP1795128](https://patents.google.com/patent/EP1795128B1/en) and the
[ACSM metabolic equations](https://www.acsm.org/) for running.

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone https://github.com/willianpaixao/polar-running-index.git
cd polar-running-index
uv sync
```

## Usage

```bash
uv run polar-running-index <FIT_FILE> --hr-max <MAX_HR> --hr-rest <REST_HR>
```

You must provide your **maximum heart rate** (`--hr-max`) and **resting heart
rate** (`--hr-rest`) in bpm. These are needed to compute the heart rate reserve
used in the VO2max estimation.

### Example

```
$ uv run polar-running-index activity.FIT --hr-max 190 --hr-rest 50

==================================================
  Running Index Report
==================================================

  Activity:    Running (Treadmill)
  Date:        2026-03-04 18:07:54 UTC
  Duration:    1h 4m 21s
  Distance:    12.02 km
  Avg Speed:   11.2 km/h (5:20 min/km)
  Avg HR:      157 bpm
  Max HR:      167 bpm

  Parameters:  HRmax=190, HRrest=50

--------------------------------------------------

  Running Index:  52.6
  Method:         Heart Rate Reserve + Drift Correction
  Level:          Good

--------------------------------------------------

  Statistics:
    Mean:      52.6
    Median:    52.4
    Std Dev:   1.7
    Min:       48.8
    Max:       57.5
    Samples:   3393 used, 28 outliers removed

==================================================
```

### Segment analysis

Use `--segments` to see Running Index broken down per segment. If the FIT file
contains multiple laps, lap boundaries are used. Otherwise, the activity is
split into per-kilometer segments.

```
$ uv run polar-running-index activity.FIT --hr-max 190 --hr-rest 50 --segments

  ...

  Segments:
      Km 1:  RI  55.5  |  5:33 /km  |  HR 141  |  153s
      Km 2:  RI  52.6  |  5:25 /km  |  HR 150  |  324s
      Km 3:  RI  50.9  |  5:26 /km  |  HR 155  |  326s
      Km 4:  RI  51.0  |  5:23 /km  |  HR 157  |  325s
      ...
```

### Comparison with Polar Flow

Use `--polar-ri` to compare the calculated value against the official Running
Index from Polar Flow:

```
$ uv run polar-running-index activity.FIT --hr-max 190 --hr-rest 50 --polar-ri 58

  ...

  Comparison with Polar:
    Polar RI:      58.0
    Calculated:    52.6
    Difference:    -5.4 (9.3% lower)
```

### Options

| Flag | Description |
|---|---|
| `--hr-max` | Maximum heart rate in bpm (required) |
| `--hr-rest` | Resting heart rate in bpm (required) |
| `--method {hrr,hrmax_ratio}` | Algorithm variant (default: `hrr`) |
| `--no-drift-correction` | Disable cardiac drift correction |
| `--polar-ri` | Official Polar RI for comparison |
| `--segments` | Show per-segment Running Index breakdown |
| `--json` | Output results as JSON |

### Algorithm methods

- **`hrr`** (default) -- Heart Rate Reserve method (Karvonen). Uses both max and
  resting HR to estimate what fraction of aerobic capacity is being used.
  More accurate across different fitness levels.
- **`hrmax_ratio`** -- Simple HRmax ratio method. Uses only max HR. Simpler but
  less accurate for individuals with unusually high or low resting heart rates.

Both methods include cardiac drift correction by default, which compensates for
the natural rise in heart rate over time at constant effort. Disable it with
`--no-drift-correction` if you prefer raw estimates.

## How it works

1. **Parse** the FIT file to extract per-second heart rate and speed records.
2. **Filter** to the valid window (3--60 minutes into the run, speed > 6 km/h).
3. **Estimate VO2 demand** at the current speed using the ACSM running equation.
4. **Extrapolate to VO2max** using the heart rate reserve ratio.
5. **Correct for cardiac drift** by fitting a linear HR trend and normalizing
   to a 12-minute reference point.
6. **Remove outliers** (IQR method) and average the remaining estimates.

The final Running Index value is an estimate of VO2max in ml/kg/min.

## References

- [Polar Running Index White Paper](https://www.polar.com/img/static/whitepapers/pdf/polar-running-index-white-paper.pdf) (April 2021)
- Patent US2007082789 / EP1795128 -- Method for determining performance
- ACSM's Guidelines for Exercise Testing and Prescription (metabolic equations)
- Swain & Leutholtz (1997) -- %HRR approximates %VO2R
