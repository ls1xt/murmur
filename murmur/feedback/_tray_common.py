"""Shared constants and icon rendering for tray backends."""

from __future__ import annotations

from typing import Any, Literal

TrayState = Literal["idle", "recording", "error"]

# Icon colors: (fill, outline) per state
_STATE_COLORS: dict[str, tuple[str, str]] = {
    "idle": ("#888888", "#444444"),
    "recording": ("#ff3333", "#cc0000"),
    "error": ("#ff9933", "#cc6600"),
}

STATE_TITLES: dict[str, str] = {
    "idle": "Idle",
    "recording": "Recording",
    "error": "Error",
}

ICON_SIZE = 64


def create_icon_image(state: TrayState) -> Any:
    """Create a 64x64 RGBA PIL image with a colored circle for the state.

    Returns a PIL.Image.Image or raises ImportError if Pillow unavailable.
    """
    from PIL import Image, ImageDraw

    fill, outline = _STATE_COLORS.get(state, _STATE_COLORS["idle"])

    img: Any = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw: Any = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
        fill=fill,
        outline=outline,
        width=2,
    )
    return img
