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

## The set (v1.0 — 100% coverage)

**1,189 unique drawables covering all 48,120 app components in the coverage
database — 13,767 apps, 100%.** Glyph sources: Material icons (Apache-2.0)
for generic apps, Simple Icons (CC0, incl. recovered purge brands) for
brands, and forged DejaVu Sans Bold letter tiles (A–Z/0–9) as the universal
fallback — every known app gets a Blackshield icon: branded where we have it,
category-generic where we don't, letter-initial otherwise.

## Pipeline

```bash
tools/fetch_glyph_libs.sh     # download glyph libs + coverage data -> tools/lib/
tools/recover_brands.sh       # recover simple-icons trademark-purge brands (CC0)
python3 tools/match_icons.py  # match coverage -> glyphs, writes tools/manifest.json
python3 tools/forge_icons.py  # render webp/adaptive/appfilter/drawable.xml
./gradlew assembleDebug       # APK (~12 MB)
```

Matching tiers: manual curation > exact slug > suffix strip > strict fuzzy >
brand-substring > letter-square rule > keyword pass > token sweep > letter
tile fallback (100% coverage). Apps sharing a glyph dedupe onto one drawable.

## Launcher support

Nova, Lawnchair (+ Android 13 themed icons via `<monochrome>`), Action
Launcher (via ADW filters), Apex, ADW, Smart, GO, Solo, Atom, Nine, Moto,
LG, OnePlus, Sony, TSF, Projectivy (Android TV), +HOME, V, Zero, Kvaesitso,
Niagara/Hyperion (compat), Turbo.

Icons render once at xxxhdpi as WebP (Android scales down); adaptive icons use
a shared `tile_bg` + per-icon transparent foreground, with `<monochrome>` so
Android 13+ themed icons work out of the box. Apps with no pack coverage get
wrapped by the launcher: their own icon is masked into the steel tile with the
accent dash stamped on top (`iconback`/`iconmask`/`iconupon`/`scale 0.75` in
appfilter.xml) — nothing on the home screen looks out of place.

## Variants (Gradle flavor dimension `livery`)

- **bone** (default) — canon: bone glyphs, blood dash. `assembleBoneDebug`
- **red** — canon swap: blood glyphs, bone dash, own launcher icon + label
  "Blackshield Red", applicationId suffix `.red` (installs alongside bone).
  `python3 tools/forge_icons.py --variant red && ./gradlew assembleRedDebug`

## Ship checklist (Play, $0.99–1.99)

- [x] 100% coverage of the known-app database (48,120 components)
- [ ] Release signing key (Play App Signing) + `assembleRelease`
- [ ] 512px store icon + feature graphic (1024×500) + screenshots
- [ ] Privacy policy URL (trivial: pack collects nothing, but Play requires one)
- [ ] Content rating questionnaire
- [ ] Optional: dashboard app (Blueprint/CandyBar) for icon requests & apply flow
- [ ] Set price in Play Console ($0.99 intro)
