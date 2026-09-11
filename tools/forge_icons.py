#!/usr/bin/env python3
"""Blackshield Icon Forge (Android edition) — v2 pipeline.

Reads tools/manifest.json (built by match_icons.py), dedupes apps that share
a glyph, then renders:
  - drawable-xxxhdpi/<name>.webp      legacy launcher icon (192px full tile)
  - drawable-xxxhdpi/<name>_fg.webp   adaptive foreground (432px, glyph only)
  - drawable-xxxhdpi/tile_bg.webp     shared adaptive background (432px)
  - drawable-anydpi-v26/<name>.xml    adaptive icon (bg + fg + monochrome)
  - res/xml/appfilter.xml             component -> drawable map (all apps)
  - assets/appfilter.xml              copy for older launchers
  - res/xml/drawable.xml              picker index
  - icons-src/<name>.svg              master SVG per unique drawable

Style canon: dark steel tile gradient #1E1E26 -> #101014, #2A2A31 hairline,
bone-gradient glyph (#F5F1E8 -> #D9D2C5), ONE blood accent (#C1121F).

Glyph path data: Material icons (Apache-2.0) + Simple Icons (CC0), 24x24 grid.
"""
import json
import multiprocessing as mp
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
LIB = TOOLS / "lib"
RES = ROOT / "app" / "src" / "main" / "res"
ASSETS = ROOT / "app" / "src" / "main" / "assets"
SVG_OUT = ROOT / "build" / "svg"
SRC_OUT = ROOT / "icons-src"

LEGACY_PX = 192   # 48dp @ xxxhdpi
ADAPTIVE_PX = 432  # 108dp @ xxxhdpi

# Blackshield palette
TILE_HI = "#1E1E26"
TILE_LO = "#101014"
TILE_STROKE = "#2A2A31"
BONE_HI = "#F5F1E8"
BONE_LO = "#D9D2C5"
BLOOD = "#C1121F"
BLOOD_DEEP = "#4A0B10"

# Variants: bone = canon (bone glyph, blood dash). red = canon swap
# (blood glyph, bone dash). Same steel tile both ways.
PALETTES = {
    "bone": {"glyph_hi": BONE_HI, "glyph_lo": BONE_LO, "accent": BLOOD},
    "red": {"glyph_hi": BLOOD, "glyph_lo": BLOOD_DEEP, "accent": BONE_LO},
}

SHIELD_PATH = "M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"

# Glyph scale: 24-grid -> px inside the 192 canvas
LEGACY_SCALE = 4.6            # 110px glyph
LEGACY_OFF = (192 - 24 * LEGACY_SCALE) / 2
FG_SCALE = 4.2                # ~100px on 192-equivalent space (adaptive safe zone)
FG_OFF = (192 - 24 * FG_SCALE) / 2

PATH_RE = re.compile(r'<path[^>]*\sd="([^"]+)"')
PRIO = {"exact": 0, "manual": 1, "suffix": 2, "fuzzy": 3, "brand-sub": 4, "keyword": 5, "letter": 6}


def glyph_inner(src: str, name: str) -> str:
    """Inner SVG content of the glyph (paths, circles, rects...)."""
    if src == "letter":
        # Bone initial-letter tile (DejaVu Sans Bold, centered on the 24-grid).
        ch = name.upper()
        return (f'<text x="12" y="16.2" font-family="DejaVu Sans" font-weight="bold" '
                f'font-size="15" text-anchor="middle">{ch}</text>')
    svg = (LIB / src / ("filled" if src == "material" else "icons") / f"{name}.svg").read_text()
    m = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    if not m:
        raise ValueError(f"no content in {src}/{name}")
    inner = re.sub(r"<title>.*?</title>", "", m.group(1), flags=re.S).strip()
    if not inner:
        raise ValueError(f"empty glyph {src}/{name}")
    return inner


def svg_legacy(glyph: str, pal: dict) -> str:
    """Full icon: dark steel tile + glyph + accent dash."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{TILE_HI}"/>
      <stop offset="1" stop-color="{TILE_LO}"/>
    </linearGradient>
    <linearGradient id="glyphgrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{pal['glyph_hi']}"/>
      <stop offset="1" stop-color="{pal['glyph_lo']}"/>
    </linearGradient>
  </defs>
  <rect x="10.4" y="9.5" width="171.2" height="171.2" rx="34"
        fill="url(#tile)" stroke="{TILE_STROKE}" stroke-width="1.5"/>
  <g fill="url(#glyphgrad)"
     transform="translate({LEGACY_OFF:.1f} {LEGACY_OFF - 4:.1f}) scale({LEGACY_SCALE})">{glyph}</g>
  <rect x="76" y="156" width="40" height="6" rx="3" fill="{pal['accent']}"/>
</svg>
"""


def svg_fg(glyph: str, pal: dict) -> str:
    """Adaptive foreground: glyph only, transparent bg."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <defs>
    <linearGradient id="glyphgrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{pal['glyph_hi']}"/>
      <stop offset="1" stop-color="{pal['glyph_lo']}"/>
    </linearGradient>
  </defs>
  <g fill="url(#glyphgrad)"
     transform="translate({FG_OFF:.1f} {FG_OFF:.1f}) scale({FG_SCALE})">{glyph}</g>
</svg>
"""


