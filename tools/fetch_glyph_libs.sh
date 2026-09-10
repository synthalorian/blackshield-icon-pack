#!/usr/bin/env bash
# Fetch glyph libraries + coverage data into tools/lib/ (gitignored).
#   material/  Material icons (Apache-2.0)  — npm @material-design-icons/svg
#   simple/    Simple Icons brand glyphs (CC0) — npm simple-icons
#              (+ amazon/minecraft from v9.21.0, removed in later releases)
#   arcticons_appfilter.xml — component coverage facts from Arcticons
set -euo pipefail
cd "$(dirname "$0")"
LIB=lib
rm -rf "$LIB"
mkdir -p "$LIB/material" "$LIB/simple"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"
npm pack --silent @material-design-icons/svg simple-icons@16.30.0 >/dev/null
tar xzf material-design-icons-svg-*.tgz
mv package/filled "$OLDPWD/$LIB/material/filled"
mv package/LICENSE "$OLDPWD/$LIB/material/LICENSE" 2>/dev/null || true
tar xzf simple-icons-*.tgz
mv package/icons "$OLDPWD/$LIB/simple/icons"
mv package/LICENSE.md "$OLDPWD/$LIB/simple/LICENSE.md"
cd "$OLDPWD"

# Brands removed from newer simple-icons releases (trademark), still CC0
for i in amazon minecraft; do
  curl -sfL "https://cdn.jsdelivr.net/npm/simple-icons@9.21.0/icons/$i.svg" \
    -o "$LIB/simple/icons/$i.svg"
done

curl -sfL "https://raw.githubusercontent.com/Arcticons-Team/Arcticons/main/app/src/main/assets/appfilter.xml" \
  -o "$LIB/arcticons_appfilter.xml"

echo "lib ready: $(ls "$LIB/material/filled" | wc -l) material, $(ls "$LIB/simple/icons" | wc -l) simple"
