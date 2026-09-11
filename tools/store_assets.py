#!/usr/bin/env python3
"""Blackshield store assets — Play listing art, generated from canon vectors.

Outputs to store-assets/<livery>/:
  - icon-512.png          Play hi-res app icon (512x512 PNG)
  - feature-1024x500.png  Play feature graphic
  - shot-1.png, shot-2.png  phone screenshots (1080x2400) — icon grid promos

Run: tools/.venv/bin/python tools/store_assets.py
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forge_icons import PALETTES, svg_launcher, TILE_HI, TILE_LO, BONE_HI, BONE_LO, BLOOD

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "store-assets"
BUILD = ROOT / "build" / "store-svg"
DRAWABLES = ROOT / "app" / "src" / "main" / "res" / "drawable-xxxhdpi"

FONT_BOLD = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/TTF/DejaVuSans.ttf"

# Recognizable faces for the promo grids (must exist as drawables).
GRID_A = ["ic_discord", "ic_spotify", "ic_youtube", "ic_github", "ic_steam",
          "ic_torbrowser", "ic_signal", "ic_jellyfin", "ic_kodi", "ic_twitch",
          "ic_whatsapp", "ic_google_mail", "ic_maps", "ic_google_chrome", "ic_minecraft",
          "ic_netflix", "ic_plex", "ic_bitwarden", "ic_obsidian", "ic_vlc"]
GRID_B = ["ic_camera", "ic_messages", "ic_phone", "ic_google_photos", "ic_google_files",
          "ic_settings", "ic_calculator", "ic_clock", "ic_calendar_31", "ic_music",
          "ic_notes", "ic_accuweather", "ic_mail", "ic_gallery", "ic_wallet",
          "ic_contacts", "ic_recorder", "ic_1password", "ic_2048", "ic_1money"]


def render_png(svg_text: str, px: int, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    svg = BUILD / (out.stem + ".svg")
    svg.write_text(svg_text)
    subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px),
                    str(svg), "-o", str(out)], check=True)


def vgrad(size, top, bottom) -> Image.Image:
    w, h = size
    im = Image.new("RGB", size)
    t = tuple(int(top[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(bottom[i:i + 2], 16) for i in (1, 3, 5))
    px = im.load()
    for y in range(h):
        f = y / max(h - 1, 1)
        row = tuple(round(t[c] + (b[c] - t[c]) * f) for c in range(3))
        for x in range(w):
            px[x, y] = row
    return im


def load_icon(name: str, px: int) -> Image.Image | None:
    p = DRAWABLES / f"{name}.webp"
    if not p.exists():
        return None
    return Image.open(p).convert("RGBA").resize((px, px), Image.LANCZOS)


def hi_res_icon(livery: str, pal: dict) -> None:
    render_png(svg_launcher(pal, legacy=True), 512, OUT / livery / "icon-512.png")


def fit_font(text: str, max_w: int, start: int) -> ImageFont.FreeTypeFont:
    size = start
    while size > 12:
        f = ImageFont.truetype(FONT_BOLD, size)
        if f.getbbox(text)[2] <= max_w:
            return f
        size -= 2
    return ImageFont.truetype(FONT_BOLD, 12)


def feature_graphic(livery: str, pal: dict) -> None:
    W, H = 1024, 500
    im = vgrad((W, H), TILE_HI, TILE_LO).convert("RGBA")
    # blood accent bar, bottom
    d = ImageDraw.Draw(im)
    d.rectangle([0, H - 12, W, H], fill=pal["accent"])
    # launcher icon, centered left third
    icon_png = OUT / livery / "icon-512.png"
    icon = Image.open(icon_png).convert("RGBA").resize((340, 340), Image.LANCZOS)
    im.alpha_composite(icon, (70, (H - 340) // 2 - 6))
    # wordmark (auto-fit to remaining width)
    tx, max_w = 450, W - 450 - 30
    name = "BLACKSHIELD RED" if livery == "red" else "BLACKSHIELD"
    f_big = fit_font(name, max_w, 96)
    f_small = fit_font("ICONS", max_w, 34)
    tag = "dark steel  ·  bone glyphs  ·  one blood accent"
    f_tag = fit_font(tag, max_w, 26)
    d.text((tx, 140), name, font=f_big, fill=BONE_HI)
    d.text((tx + 2, 140 + f_big.size + 20), "ICONS", font=f_small, fill=pal["accent"])
    d.text((tx + 2, 140 + f_big.size + 20 + f_small.size + 18), tag, font=f_tag, fill=BONE_LO)
    im.convert("RGB").save(OUT / livery / "feature-1024x500.png")


def screenshot(livery: str, pal: dict, grid: list[str], fname: str, title: str) -> None:
    W, H = 1080, 2400
    im = vgrad((W, H), "#0B0B0F", "#14141B").convert("RGBA")
    d = ImageDraw.Draw(im)
    # header: wordmark + accent dash
    f_word = ImageFont.truetype(FONT_BOLD, 64)
    f_sub = ImageFont.truetype(FONT_REG, 30)
    d.text((70, 150), "BLACKSHIELD", font=f_word, fill=BONE_HI)
    d.rectangle([70, 240, 210, 248], fill=pal["accent"])
    d.text((70, 270), title, font=f_sub, fill=BONE_LO)
    # grid: 4 cols, icon 180px
    cols, cell, ipx = 4, 240, 180
    x0 = (W - cols * cell) // 2 + (cell - ipx) // 2
    y0 = 420
    placed = 0
    for name in grid:
        icon = load_icon(name, ipx)
        if icon is None:
            print(f"  !! missing {name}, skipping")
            continue
        r, c = divmod(placed, cols)
        x = x0 + c * cell
        y = y0 + r * cell
        im.alpha_composite(icon, (x, y))
        placed += 1
    im.convert("RGB").save(OUT / livery / fname, quality=95)
    print(f"  {livery}/{fname}: {placed} icons placed")


def main() -> None:
    for livery, pal in PALETTES.items():
        print(f"livery: {livery}")
        hi_res_icon(livery, pal)
        feature_graphic(livery, pal)
        screenshot(livery, pal, GRID_A, "shot-1.png", "your apps, in bone and steel")
        screenshot(livery, pal, GRID_B, "shot-2.png", "every icon, one language")
    print("done -> store-assets/")


if __name__ == "__main__":
    main()
