#!/usr/bin/env python3
"""CLI script to generate player cards for Statis Pro Football."""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.data.generate_2025_data import main as generate_2025
from engine.data.generate_2024_data import main as generate_2024

SUPPORTED_SEASONS = {
    2024: generate_2024,
    2025: generate_2025,
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate Statis Pro Football player cards"
    )
    parser.add_argument(
        "--season",
        type=int,
        default=2025,
        choices=sorted(SUPPORTED_SEASONS.keys()),
        help="Season year (default: 2025)",
    )
    args = parser.parse_args()

    generator = SUPPORTED_SEASONS.get(args.season)
    if generator:
        generator()
    else:
        print(f"Season {args.season} not yet supported. Available: {sorted(SUPPORTED_SEASONS.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
