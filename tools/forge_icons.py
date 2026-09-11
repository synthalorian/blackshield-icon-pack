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


def render_recolor(master: Path, out_res: Path, name: str, pal: dict) -> None:
    """Recolor an extracted app icon into the livery: luminance -> glyph ramp,
    alpha preserved. Produces <name>.webp (legacy tile) + <name>_fg.webp."""
    from PIL import Image, ImageDraw
    import numpy as np

    im = Image.open(master).convert("RGBA")
    s = max(im.size)
    sq = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sq.paste(im, ((s - im.width) // 2, (s - im.height) // 2))
    arr = np.asarray(sq).astype(np.float32)
    lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0
    alpha = arr[..., 3] / 255.0
    m = alpha > 0.05
    if m.any():
        lo, hi = np.percentile(lum[m], 2), np.percentile(lum[m], 98)
        lum = np.clip((lum - lo) / max(hi - lo, 1e-6), 0, 1)
    glo = np.array([int(pal["glyph_lo"][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
    ghi = np.array([int(pal["glyph_hi"][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
    rgb = glo[None, None, :] + lum[..., None] * (ghi - glo)[None, None, :]
    icon = Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8))

    full_bleed = (m.mean() > 0.9) if m.any() else False

    # tile mask (shared)
    def squircle_mask(px: int) -> "Image.Image":
        r = 34 / 192 * px
        inset = 10.4 / 192 * px
        size = 171.2 / 192 * px
        tm = Image.new("L", (px, px), 0)
        ImageDraw.Draw(tm).rounded_rectangle(
            [inset, inset, inset + size, inset + size], radius=r, fill=255)
        return tm

    if full_bleed:
        # full-bleed artwork IS the tile: mask recolored icon into the squircle
        fg = Image.new("RGBA", (ADAPTIVE_PX, ADAPTIVE_PX), (0, 0, 0, 0))
        icon_fg = icon.resize((ADAPTIVE_PX, ADAPTIVE_PX), Image.Resampling.LANCZOS)
        fg.paste(icon_fg, (0, 0), squircle_mask(ADAPTIVE_PX))
        fg.save(out_res / "drawable-xxxhdpi" / f"{name}_fg.webp", quality=92)

        full = Image.new("RGBA", (LEGACY_PX, LEGACY_PX), (0, 0, 0, 0))
        icon_leg = icon.resize((LEGACY_PX, LEGACY_PX), Image.Resampling.LANCZOS)
        full.paste(icon_leg, (0, 0), squircle_mask(LEGACY_PX))
        draw = ImageDraw.Draw(full)
        inset = 10.4
        draw.rounded_rectangle([inset, inset - 0.9, inset + 171.2, inset - 0.9 + 171.2],
                               radius=34, outline=TILE_STROKE, width=2)
        draw.rounded_rectangle([76, 156, 116, 162], radius=3, fill=pal["accent"])
        full.save(out_res / "drawable-xxxhdpi" / f"{name}.webp", quality=92)
        return

    # glyph-style: transparent-bg icon at safe-zone size on our tile
    fg_px = round(FG_SCALE * 24 / 192 * ADAPTIVE_PX)
    fg = Image.new("RGBA", (ADAPTIVE_PX, ADAPTIVE_PX), (0, 0, 0, 0))
    icon_fg = icon.resize((fg_px, fg_px), Image.Resampling.LANCZOS)
    fg.paste(icon_fg, ((ADAPTIVE_PX - fg_px) // 2, (ADAPTIVE_PX - fg_px) // 2), icon_fg)
    fg.save(out_res / "drawable-xxxhdpi" / f"{name}_fg.webp", quality=92)

    # legacy: steel tile + icon at LEGACY size + accent dash
    leg = Image.new("RGBA", (LEGACY_PX, LEGACY_PX), (0, 0, 0, 0))
    draw = ImageDraw.Draw(leg)
    # tile gradient (vertical TILE_HI -> TILE_LO)
    t_hi = [int(TILE_HI[i:i + 2], 16) for i in (1, 3, 5)]
    t_lo = [int(TILE_LO[i:i + 2], 16) for i in (1, 3, 5)]
    for y in range(LEGACY_PX):
        t = y / LEGACY_PX
        draw.line([(0, y), (LEGACY_PX, y)],
                  fill=tuple(round(a + (b - a) * t) for a, b in zip(t_hi, t_lo)))
    tile_mask = Image.new("L", (LEGACY_PX, LEGACY_PX), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(
        [10.4, 9.5, 10.4 + 171.2, 9.5 + 171.2], radius=34, fill=255)
    full = Image.new("RGBA", (LEGACY_PX, LEGACY_PX), (0, 0, 0, 0))
    full.paste(leg, (0, 0), tile_mask)
    draw = ImageDraw.Draw(full)
    draw.rounded_rectangle([10.4, 9.5, 10.4 + 171.2, 9.5 + 171.2], radius=34,
                           outline=TILE_STROKE, width=2)
    icon_px = round(LEGACY_SCALE * 24)
    icon_leg = icon.resize((icon_px, icon_px), Image.Resampling.LANCZOS)
    off = round(LEGACY_OFF)
    full.paste(icon_leg, (off, off - 4), icon_leg)
    draw.rounded_rectangle([76, 156, 116, 162], radius=3, fill=pal["accent"])
    full.save(out_res / "drawable-xxxhdpi" / f"{name}.webp", quality=92)


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

    # ---- device sync extras (apps on the phone with no DB coverage) ----
    # glyph entries flow through the normal pipeline; src=="recolor" entries
    # are rendered from extracted-icon masters after the main render pass.
    device_mf = TOOLS / "device_manifest.json"
    if device_mf.exists():
        for name, v in json.loads(device_mf.read_text()).items():
            if v["source"] == "glyph":
                drawables[name] = (v["glyph_src"], v["glyph_name"], v["components"])
            else:
                drawables[name] = ("recolor", name, v["components"])
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
        if src == "recolor":
            continue  # rendered after the pool pass from PNG masters
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

    # ---- recolor pass (device-sync extracted icons) ----
    n_recolor = 0
    for name, (src, _, _) in drawables.items():
        if src != "recolor":
            continue
        master = TOOLS / "device_icons" / f"{name}.png"
        if master.exists():
            render_recolor(master, out_res, name, pal)
            n_recolor += 1
        else:
            print(f"  WARNING: no master for recolor drawable {name}")
    if n_recolor:
        print(f"recolored {n_recolor} device icons into {args.variant} livery")

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
