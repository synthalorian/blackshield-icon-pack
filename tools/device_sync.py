#!/usr/bin/env python3
"""Device coverage sync — make the pack cover EVERY app on the connected phone.

1. Enumerate launchable components via adb.
2. Diff against generated appfilter coverage.
3. For uncovered apps, in preference order:
   a. MANUAL glyph override (curated below — synth's own apps get proper glyphs)
   b. label -> glyph via the match_icons.py matcher (confident tiers only)
   c. RECOLOR the app's real icon into the livery (androguard extraction,
      luminance ramp applied at forge time per variant)
4. Writes tools/device_manifest.json + tools/device_icons/*.png masters.

Run with the tools venv:  tools/.venv/bin/python tools/device_sync.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
ICONS = TOOLS / "device_icons"
APKS = ICONS / "apks"
ADB = str(Path.home() / "opt" / "platform-tools" / "adb")

sys.path.insert(0, str(TOOLS))
import match_icons  # noqa: E402

try:
    from loguru import logger
    logger.remove()  # silence androguard debug spam
except Exception:
    pass

# Curated glyphs for known apps (synth's own fleet etc.). component pkg ->
# (glyph_src, glyph_name) — flows through the normal forge like any icon.
MANUAL_DEVICE = {
    "ai.openclaw.app": ("material", "smart_toy"),
    "app.openbible": ("material", "menu_book"),
    "com.example.hermes_wingman": ("material", "support_agent"),
    "com.moonshot.kimiclaw": ("material", "smart_toy"),
    "com.nikhil.yt": ("simple", "youtube"),
    "com.openamp": ("material", "graphic_eq"),
    "com.openshield.armory": ("material", "shield"),
    "com.synth.vhscam": ("material", "videocam"),
    "com.synth.voidshmup": ("material", "rocket_launch"),
    "com.synthalorian.sc_synthesis": ("simple", "starcitizen"),
    "com.blackclaw.blackshieldicons": ("material", "shield"),
    "com.blackclaw.blackshieldicons.red": ("material", "shield"),
    "com.synthshark.flamingo": ("material", "photo_camera"),
}


def adb(*args: str) -> str:
    return subprocess.run([ADB, *args], capture_output=True, text=True).stdout


def device_components() -> dict[str, list[str]]:
    """pkg -> [full component strings]."""
    out = adb("shell", "cmd package query-activities --brief "
              "-a android.intent.action.MAIN -c android.intent.category.LAUNCHER")
    comps = {}
    for line in out.splitlines():
        m = re.match(r"\s+([a-zA-Z0-9_.]+)/([a-zA-Z0-9_.$]+)\s*$", line)
        if not m:
            continue
        pkg, cls = m.group(1), m.group(2)
        if cls.startswith("."):
            cls = pkg + cls
        elif "." not in cls:
            cls = pkg + "." + cls
        comps.setdefault(pkg, []).append(f"{pkg}/{cls}")
    return comps


def covered_components() -> set[str]:
    af = (ROOT / "app/src/main/res/xml/appfilter.xml").read_text()
    return set(re.findall(r"ComponentInfo\{([^}]+)\}", af))


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def pull_icon(pkg: str, dest: Path) -> Path | None:
    """Pull the app APK and extract the best launcher icon raster."""
    import androguard.core.apk as andro
    out = adb("shell", "pm", "path", pkg)
    m = re.search(r"package:(\S*base\.apk)", out)
    if not m:
        m = re.search(r"package:(\S+\.apk)", out)
    if not m:
        return None
    apk_path = APKS / f"{pkg}.apk"
    subprocess.run([ADB, "pull", m.group(1), str(apk_path)], capture_output=True)
    try:
        a = andro.APK(str(apk_path))
        label = a.get_app_name()
    except Exception:
        return None
    # get_app_icon resolves the best-density raster; may be None for
    # adaptive-only XML icons
    try:
        icon_res = a.get_app_icon()
    except Exception:
        icon_res = None
    if icon_res:
        try:
            data = a.get_file(icon_res)
            dest.write_bytes(data)
            return dest
        except Exception:
            pass
    print(f"  {pkg}: no raster icon (adaptive/vector XML), label={label!r}")
    return None


def main() -> int:
    ICONS.mkdir(parents=True, exist_ok=True)
    APKS.mkdir(parents=True, exist_ok=True)

    comps = device_components()
    covered = covered_components()
    manifest = {}
    if (TOOLS / "device_manifest.json").exists():
        manifest = json.loads((TOOLS / "device_manifest.json").read_text())
    existing_components = {c for v in manifest.values() for c in v["components"]}

    new = 0
    for pkg, cl in sorted(comps.items()):
        uncovered = [c for c in cl if c not in covered and c not in existing_components]
        if not uncovered:
            continue
        name = "ic_dev_" + slugify(pkg)
        if pkg in MANUAL_DEVICE:
            src, gname = MANUAL_DEVICE[pkg]
            # verify glyph exists
            lib = match_icons.simple if src == "simple" else match_icons.material
            if gname in lib:
                manifest[name] = {"source": "glyph", "glyph_src": src,
                                  "glyph_name": gname, "components": uncovered}
                print(f"  glyph {src}/{gname} <- {pkg}")
                new += 1
                continue
        # recolor fallback: pull the real icon
        dest = ICONS / f"{name}.png"
        if pull_icon(pkg, dest):
            manifest[name] = {"source": "recolor", "components": uncovered}
            print(f"  recolor <- {pkg}")
            new += 1
        else:
            print(f"  FAILED <- {pkg} (letter tile remains the fallback)")

    (TOOLS / "device_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"\ndevice coverage: {len(manifest)} extra drawables ({new} new this run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
