#!/bin/bash
# Installerer eller opdaterer Transskriber.
#
#   Første gang:   bash install.sh        (kør inde fra den udpakkede mappe)
#   Opdateringer:  køres normalt af appen selv, når der er en ny release på GitHub.
#
# Kræver internet under installationen. Bagefter virker appen offline.

set -e

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for f in VERSION config.env requirements.txt app/transskriber.py assets/icon1024.png \
         scripts/afinstaller.sh scripts/opdater.sh; do
  if [ ! -f "$SRC/$f" ]; then
    echo "Filen '$f' mangler. Kør 'bash install.sh' inde fra den udpakkede mappe."
    exit 1
  fi
done

# shellcheck disable=SC1091
. "$SRC/config.env"
MODEL="${MODEL:-mlx-community/whisper-large-v3-turbo}"
VERSION="${TRANSSKRIBER_VERSION:-$(tr -d '[:space:]' < "$SRC/VERSION")}"
UPDATING="${TRANSSKRIBER_UPDATE:-0}"

BASE="$HOME/Library/Application Support/Transskriber"
APP_DIR="$HOME/Applications"
APP="$APP_DIR/Transskriber.app"

if [ "$(uname -m)" != "arm64" ]; then
  echo "Denne app kræver en Mac med Apple-chip (M1 eller nyere)."
  exit 1
fi

# Må ikke køres med sudo: så ejer root filerne, og appen kan hverken køre eller opdatere sig selv
if [ "$(id -u)" -eq 0 ]; then
  echo "Kør install.sh uden 'sudo', altså bare:  bash install.sh"
  exit 1
fi

# En tidligere installation med sudo kan have efterladt mapper, som ejes af root
HF_DIR="${HF_HOME:-$HOME/.cache/huggingface}"
BAD=()
for p in "$BASE" "$APP" "$HF_DIR"; do
  if [ -e "$p" ] && [ -n "$(find "$p" ! -user "$(id -u)" -print -quit 2>/dev/null)" ]; then
    BAD+=("$p")
  fi
done
if [ -e "$APP_DIR" ] && [ ! -w "$APP_DIR" ]; then
  BAD+=("$APP_DIR")
fi
if [ ${#BAD[@]} -gt 0 ]; then
  echo "Nogle mapper ejes ikke af dig, sandsynligvis fordi en tidligere installation blev kørt med sudo:"
  for p in "${BAD[@]}"; do echo "  - $p"; done
  echo ""
  echo "Ret det ved at køre denne kommando i Terminal (den spørger efter din adgangskode):"
  echo ""
  printf '  sudo chown -R "%s":staff' "$USER"
  for p in "${BAD[@]}"; do printf ' "%s"' "$p"; done
  echo ""
  echo ""
  echo "Kør derefter 'bash install.sh' igen."
  exit 1
fi

echo "==> 1/6 Forbereder mapper (version $VERSION)"
mkdir -p "$BASE/bin" "$APP_DIR"

echo "==> 2/6 Henter Python-værktøjet 'uv' (hvis det mangler)"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> 3/6 Installerer Python og transskriberingsmotoren"
uv venv --python 3.12 --allow-existing "$BASE/venv"
uv pip install --python "$BASE/venv/bin/python" -r "$SRC/requirements.txt"

# ffmpeg uden Homebrew: imageio-ffmpeg medbringer en ffmpeg-binær
FFMPEG="$("$BASE/venv/bin/python" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
ln -sf "$FFMPEG" "$BASE/bin/ffmpeg"

echo "==> 4/6 Sikrer at sprogmodellen er hentet (ca. 1,5 GB første gang)"
"$BASE/venv/bin/python" -c "from huggingface_hub import snapshot_download; snapshot_download('$MODEL')"

echo "==> 5/6 Laver ikon"
cp "$SRC/assets/icon1024.png" "$BASE/icon1024.png"
sips -z 512 512 "$BASE/icon1024.png" --out "$BASE/icon512.png" >/dev/null
ICONSET="$BASE/AppIcon.iconset"
rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z $size $size "$BASE/icon1024.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z $double $double "$BASE/icon1024.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$BASE/AppIcon.icns"
rm -rf "$ICONSET"

echo "==> 6/6 Installerer programmet"
# Filerne kopieres først nu, så en mislykket opdatering ovenfor efterlader den gamle version intakt
cp "$SRC/app/transskriber.py" "$BASE/transskriber.py"
cp "$SRC/config.env" "$BASE/config.env"
cp "$SRC/requirements.txt" "$BASE/requirements.txt"
cp "$SRC/scripts/afinstaller.sh" "$BASE/Afinstaller.command"
cp "$SRC/scripts/opdater.sh" "$BASE/Opdater.command"
chmod +x "$BASE/Afinstaller.command" "$BASE/Opdater.command"
printf '%s\n' "$VERSION" > "$BASE/version.txt"

# Selve .app-pakken (lavet lokalt, så macOS viser ingen sikkerhedsadvarsel)
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BASE/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Transskriber</string>
  <key>CFBundleDisplayName</key><string>Transskriber</string>
  <key>CFBundleIdentifier</key><string>local.transskriber</string>
  <key>CFBundleExecutable</key><string>Transskriber</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundleDocumentTypes</key>
  <array>
    <dict>
      <key>CFBundleTypeName</key><string>Lyd og video</string>
      <key>CFBundleTypeRole</key><string>Viewer</string>
      <key>LSHandlerRank</key><string>Alternate</string>
      <key>LSItemContentTypes</key>
      <array>
        <string>public.audio</string>
        <string>public.movie</string>
      </array>
    </dict>
  </array>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLISTEOF

cat > "$APP/Contents/MacOS/Transskriber" <<'LAUNCHEOF'
#!/bin/bash
BASE="$HOME/Library/Application Support/Transskriber"
exec "$BASE/venv/bin/python" "$BASE/transskriber.py"
LAUNCHEOF
chmod +x "$APP/Contents/MacOS/Transskriber"
xattr -cr "$APP" 2>/dev/null || true
# Fortæl macOS om appens filtyper, så filer kan slippes på ikonet
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP" >/dev/null 2>&1 || true
touch "$APP"

echo ""
echo "Færdig! Transskriber $VERSION ligger i: $APP"
if [ "$UPDATING" != "1" ]; then
  echo "Tip: træk det ned i Dock'en, så det er nemt at finde. Man kan også trække lydfiler ind i vinduet eller hen på ikonet."
  echo ""
  echo "Opdatere motoren senere:  bash \"$BASE/Opdater.command\""
  echo "Fjerne alt igen:          bash \"$BASE/Afinstaller.command\""
  open "$APP_DIR"
fi
