"""Validated local-time alarm requests."""

from platform_api.base import Platform


def set_alarm(platform: Platform, hour: int, minute: int) -> None:
    """Request a one-time alarm at a 24-hour local time."""
    if type(hour) is not int or not 0 <= hour <= 23:
        raise ValueError("Alarm hour must be an integer from 0 to 23")
    if type(minute) is not int or not 0 <= minute <= 59:
        raise ValueError("Alarm minute must be an integer from 0 to 59")
    platform.set_alarm(hour, minute)
