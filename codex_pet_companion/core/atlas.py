"""Shared v1/v2 validation and clockwise pointer direction selection."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from .constants import ATLAS_SIZES


def atlas_version(size: tuple[int, int], declared: object = None) -> int:
    if declared is not None:
        if type(declared) is not int or declared not in ATLAS_SIZES:
            raise ValueError("spriteVersionNumber must be 1 or 2.")
        if size != ATLAS_SIZES[declared]:
            raise ValueError(f"Codex v{declared} requires {ATLAS_SIZES[declared]}, got {size}.")
        return declared
    for version, expected in ATLAS_SIZES.items():
        if size == expected:
            return version
    raise ValueError(f"Unsupported atlas size {size}; expected 1536x1872 or 1536x2288.")


def inspect_spritesheet(path: Path, declared: object = None) -> int:
    with Image.open(path) as image:
        if image.format not in {"WEBP", "PNG"}:
            raise ValueError("Spritesheet must be PNG or WebP.")
        version = atlas_version(image.size, declared)
        image.load()
        return version


def look_direction(dx: float, dy: float, previous: int | None = None,
                   deadzone: float = 12.0, radius: float = 360.0) -> int | None:
    """Screen coordinates: up=0, right=4, down=8, left=12.

    A three-degree hysteresis margin prevents flicker at sector boundaries.
    The center and pointers outside the interaction radius return to idle.
    """
    distance = math.hypot(dx, dy)
    if distance <= deadzone or distance > radius:
        return None
    angle = math.degrees(math.atan2(dx, -dy)) % 360
    if previous is not None:
        delta = (angle - previous * 22.5 + 180) % 360 - 180
        if abs(delta) <= 14.25:
            return previous
    return int(math.floor(angle / 22.5 + 0.5)) % 16
