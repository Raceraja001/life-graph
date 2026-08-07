#!/usr/bin/env python3
"""
Keep‑alive script with configurable interval, optional quiet mode,
and simple rotating log output.

Usage examples:
    python keep_awake.py                 # default: 30‑second interval, prints to console
    python keep_awake.py --interval 10   # heartbeat every 10 seconds
    python keep_awake.py --quiet          # no console output, only log file
    python keep_awake.py --log logs/ka.log --interval 5
"""

import argparse
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

def setup_logger(log_path: str | None) -> logging.Logger:
    """Configure a rotating file logger if a path is supplied."""
    logger = logging.getLogger("keepalive")
    logger.setLevel(logging.INFO)

    # Always have a console handler unless we are in quiet mode
    if not args.quiet:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - Alive: %(message)s")
        console.setFormatter(formatter)
        logger.addHandler(console)

    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_formatter = logging.Formatter("%(asctime)s - Alive")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def main() -> None:
    global args
    parser = argparse.ArgumentParser(description="Prevent system sleep/hibernate.")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Seconds between heartbeats (default: 30)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress console output (log only)."
    )
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="Path to a log file (will rotate after 1 MB, keep 3 backups).",
    )
    args = parser.parse_args()

    logger = setup_logger(args.log)

    try:
        while True:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            msg = f"Alive: {timestamp}"
            logger.info(msg)          # goes to file and/or console
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Keep‑alive stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()