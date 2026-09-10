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
- `res/drawable-{mdpi..xxxhdpi}/ic_*.png` — legacy density icons (48–192 px)
- `res/drawable-anydpi-v26/ic_*.xml` — adaptive-icon wrappers (API 26+)
- `assets/appfilter.xml` — copy for older launchers that read assets

## Forging icons

```bash
python3 tools/forge_icons.py
```

Renders every SVG in `icons-src/` (canon: dark steel tile gradient
`#1E1E26→#101014`, `#2A2A31` hairline, bone-gradient glyph, one `#C1121F`
accent) to PNGs at mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi (48–192 px), plus `_fg`
foregrounds referenced by the adaptive XMLs. Master SVGs live in `icons-src/`.

## Building

```bash
./gradlew assembleDebug        # debug APK (debug-signed, sideloadable)
./gradlew assembleRelease      # unsigned release APK
```

Debug APK lands at `app/build/outputs/apk/debug/app-debug.apk`.

## Starter set (10 icons)

browser · mail · phone · messages · camera · gallery · music · calendar ·
settings · calculator — each mapped to the common Google/AOSP/OEM components
in `appfilter.xml`.

## Ship checklist (Play, $0.99–1.99)

- [ ] Grow the pack to ~1,500+ icons (Play buyers expect coverage; use
      `tools/forge_icons.py` + request-driven appfilter entries)
- [ ] Release signing key (Play App Signing) + `assembleRelease`
- [ ] 512px store icon + feature graphic (1024×500) + screenshots
- [ ] Privacy policy URL (trivial: pack collects nothing, but Play requires one)
- [ ] Content rating questionnaire
- [ ] Optional: dashboard app (Blueprint/CandyBar) for icon requests & apply flow
- [ ] Set price in Play Console ($0.99 intro)