def svg_launcher(pal: dict, legacy: bool) -> str:
    """Pack's own launcher icon: tile + shield + accent core (core = accent)."""
    tile = ""
    if legacy:
        tile = (f'<rect x="10.4" y="9.5" width="171.2" height="171.2" rx="34" '
                f'fill="url(#tile)" stroke="{TILE_STROKE}" stroke-width="1.5"/>')
    off = LEGACY_OFF if legacy else FG_OFF
    scale = LEGACY_SCALE if legacy else FG_SCALE
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{TILE_HI}"/>
      <stop offset="1" stop-color="{TILE_LO}"/>
    </linearGradient>
    <linearGradient id="glyphgrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{pal['glyph_hi']}"/>
      <stop offset="1" stop-color="{pal['glyph_lo']}"/>
    </linearGradient>
  </defs>
  {tile}
  <g fill="url(#glyphgrad)"
     transform="translate({off:.1f} {off:.1f}) scale({scale})"><path d="{SHIELD_PATH}"/></g>
  <path d="{SHIELD_PATH}" fill="{pal['accent']}" transform="translate(76 76) scale(1.667)"/>
</svg>
"""


SVG_TILE_BG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{TILE_HI}"/>
      <stop offset="1" stop-color="{TILE_LO}"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="192" height="192" fill="url(#tile)"/>
</svg>
"""

# Unthemed-app wrapping (iconback/iconmask/iconupon/scale): launchers composite
# any uncovered app's own icon onto our tile so NOTHING looks out of place.
SVG_ICONMASK = """<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <rect x="10.4" y="9.5" width="171.2" height="171.2" rx="34" fill="#ffffff"/>
</svg>
"""


def svg_iconupon(accent: str) -> str:
    """Overlay stamped on unthemed icons: hairline ring + accent dash."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <rect x="10.4" y="9.5" width="171.2" height="171.2" rx="34"
        fill="none" stroke="{TILE_STROKE}" stroke-width="1.5"/>
  <rect x="76" y="156" width="40" height="6" rx="3" fill="{accent}"/>
</svg>
"""


SCALE_FACTOR = 0.75


def render_webp(svg_path: Path, px: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".png")
    subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px),
                    str(svg_path), "-o", str(tmp)], check=True)
    subprocess.run(["magick", str(tmp), "-quality", "92", str(out_path)], check=True)
    tmp.unlink()


