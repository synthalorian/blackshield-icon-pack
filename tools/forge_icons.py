#!/usr/bin/env python3
"""Blackshield Icon Forge (Android edition).

Renders the Blackshield icon set as PNGs at Android launcher densities.
Style canon (from blackshield-icon-forge skill):
  - Nordzy-style rounded tile, dark steel gradient #1E1E26 -> #101014
  - #2A2A31 hairline stroke on the tile
  - Bone-gradient glyph (#F5F1E8 -> #D9D2C5)
  - ONE blood accent per icon (#C1121F), restraint is the livery

Canvas: 192x192 (xxxhdpi launcher icon base). Densities:
  mdpi=48, hdpi=72, xhdpi=96, xxhdpi=144, xxxhdpi=192

Glyph shapes use Material icon path data (Apache-2.0) on a 24x24 grid,
scaled into the tile's safe zone.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "app" / "src" / "main" / "res"
SVG_OUT = ROOT / "build" / "svg"

DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

# Blackshield palette
TILE_HI = "#1E1E26"
TILE_LO = "#101014"
TILE_STROKE = "#2A2A31"
BONE_HI = "#F5F1E8"
BONE_LO = "#D9D2C5"
BLOOD = "#C1121F"

# Material icon path data (24x24 grid, Apache-2.0)
GLYPHS = {
    "ic_browser": "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z",
    "ic_mail": "M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z",
    "ic_phone": "M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z",
    "ic_messages": "M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z",
    "ic_camera": "M12 15.2c1.77 0 3.2-1.43 3.2-3.2s-1.43-3.2-3.2-3.2-3.2 1.43-3.2 3.2 1.43 3.2 3.2 3.2zM9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z",
    "ic_gallery": "M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z",
    "ic_music": "M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z",
    "ic_calendar": "M20 3h-1V1h-2v2H7V1H5v2H4c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 18H4V8h16v13z",
    "ic_settings": "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z",
    "ic_calculator": "M19 2H5c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6.25 7.72h11.5v3h-11.5v-3zm2.62 10.6l1.56-1.56-1.56-1.56 1.41-1.41 1.56 1.56 1.56-1.56 1.41 1.41-1.56 1.56 1.56 1.56-1.41 1.41-1.56-1.56-1.56 1.56-1.41-1.41z",
    # Brand shield for the pack's own launcher icon (Material 'shield')
    "ic_launcher": "M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z",
}

# Glyph scale: 24-grid -> ~110px inside the 171px tile
GLYPH_SCALE = 4.6
GLYPH_OFF = (192 - 24 * GLYPH_SCALE) / 2  # 40.8


def svg_tile(glyph_path: str, accent: str = "dash") -> str:
    """Full icon: dark steel tile + bone glyph + one blood accent."""
    if accent == "core":
        # Blood core inside the glyph silhouette (brand shield)
        accent_el = (
            f'<path d="{glyph_path}" fill="{BLOOD}" '
            f'transform="translate(76 76) scale(1.667)"/>'
        )
    else:
        # Blood dash at the bottom of the tile
        accent_el = f'<rect x="76" y="156" width="40" height="6" rx="3" fill="{BLOOD}"/>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{TILE_HI}"/>
      <stop offset="1" stop-color="{TILE_LO}"/>
    </linearGradient>
    <linearGradient id="bone" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{BONE_HI}"/>
      <stop offset="1" stop-color="{BONE_LO}"/>
    </linearGradient>
  </defs>
  <rect x="10.4" y="9.5" width="171.2" height="171.2" rx="34"
        fill="url(#tile)" stroke="{TILE_STROKE}" stroke-width="1.5"/>
  <path d="{glyph_path}" fill="url(#bone)"
        transform="translate({GLYPH_OFF:.1f} {GLYPH_OFF - 4:.1f}) scale({GLYPH_SCALE})"/>
  {accent_el}
</svg>
"""


def render(svg_path: Path, size: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size),
         str(svg_path), "-o", str(out_path)],
        check=True,
    )


def main() -> int:
    SVG_OUT.mkdir(parents=True, exist_ok=True)
    count = 0
    for name, path in GLYPHS.items():
        accent = "core" if name == "ic_launcher" else "dash"
        svg = svg_tile(path, accent)
        svg_path = SVG_OUT / f"{name}.svg"
        svg_path.write_text(svg)

        bucket = "mipmap" if name == "ic_launcher" else "drawable"
        for density, px in DENSITIES.items():
            render(svg_path, px, RES / f"{bucket}-{density}" / f"{name}.png")
            count += 1
            if bucket == "drawable" or name == "ic_launcher":
                # Separate foreground asset so the anydpi-v26 adaptive-icon
                # XML of the same name can reference it without a circular ref.
                render(svg_path, px, RES / f"{bucket}-{density}" / f"{name}_fg.png")
                count += 1
        # Keep the master SVG alongside sources for future re-forging
        (ROOT / "icons-src").mkdir(exist_ok=True)
        (ROOT / "icons-src" / f"{name}.svg").write_text(svg)

    print(f"forged {len(GLYPHS)} icons -> {count} PNGs "
          f"({len(DENSITIES)} densities each)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
