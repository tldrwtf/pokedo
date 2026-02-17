"""Sprite rendering utilities for displaying Pokemon sprites in the terminal.

Uses Unicode half-block characters and true color to render pixel-accurate
sprite previews directly in the terminal.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    from PIL import Image as PILImage


def _load_image(source: Path | bytes) -> PILImage.Image:
    """Load an image from a file path or raw bytes."""
    from PIL import Image

    if isinstance(source, (str, Path)):
        return Image.open(source).convert("RGBA")
    return Image.open(BytesIO(source)).convert("RGBA")


def _is_transparent(pixel: tuple[int, ...], threshold: int = 20) -> bool:
    """Check if a pixel is effectively transparent."""
    return len(pixel) >= 4 and pixel[3] < threshold


def sprite_to_rich_text(
    source: Path | bytes,
    *,
    bg_color: str | None = None,
) -> Text:
    """Convert a sprite image to Rich Text using Unicode half-block characters.

    Each terminal row encodes two pixel rows using the upper-half-block
    character (U+2580). The foreground color represents the top pixel and
    the background color represents the bottom pixel.

    Args:
        source: Path to a PNG file or raw image bytes.
        bg_color: Hex color for transparent pixels (e.g. "#1e1e2e"). None = no bg.

    Returns:
        A Rich Text object ready for console.print().
    """
    from PIL import Image

    img = _load_image(source)

    width, height = img.size

    # Ensure even height for half-block pairing
    if height % 2 != 0:
        new_img = Image.new("RGBA", (width, height + 1), (0, 0, 0, 0))
        new_img.paste(img, (0, 0))
        img = new_img
        height += 1

    pixels = img.load()
    text = Text()

    upper_half_block = "\u2580"  # top half

    for y in range(0, height, 2):
        for x in range(width):
            top = pixels[x, y]
            bottom = pixels[x, y + 1] if (y + 1) < height else (0, 0, 0, 0)

            top_trans = _is_transparent(top)
            bottom_trans = _is_transparent(bottom)

            if top_trans and bottom_trans:
                # Both transparent -- space with optional background
                if bg_color:
                    text.append(" ", style=f"on {bg_color}")
                else:
                    text.append(" ")
            elif top_trans:
                # Only bottom pixel visible -- lower half block
                br, bg, bb = bottom[0], bottom[1], bottom[2]
                color = f"rgb({br},{bg},{bb})"
                if bg_color:
                    text.append(upper_half_block, style=f"{bg_color} on {color}")
                else:
                    # Use lower half block instead
                    text.append("\u2584", style=f"{color}")
            elif bottom_trans:
                # Only top pixel visible -- upper half block
                tr, tg, tb = top[0], top[1], top[2]
                color = f"rgb({tr},{tg},{tb})"
                if bg_color:
                    text.append(upper_half_block, style=f"{color} on {bg_color}")
                else:
                    text.append(upper_half_block, style=f"{color}")
            else:
                # Both visible
                tr, tg, tb = top[0], top[1], top[2]
                br, bg_val, bb = bottom[0], bottom[1], bottom[2]
                fg = f"rgb({tr},{tg},{tb})"
                bg_style = f"rgb({br},{bg_val},{bb})"
                text.append(upper_half_block, style=f"{fg} on {bg_style}")

        text.append("\n")

    return text


def render_sprite_panel(
    source: Path | bytes,
    title: str = "",
    *,
    bg_color: str | None = None,
    subtitle: str | None = None,
) -> Panel:
    """Render a sprite inside a Rich Panel.

    Args:
        source: Path to a PNG file or raw image bytes.
        title: Panel title (e.g. Pokemon name).
        bg_color: Hex color for transparent pixels.
        subtitle: Optional subtitle text.

    Returns:
        A Rich Panel containing the rendered sprite.
    """
    from rich import box

    text = sprite_to_rich_text(source, bg_color=bg_color)
    return Panel(
        text,
        title=title,
        subtitle=subtitle,
        box=box.ROUNDED,
        expand=False,
    )


def display_sprite(
    source: Path | bytes,
    title: str = "",
    *,
    bg_color: str | None = None,
    subtitle: str | None = None,
    console: Console | None = None,
) -> None:
    """Display a sprite in the terminal.

    Convenience function that creates and prints a sprite panel.

    Args:
        source: Path to a PNG file or raw image bytes.
        title: Panel title.
        bg_color: Background color for transparent areas.
        subtitle: Optional subtitle.
        console: Rich Console instance (uses default if None).
    """
    if console is None:
        console = Console()

    panel = render_sprite_panel(
        source, title=title, bg_color=bg_color, subtitle=subtitle
    )
    console.print(panel)
