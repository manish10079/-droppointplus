#!/usr/bin/env bash
# Build a DropPoint+ AppImage from the PyInstaller onedir output.
#
# Prereqs: dist/DropPointPlus/ exists (from `pyinstaller --noconfirm
# DropPointPlus.spec`), and `appimagetool` is on PATH or set via
# APPIMAGETOOL. Downloads it if missing.
#
# Usage:  ./packaging/linux/build_appimage.sh
# Output: dist/DropPointPlus-x86_64.AppImage
set -euo pipefail

cd "$(dirname "$0")/../.."   # project root

APP_NAME="DropPoint+"
# The AppImage filename must match the workflow's upload glob
# (dist/DropPointPlus-x86_64.AppImage).
APPIMAGE_NAME="DropPointPlus-x86_64.AppImage"
BUNDLE="dist/DropPointPlus"
APPDIR="dist/AppDir"
APPIMAGE_TOOL="${APPIMAGETOOL:-}"

if [[ ! -x "$BUNDLE/DropPointPlus" ]]; then
    echo "error: $BUNDLE/DropPointPlus not found — run 'pyinstaller --noconfirm DropPointPlus.spec' first" >&2
    exit 1
fi

# --- AppDir skeleton ---------------------------------------------------------
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib/droppointplus"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/128x128/apps"

# Copy the PyInstaller bundle: the launcher expects _internal/ next to it.
cp -r "$BUNDLE/_internal" "$APPDIR/usr/lib/droppointplus/"
cp "$BUNDLE/DropPointPlus" "$APPDIR/usr/lib/droppointplus/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
SELF="$(dirname "$(readlink -f "$0")")"
exec "$SELF/usr/lib/droppointplus/DropPointPlus" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Desktop entry + icon (from the bundled resources).
cp packaging/linux/droppointplus.desktop "$APPDIR/usr/share/applications/"
cp droppointplus/resources/icons/pngLogo/droppoint.png \
    "$APPDIR/usr/share/icons/hicolor/128x128/apps/droppoint.png"
# AppImage also looks for the .desktop and icon in the AppDir root.
cp packaging/linux/droppointplus.desktop "$APPDIR/"
cp droppointplus/resources/icons/pngLogo/droppoint.png "$APPDIR/"

# --- appimagetool ------------------------------------------------------------
if [[ -z "$APPIMAGE_TOOL" || ! -x "$APPIMAGE_TOOL" ]]; then
    echo "downloading appimagetool..."
    curl -L -o dist/appimagetool \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x dist/appimagetool
    APPIMAGE_TOOL="dist/appimagetool"
fi

# appimagetool is itself an AppImage; GitHub Actions runners (and other
# containers) have no FUSE, so run it in extract-and-run mode.
export APPIMAGE_EXTRACT_AND_RUN=1

ARCH=x86_64 "$APPIMAGE_TOOL" "$APPDIR" "dist/${APPIMAGE_NAME}"
echo "done: dist/${APPIMAGE_NAME}"
