"""Tests for the sprite rendering utilities."""

from io import BytesIO, StringIO
from pathlib import Path

import pytest
from PIL import Image
from rich.panel import Panel
from rich.text import Text

from pokedo.utils.sprites import (
    _is_transparent,
    _load_image,
    display_sprite,
    render_sprite_panel,
    sprite_to_rich_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png_bytes(width: int, height: int, color: tuple = (255, 0, 0, 255)) -> bytes:
    """Create a solid-color RGBA PNG as raw bytes."""
    img = Image.new("RGBA", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_png_file(tmp_path: Path, width: int, height: int, color: tuple = (255, 0, 0, 255)) -> Path:
    """Create a solid-color RGBA PNG file and return its path."""
    img = Image.new("RGBA", (width, height), color)
    path = tmp_path / "sprite.png"
    img.save(path, format="PNG")
    return path


def _make_checkerboard_png_bytes(
    width: int, height: int,
    color_a: tuple = (255, 0, 0, 255),
    color_b: tuple = (0, 0, 0, 0),
) -> bytes:
    """Create a checkerboard pattern PNG (alternating opaque / transparent)."""
    img = Image.new("RGBA", (width, height), color_b)
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            if (x + y) % 2 == 0:
                pixels[x, y] = color_a
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _is_transparent
# ---------------------------------------------------------------------------

class TestIsTransparent:
    """Tests for the _is_transparent helper."""

    def test_fully_transparent_pixel(self):
        assert _is_transparent((0, 0, 0, 0)) is True

    def test_near_transparent_pixel(self):
        assert _is_transparent((255, 255, 255, 10)) is True

    def test_fully_opaque_pixel(self):
        assert _is_transparent((255, 0, 0, 255)) is False

    def test_partially_opaque_pixel(self):
        assert _is_transparent((100, 100, 100, 128)) is False

    def test_threshold_boundary_below(self):
        assert _is_transparent((0, 0, 0, 19), threshold=20) is True

    def test_threshold_boundary_at(self):
        assert _is_transparent((0, 0, 0, 20), threshold=20) is False

    def test_rgb_only_pixel_no_alpha(self):
        """A 3-channel pixel (no alpha) should not be transparent."""
        assert _is_transparent((255, 0, 0)) is False

    def test_custom_threshold(self):
        assert _is_transparent((0, 0, 0, 50), threshold=100) is True
        assert _is_transparent((0, 0, 0, 50), threshold=40) is False


# ---------------------------------------------------------------------------
# _load_image
# ---------------------------------------------------------------------------

class TestLoadImage:
    """Tests for the _load_image helper."""

    def test_load_from_bytes(self):
        data = _make_png_bytes(4, 4)
        img = _load_image(data)
        assert img.mode == "RGBA"
        assert img.size == (4, 4)

    def test_load_from_path(self, tmp_path):
        path = _make_png_file(tmp_path, 8, 8)
        img = _load_image(path)
        assert img.mode == "RGBA"
        assert img.size == (8, 8)

    def test_load_converts_rgb_to_rgba(self):
        """An RGB image (no alpha) should be converted to RGBA."""
        img = Image.new("RGB", (4, 4), (255, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        loaded = _load_image(buf.getvalue())
        assert loaded.mode == "RGBA"

    def test_load_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(Exception):
            _load_image(tmp_path / "missing.png")


# ---------------------------------------------------------------------------
# sprite_to_rich_text
# ---------------------------------------------------------------------------

class TestSpriteToRichText:
    """Tests for the main sprite rendering function."""

    def test_returns_text_object(self):
        data = _make_png_bytes(2, 2)
        result = sprite_to_rich_text(data)
        assert isinstance(result, Text)

    def test_output_contains_characters(self):
        data = _make_png_bytes(4, 4, (255, 0, 0, 255))
        result = sprite_to_rich_text(data)
        plain = result.plain
        assert len(plain.strip()) > 0

    def test_even_height_no_padding(self):
        """An even-height image should not need padding."""
        data = _make_png_bytes(4, 4)
        result = sprite_to_rich_text(data)
        lines = result.plain.rstrip("\n").split("\n")
        # 4 pixel rows -> 2 terminal rows
        assert len(lines) == 2

    def test_odd_height_padded_to_even(self):
        """An odd-height image should be padded to even height."""
        data = _make_png_bytes(4, 3)
        result = sprite_to_rich_text(data)
        lines = result.plain.rstrip("\n").split("\n")
        # 3 pixel rows padded to 4 -> 2 terminal rows
        assert len(lines) == 2

    def test_transparent_image_all_spaces(self):
        """A fully transparent image should produce only spaces/newlines."""
        data = _make_png_bytes(4, 4, (0, 0, 0, 0))
        result = sprite_to_rich_text(data)
        plain = result.plain.replace("\n", "")
        assert plain.strip() == ""

    def test_opaque_image_has_half_blocks(self):
        """A fully opaque image should use the upper-half-block character."""
        data = _make_png_bytes(4, 4, (255, 0, 0, 255))
        result = sprite_to_rich_text(data)
        assert "\u2580" in result.plain

    def test_bg_color_option(self):
        """With bg_color set, transparent pixels should still yield output."""
        data = _make_png_bytes(4, 4, (0, 0, 0, 0))
        result = sprite_to_rich_text(data, bg_color="#1e1e2e")
        # Should have styled spaces
        assert isinstance(result, Text)

    def test_mixed_transparency_uses_lower_half_block(self):
        """When top is transparent and bottom is opaque, use lower-half-block."""
        img = Image.new("RGBA", (1, 2), (0, 0, 0, 0))
        pixels = img.load()
        pixels[0, 0] = (0, 0, 0, 0)      # top transparent
        pixels[0, 1] = (255, 0, 0, 255)   # bottom opaque
        buf = BytesIO()
        img.save(buf, format="PNG")
        result = sprite_to_rich_text(buf.getvalue())
        assert "\u2584" in result.plain  # lower half block

    def test_top_only_uses_upper_half_block(self):
        """When top is opaque and bottom is transparent, use upper-half-block."""
        img = Image.new("RGBA", (1, 2), (0, 0, 0, 0))
        pixels = img.load()
        pixels[0, 0] = (0, 255, 0, 255)   # top opaque
        pixels[0, 1] = (0, 0, 0, 0)       # bottom transparent
        buf = BytesIO()
        img.save(buf, format="PNG")
        result = sprite_to_rich_text(buf.getvalue())
        assert "\u2580" in result.plain  # upper half block

    def test_width_preserved_in_output(self):
        """Each terminal row should have width characters (plus newline)."""
        w, h = 6, 4
        data = _make_png_bytes(w, h, (100, 100, 100, 255))
        result = sprite_to_rich_text(data)
        lines = result.plain.rstrip("\n").split("\n")
        for line in lines:
            assert len(line) == w

    def test_accepts_path(self, tmp_path):
        path = _make_png_file(tmp_path, 4, 4)
        result = sprite_to_rich_text(path)
        assert isinstance(result, Text)

    def test_single_pixel_image(self):
        """A 1x1 image should produce one row."""
        data = _make_png_bytes(1, 1, (255, 0, 0, 255))
        result = sprite_to_rich_text(data)
        lines = result.plain.rstrip("\n").split("\n")
        # 1 pixel row padded to 2 -> 1 terminal row
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# render_sprite_panel
# ---------------------------------------------------------------------------

class TestRenderSpritePanel:
    """Tests for the panel wrapper."""

    def test_returns_panel(self):
        data = _make_png_bytes(4, 4)
        panel = render_sprite_panel(data, title="Test")
        assert isinstance(panel, Panel)

    def test_panel_has_title(self):
        data = _make_png_bytes(4, 4)
        panel = render_sprite_panel(data, title="Pikachu")
        assert panel.title is not None

    def test_panel_has_subtitle(self):
        data = _make_png_bytes(4, 4)
        panel = render_sprite_panel(data, title="Pikachu", subtitle="Electric")
        assert panel.subtitle is not None

    def test_panel_no_expand(self):
        data = _make_png_bytes(4, 4)
        panel = render_sprite_panel(data)
        assert panel.expand is False


# ---------------------------------------------------------------------------
# display_sprite
# ---------------------------------------------------------------------------

class TestDisplaySprite:
    """Tests for the convenience display function."""

    def test_display_does_not_raise(self, tmp_path):
        """Calling display_sprite should not raise exceptions."""
        path = _make_png_file(tmp_path, 4, 4)
        from rich.console import Console
        c = Console(file=StringIO(), force_terminal=True)
        display_sprite(path, title="Test", console=c)

    def test_display_with_bg_color(self, tmp_path):
        path = _make_png_file(tmp_path, 4, 4, (0, 0, 0, 0))
        from rich.console import Console
        c = Console(file=StringIO(), force_terminal=True)
        display_sprite(path, title="Ghost", bg_color="#000000", console=c)

    def test_display_with_bytes(self):
        data = _make_png_bytes(4, 4)
        from rich.console import Console
        c = Console(file=StringIO(), force_terminal=True)
        display_sprite(data, title="Bytes sprite", console=c)

    def test_display_defaults_to_new_console(self, tmp_path):
        """When console=None, display_sprite should create its own Console."""
        path = _make_png_file(tmp_path, 2, 2)
        # Should not raise -- just prints to stdout
        display_sprite(path, title="Default Console")
