"""Command-line interface for the Polar Running Index calculator."""

import argparse
import sys

from polar_running_index.fit_parser import FitParseError, parse_fit_file
from polar_running_index.output import format_json_report, format_text_report
from polar_running_index.running_index import calculate_running_index


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="polar-running-index",
        description=(
            "Calculate Polar Running Index (VO2max estimate) from a "
            "FIT file. Based on patents US2007082789 / EP1795128 "
            "and the ACSM metabolic equations."
        ),
    )

    parser.add_argument(
        "fit_file",
        metavar="FIT_FILE",
        help="Path to the FIT file",
    )

    required = parser.add_argument_group("required arguments")
    required.add_argument(
        "--hr-max",
        type=int,
        required=True,
        help="Maximum heart rate in bpm",
    )
    required.add_argument(
        "--hr-rest",
        type=int,
        required=True,
        help="Resting heart rate in bpm",
    )

    parser.add_argument(
        "--method",
        choices=["hrr", "hrmax_ratio"],
        default="hrr",
        help="Algorithm variant (default: hrr)",
    )
    parser.add_argument(
        "--no-drift-correction",
        action="store_true",
        default=False,
        help="Disable cardiac drift correction",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        # Parse FIT file
        activity = parse_fit_file(args.fit_file)

        # Calculate Running Index
        result = calculate_running_index(
            activity=activity,
            hr_max=args.hr_max,
            hr_rest=args.hr_rest,
            method=args.method,
            drift_correction=not args.no_drift_correction,
        )

        # Output results
        if args.json:
            print(format_json_report(activity, result, args.hr_max, args.hr_rest))
        else:
            print(format_text_report(activity, result, args.hr_max, args.hr_rest))

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except FitParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
