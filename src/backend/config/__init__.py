"""
Config module for GridKey BESS Optimizer
"""

from .battery_config import (
    BATTERY_CONFIG,
    C_RATE_OPTIONS,
    get_battery_config,
    get_config_summary,
)

__all__ = [
    "BATTERY_CONFIG",
    "C_RATE_OPTIONS",
    "get_battery_config",
    "get_config_summary",
]
