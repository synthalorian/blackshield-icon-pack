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

# Glyph scale: 24-grid -> px inside the 192 canvas
LEGACY_SCALE = 4.6            # 110px glyph
LEGACY_OFF = (192 - 24 * LEGACY_SCALE) / 2
FG_SCALE = 4.2                # ~100px on 192-equivalent space (adaptive safe zone)
FG_OFF = (192 - 24 * FG_SCALE) / 2

PATH_RE = re.compile(r'<path[^>]*\sd="([^"]+)"')
PRIO = {"exact": 0, "manual": 1, "suffix": 2, "fuzzy": 3, "keyword": 4}


def glyph_inner(src: str, name: str) -> str:
    """Inner SVG content of the glyph (paths, circles, rects...)."""
    svg = (LIB / src / ("filled" if src == "material" else "icons") / f"{name}.svg").read_text()
    m = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    if not m:
        raise ValueError(f"no content in {src}/{name}")
    inner = re.sub(r"<title>.*?</title>", "", m.group(1), flags=re.S).strip()
    if not inner:
        raise ValueError(f"empty glyph {src}/{name}")
    return inner


def svg_legacy(glyph: str) -> str:
    """Full icon: dark steel tile + bone glyph + blood dash."""
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
  <g fill="url(#bone)"
     transform="translate({LEGACY_OFF:.1f} {LEGACY_OFF - 4:.1f}) scale({LEGACY_SCALE})">{glyph}</g>
  <rect x="76" y="156" width="40" height="6" rx="3" fill="{BLOOD}"/>
</svg>
"""


def svg_fg(glyph: str) -> str:
    """Adaptive foreground: bone glyph only, transparent bg."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <defs>
    <linearGradient id="bone" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{BONE_HI}"/>
      <stop offset="1" stop-color="{BONE_LO}"/>
    </linearGradient>
  </defs>
  <g fill="url(#bone)"
     transform="translate({FG_OFF:.1f} {FG_OFF:.1f}) scale({FG_SCALE})">{glyph}</g>
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


def render_webp(svg_path: Path, px: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".png")
    subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px),
                    str(svg_path), "-o", str(tmp)], check=True)
    subprocess.run(["magick", str(tmp), "-quality", "92", str(out_path)], check=True)
    tmp.unlink()


def render_one(job):
    name, legacy_svg, fg_svg = job
    try:
        render_webp(legacy_svg, LEGACY_PX, RES / "drawable-xxxhdpi" / f"{name}.webp")
        render_webp(fg_svg, ADAPTIVE_PX, RES / "drawable-xxxhdpi" / f"{name}_fg.webp")
        return None
    except subprocess.CalledProcessError as e:
        return f"{name}: {e}"


def main() -> int:
    manifest = json.loads((TOOLS / "manifest.json").read_text())

    # ---- dedupe apps by glyph -> one drawable per unique glyph ----
    groups = defaultdict(list)  # (src, glyph) -> [(drawable, match, components)]
    for name, v in manifest.items():
        groups[(v["glyph_src"], v["glyph_name"])].append(
            (name, v["match"], v["components"]))

    drawables = {}  # drawable name -> (src, glyph, [components])
    for (src, gname), entries in groups.items():
        entries.sort(key=lambda e: (PRIO.get(e[1], 5), len(e[0]), e[0]))
        rep = entries[0][0]
        comps = [c for _, _, cl in entries for c in cl]
        drawables[rep] = (src, gname, comps)
    print(f"{len(manifest)} apps -> {len(drawables)} unique drawables, "
          f"{sum(len(v[2]) for v in drawables.values())} components")

    # ---- clean generated dirs ----
    for d in RES.glob("drawable-*"):
        if d.name == "drawable-anydpi-v26":
            for f in d.glob("ic_*.xml"):
                f.unlink()
        else:
            shutil.rmtree(d)
    (RES / "drawable-xxxhdpi").mkdir(exist_ok=True)
    (RES / "drawable-anydpi-v26").mkdir(exist_ok=True)
    SVG_OUT.mkdir(parents=True, exist_ok=True)
    SRC_OUT.mkdir(exist_ok=True)

    # ---- shared adaptive background ----
    bg_svg = SVG_OUT / "tile_bg.svg"
    bg_svg.write_text(SVG_TILE_BG)
    render_webp(bg_svg, ADAPTIVE_PX, RES / "drawable-xxxhdpi" / "tile_bg.webp")

    # ---- render all drawables ----
    jobs = []
    for name, (src, gname, _) in sorted(drawables.items()):
        glyph = glyph_inner(src, gname)
        legacy = SVG_OUT / f"{name}.svg"
        fg = SVG_OUT / f"{name}_fg.svg"
        legacy.write_text(svg_legacy(glyph))
        fg.write_text(svg_fg(glyph))
        (SRC_OUT / f"{name}.svg").write_text(svg_legacy(glyph))
        jobs.append((name, legacy, fg))

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
        (RES / "drawable-anydpi-v26" / f"{name}.xml").write_text(
            adaptive_tpl.format(name=name))

    # ---- appfilter.xml (res + assets) ----
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!-- GENERATED by tools/forge_icons.py — do not hand-edit.',
        f'     {len(drawables)} icons, {sum(len(v[2]) for v in drawables.values())} components. -->',
        '<resources>',
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