def render_one(job):
    name, legacy_svg, fg_svg, res_dir = job
    res = Path(res_dir)
    try:
        render_webp(legacy_svg, LEGACY_PX, res / "drawable-xxxhdpi" / f"{name}.webp")
        render_webp(fg_svg, ADAPTIVE_PX, res / "drawable-xxxhdpi" / f"{name}_fg.webp")
        return None
    except subprocess.CalledProcessError as e:
        return f"{name}: {e}"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=sorted(PALETTES), default="bone",
                    help="bone = canon (default, main/res); red = canon swap (src/red/res)")
    args = ap.parse_args()
    pal = PALETTES[args.variant]
    red = args.variant == "red"
    out_res = ROOT / "app" / "src" / "red" / "res" if red else RES

    manifest = json.loads((TOOLS / "manifest.json").read_text())

    # ---- dedupe apps by glyph -> one drawable per unique glyph ----
    groups = defaultdict(list)  # (src, glyph) -> [(drawable, match, components)]
    for name, v in manifest.items():
        groups[(v["glyph_src"], v["glyph_name"])].append(
            (name, v["match"], v["components"]))

    drawables = {}  # drawable name -> (src, glyph, [components])
    for (src, gname), entries in groups.items():
        entries.sort(key=lambda e: (PRIO.get(e[1], 5), len(e[0]), e[0]))
        rep = f"ic_letter_{gname}" if src == "letter" else entries[0][0]
        comps = [c for _, _, cl in entries for c in cl]
        drawables[rep] = (src, gname, comps)
    print(f"{len(manifest)} apps -> {len(drawables)} unique drawables, "
          f"{sum(len(v[2]) for v in drawables.values())} components")

    # ---- clean generated dirs (bone/main only; red overlays its own tree) ----
    if not red:
        for d in out_res.glob("drawable-*"):
            if d.name == "drawable-anydpi-v26":
                for f in d.glob("ic_*.xml"):
                    f.unlink()
            else:
                shutil.rmtree(d)
    else:
        for d in out_res.glob("drawable-*"):
            shutil.rmtree(d)
    (out_res / "drawable-xxxhdpi").mkdir(parents=True, exist_ok=True)
    (out_res / "drawable-anydpi-v26").mkdir(parents=True, exist_ok=True)
    SVG_OUT.mkdir(parents=True, exist_ok=True)
    SRC_OUT.mkdir(exist_ok=True)

    # ---- shared adaptive background + unthemed-app wrap assets ----
    bg_svg = SVG_OUT / "tile_bg.svg"
    bg_svg.write_text(SVG_TILE_BG)
    render_webp(bg_svg, ADAPTIVE_PX, out_res / "drawable-xxxhdpi" / "tile_bg.webp")
    mask_svg = SVG_OUT / "iconmask.svg"
    mask_svg.write_text(SVG_ICONMASK)
    render_webp(mask_svg, LEGACY_PX, out_res / "drawable-xxxhdpi" / "iconmask.webp")
    upon_svg = SVG_OUT / f"{args.variant}_iconupon.svg"
    upon_svg.write_text(svg_iconupon(pal["accent"]))
    render_webp(upon_svg, LEGACY_PX, out_res / "drawable-xxxhdpi" / "iconupon.webp")
    # iconback = full-bleed tile at legacy size
    render_webp(bg_svg, LEGACY_PX, out_res / "drawable-xxxhdpi" / "iconback.webp")

    # ---- render all drawables ----
    jobs = []
    for name, (src, gname, _) in sorted(drawables.items()):
        glyph = glyph_inner(src, gname)
        legacy = SVG_OUT / f"{args.variant}_{name}.svg"
        fg = SVG_OUT / f"{args.variant}_{name}_fg.svg"
        legacy.write_text(svg_legacy(glyph, pal))
        fg.write_text(svg_fg(glyph, pal))
        if not red:
            (SRC_OUT / f"{name}.svg").write_text(svg_legacy(glyph, pal))
        jobs.append((name, legacy, fg, str(out_res)))

    with mp.Pool() as pool:
        errors = [e for e in pool.map(render_one, jobs) if e]
    if errors:
        print(f"{len(errors)} render errors:", *errors[:10], sep="\n  ")
        return 1
    print(f"rendered {len(jobs)} drawables x2 (legacy + fg) as webp")

    # ---- adaptive icon XMLs ----
    adaptive_tpl = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@drawable/tile_bg" />\n'
        '    <foreground android:drawable="@drawable/{name}_fg" />\n'
        '    <monochrome android:drawable="@drawable/{name}_fg" />\n'
        '</adaptive-icon>\n'
    )
    for name in drawables:
        (out_res / "drawable-anydpi-v26" / f"{name}.xml").write_text(
            adaptive_tpl.format(name=name))

    if red:
        # ---- red variant extras: launcher icon + app name overlay ----
        launch = SVG_OUT / "red_ic_launcher.svg"
        launch.write_text(svg_launcher(pal, legacy=True))
        launch_fg = SVG_OUT / "red_ic_launcher_fg.svg"
        launch_fg.write_text(svg_launcher(pal, legacy=False))
        render_webp(launch, LEGACY_PX, out_res / "mipmap-xxxhdpi" / "ic_launcher.webp")
        render_webp(launch_fg, ADAPTIVE_PX, out_res / "mipmap-xxxhdpi" / "ic_launcher_fg.webp")
        (out_res / "mipmap-anydpi-v26").mkdir(parents=True, exist_ok=True)
        (out_res / "mipmap-anydpi-v26" / "ic_launcher.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@drawable/tile_bg" />\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_fg" />\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_fg" />\n'
            '</adaptive-icon>\n')
        (out_res / "values").mkdir(parents=True, exist_ok=True)
        (out_res / "values" / "strings.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<resources>\n'
            '    <string name="app_name">Blackshield Red</string>\n'
            '</resources>\n')
        print(f"red variant: {len(jobs)} drawables + launcher -> {out_res}")
        return 0

    # ---- appfilter.xml (res + assets) ----
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!-- GENERATED by tools/forge_icons.py — do not hand-edit.',
        f'     {len(drawables)} icons, {sum(len(v[2]) for v in drawables.values())} components. -->',
        '<resources>',
        '    <!-- Unthemed apps: wrap their own icon in the Blackshield tile -->',
        '    <iconback img1="iconback" />',
        '    <iconmask img1="iconmask" />',
        '    <iconupon img1="iconupon" />',
        f'    <scale factor="{SCALE_FACTOR}" />',
    ]
    for name, (_, _, comps) in sorted(drawables.items()):
        lines.append(f'    <!-- {name} -->')
        for c in sorted(set(comps)):
            lines.append(f'    <item component="ComponentInfo{{{c}}}" drawable="{name}" />')
    lines.append('</resources>')
    appfilter = "\n".join(lines) + "\n"
    (RES / "xml" / "appfilter.xml").write_text(appfilter)
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "appfilter.xml").write_text(appfilter)

    # ---- drawable.xml (picker index) ----
    dlines = ['<?xml version="1.0" encoding="utf-8"?>',
              '<!-- GENERATED by tools/forge_icons.py -->', '<resources>']
    dlines += [f'    <item drawable="{n}" />' for n in sorted(drawables)]
    dlines.append('</resources>')
    (RES / "xml" / "drawable.xml").write_text("\n".join(dlines) + "\n")

    print(f"appfilter: {sum(len(v[2]) for v in drawables.values())} entries, "
          f"drawable.xml: {len(drawables)} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
