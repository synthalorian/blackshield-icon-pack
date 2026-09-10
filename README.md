# Blackshield Icons

Steel + blood icon pack for Android launchers (Nova, Lawnchair, Apex, ADW, Smart, Niagara-via-compat).
Dark Nordzy-style tiles, bone glyphs, one blood accent per icon.

**Made by synth with synthclaw**

## Palette

| Role    | Hex       |
|---------|-----------|
| bg      | `#101014` |
| surface | `#16161C` |
| tile-hi | `#1E1E26` |
| bone    | `#D9D2C5` |
| bone-hi | `#F5F1E8` |
| blood   | `#C1121F` |

## How it works

Icon packs are resource-bundle apps. Launchers discover the pack via the
intent filters in `AndroidManifest.xml`, then read:

- `res/xml/appfilter.xml` — maps `ComponentInfo{package/activity}` → drawable name
- `res/xml/drawable.xml` — index of all icons (picker/preview grid)
- `res/drawable-xxxhdpi/ic_*.webp` — legacy icons (192px, WebP; Android scales down)
- `res/drawable-anydpi-v26/ic_*.xml` — adaptive-icon wrappers (API 26+, incl. monochrome)
- `assets/appfilter.xml` — copy for older launchers that read assets

## The set (v0.2 — 1,008 icons)

**1,008 unique drawables covering 29,430 app components** (4,646 apps from the
coverage database). Glyph sources: Material icons (Apache-2.0) for generic
apps, Simple Icons (CC0) for brands. All icons are steel-tile + bone glyph +
one blood dash, 100% canon palette.

## Pipeline

```bash
tools/fetch_glyph_libs.sh     # download glyph libs + coverage data -> tools/lib/
python3 tools/match_icons.py  # match coverage -> glyphs, writes tools/manifest.json
python3 tools/forge_icons.py  # render webp/adaptive/appfilter/drawable.xml
./gradlew assembleDebug       # APK (~11 MB)
```

Matching tiers: manual curation > exact slug > suffix strip > strict fuzzy >
keyword fallback (long-tail apps get the right *generic* glyph — a weather app
always gets the weather icon). Apps sharing a glyph dedupe onto one drawable.

Icons render once at xxxhdpi as WebP (Android scales down); adaptive icons use
a shared `tile_bg` + per-icon transparent foreground, with `<monochrome>` so
Android 13+ themed icons work out of the box.

## Ship checklist (Play, $0.99–1.99)

- [x] Grow the pack past the ~1,500 coverage gate (29,430 components mapped)
- [ ] Release signing key (Play App Signing) + `assembleRelease`
- [ ] 512px store icon + feature graphic (1024×500) + screenshots
- [ ] Privacy policy URL (trivial: pack collects nothing, but Play requires one)
- [ ] Content rating questionnaire
- [ ] Optional: dashboard app (Blueprint/CandyBar) for icon requests & apply flow
- [ ] Set price in Play Console ($0.99 intro)
