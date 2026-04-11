#!/usr/bin/env python3
"""CLI script to generate player cards for Statis Pro Football."""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.data.generate_2025_data import main as generate_2025


def main():
    parser = argparse.ArgumentParser(
        description="Generate Statis Pro Football player cards"
    )
    parser.add_argument(
        "--season",
        type=int,
        default=2025,
        help="Season year (default: 2025)",
    )
    args = parser.parse_args()

    if args.season == 2025:
        generate_2025()
    else:
        print(f"Season {args.season} not yet supported. Only 2025 is available.")
        sys.exit(1)


if __name__ == "__main__":
    main()
