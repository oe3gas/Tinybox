#!/usr/bin/env bash
# Build the Windows release package (ZIP) for other stations.
#   release/build_release.sh <direwolf-tinybox.exe> [branch]
#     -> release-out/TinyBox-<RELEASE>-<short-hash>.zip
# The package holds a shallow git clone of GitHub (branch main by default), reduced
# by release/sparse-checkout.txt (no GeoSphere, no DX cluster feed, no tests/docs
# for development), plus the Direwolf fork and install.bat. Because the .git data
# is inside, the installation updates itself later with "git pull" (start menu).
# It is built from GitHub, not from the working tree: push first.
# Details: INSTALL.md (section "Paket bauen")
set -euo pipefail

DW=${1:?usage: release/build_release.sh <direwolf-tinybox.exe> [branch]}
BRANCH=${2:-main}
URL=${TINYBOX_URL:-https://github.com/oe3gas/Tinybox.git}   # TINYBOX_URL: other source, e.g. for a test
HERE=$(cd "$(dirname "$0")/.." && pwd)
[ -f "$DW" ] || { echo "Direwolf exe not found: $DW" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git clone -q --depth 1 --no-checkout --branch "$BRANCH" "$URL" "$tmp/payload"
git -C "$tmp/payload" sparse-checkout set --no-cone --stdin < "$HERE/release/sparse-checkout.txt"
git -C "$tmp/payload" checkout -q "$BRANCH"

P="$tmp/payload"
SHORT=$(git -C "$P" rev-parse --short HEAD)
RELEASE=$(sed -n 's/^RELEASE = "\(.*\)"/\1/p' "$P/prcore/release.py")
NAME="TinyBox-$RELEASE-$SHORT"
STAGE="$tmp/$NAME"
mkdir -p "$STAGE/direwolf"
mv "$P" "$STAGE/payload"
cp "$DW" "$STAGE/direwolf/direwolf-tinybox.exe"
cp "$STAGE/payload/release/install.bat" "$STAGE/install.bat"

# must be there - a release without them would not run
for f in tbclient/__main__.py tinybox/__main__.py brocast/brocast/daemon.py \
         release/konfig.py release/start.ps1 TinyBox-Start.bat; do
    [ -f "$STAGE/payload/$f" ] || { echo "ERROR: $f missing in the package" >&2; exit 1; }
done
# must not be there
if ls "$STAGE/payload" | grep -qiE '^(geosphere_|dxfeed)'; then
    echo "ERROR: GeoSphere/dxfeed files in the package - check sparse-checkout.txt" >&2; exit 1
fi

cat > "$STAGE/VERSION.txt" <<EOF
TinyBox Release $RELEASE, Stand $SHORT ($(git -C "$STAGE/payload" show -s --format=%cs HEAD))
Client $(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$STAGE/payload/tbclient/__init__.py"), Direwolf-Fork $(date -r "$DW" +%Y-%m-%d)
Gebaut $(date -Iseconds)
EOF
printf '%s\r\n' \
  "TinyBox - Installation unter Windows 10/11" "" \
  "1. Diese ZIP-Datei ganz entpacken (Rechtsklick - Alle extrahieren)." \
  "2. Im entpackten Ordner install.bat doppelklicken." \
  "3. Fragen beantworten (Ordner, Rufzeichen, Direwolf ...)." \
  "4. Starten mit TinyBox-Start.bat im Installationsordner oder der Desktop-Verknuepfung." "" \
  "Git und Python werden bei Bedarf automatisch installiert (winget)." \
  "Updates holt das Startmenue bei jedem Start selbst von GitHub (git pull)." \
  "Anleitung: INSTALL.md und MANUAL.md im Installationsordner." > "$STAGE/LIESMICH.txt"

mkdir -p "$HERE/release-out"
OUT="$HERE/release-out/$NAME.zip"
rm -f "$OUT"
(cd "$tmp" && python3 -m zipfile -c "$OUT" "$NAME")
echo "Built $OUT ($(du -h "$OUT" | cut -f1), $(find "$STAGE" -type f -not -path '*/.git/*' | wc -l) files + git data)"
