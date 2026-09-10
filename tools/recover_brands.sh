#!/usr/bin/env bash
# Recover brands that simple-icons removed in later releases (trademark purges).
# All versions are CC0. Tries newest-first so we get the freshest available glyph.
set -uo pipefail
cd "$(dirname "$0")"
OUT=lib/simple/icons
VERSIONS="14.13.0 12.4.0 10.4.0 8.15.0 6.23.0 4.25.0"

BRANDS="adobeacrobatreader adobelightroom adobephotoshop amazonalexa anydo authy
brawlstars briar calm canva chromecast clashofclans clashroyale costco dayone depop
disneyplus dominos draftkings espn eventbrite fanduel flashscore fotmob genshinimpact
googleduo googlefit googlehangouts googleone googlewallet grubhub hulu icedrive iheart
insighttimer kindle kraken libby linkedin mercari microsoft microsoftedge microsoftexcel
microsoftoffice microsoftonedrive microsoftonenote microsoftoutlook microsoftpowerpoint
microsoftteams microsoftword myfitnesspal nest nintendo nintendoswitch offerup olx
onefootball openai pcloud peacock pizzahut plutotv pocket pokemongo poshmark primevideo
resiliosync samsunginternet shein siriusxm skype slack snapseed sofascore teamspeak3
temu tenor termux thescore tunein visualstudiocode walmart whereby winrar wps xbox
zedge santander flipkart twint orbot angrybirds rockstargames bhim caixa blinkit
telegramx session element threema viber line kakaotalk wechat guilded mumble
ventrilo teamspeak viber signal whatsapp messenger facebookmessenger"

ok=0; fail=0; failed=""
for b in $BRANDS; do
  [ -f "$OUT/$b.svg" ] && { ok=$((ok+1)); continue; }
  got=""
  for v in $VERSIONS; do
    if curl -sfL "https://cdn.jsdelivr.net/npm/simple-icons@$v/icons/$b.svg" -o "$OUT/$b.svg" 2>/dev/null; then
      got="$v"; break
    fi
    rm -f "$OUT/$b.svg"
  done
  if [ -n "$got" ]; then ok=$((ok+1)); echo "  + $b (v$got)"; else fail=$((fail+1)); failed="$failed $b"; fi
done
echo "recovered/present: $ok, not found:$fail"
[ -n "$failed" ] && echo "not found:$failed"
exit 0
