"""Datetime tool for retrieving current date and time information.

Uses the standard library ``zoneinfo`` module for timezone handling
(Python 3.9+). No external dependencies required.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)


@tool(
    name="get_current_datetime",
    description="Get the current date, time, and timezone information",
    parameters_schema={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": (
                    "IANA timezone name (e.g. Asia/Kolkata, "
                    "America/New_York). Defaults to UTC."
                ),
                "default": "UTC",
            },
        },
        "required": [],
    },
)
async def get_current_datetime(timezone: str = "UTC") -> str:
    """Get the current datetime in the specified timezone.

    Args:
        timezone: IANA timezone name. Defaults to ``"UTC"``.

    Returns:
        JSON string with datetime details including ISO format,
        date, time, day of week, and Unix timestamp.
    """
    logger.info("Getting current datetime for timezone: %s", timezone)

    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning("Invalid timezone requested: %s", timezone)
        return json.dumps({
            "error": (
                f"Unknown timezone: '{timezone}'. "
                "Use IANA timezone names like 'UTC', "
                "'Asia/Kolkata', or 'America/New_York'."
            ),
        })

    now = datetime.now(tz=tz)

    return json.dumps({
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": timezone,
        "utc_offset": now.strftime("%z"),
        "day_of_week": now.strftime("%A"),
        "unix_timestamp": int(now.timestamp()),
    })
