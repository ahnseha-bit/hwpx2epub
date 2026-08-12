#!/bin/zsh
set -euo pipefail

ROOT_DIR="${0:A:h}"
APP_NAME="HWPX 전자책 변환기.app"
APP_DIR="$ROOT_DIR/dist/$APP_NAME"
VENV_DIR="$ROOT_DIR/.build-venv"

if [[ ! -x "$VENV_DIR/bin/pyinstaller" ]]; then
    /usr/bin/python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install "pyinstaller<7" "EbookLib>=0.18,<1.0" "chardet>=5.2,<6" "Pillow>=10,<12"
fi

if ! "$VENV_DIR/bin/python" -c "import PIL" 2>/dev/null; then
    "$VENV_DIR/bin/pip" install "Pillow>=10,<12"
fi

# Always regenerate the macOS icon from the canonical PNG so every build uses
# the same artwork in Finder, Dock, and the distributed ZIP.
"$VENV_DIR/bin/python" -c \
    'import sys; from PIL import Image; Image.open(sys.argv[1]).convert("RGBA").save(sys.argv[2], format="ICNS")' \
    "$ROOT_DIR/assets/app-icon-v1.png" "$ROOT_DIR/assets/AppIcon.icns"

"$VENV_DIR/bin/pyinstaller" \
    --noconfirm --clean --onefile \
    --name epub_engine \
    --paths "$ROOT_DIR/engine" \
    --distpath "$ROOT_DIR/dist" \
    --workpath "$ROOT_DIR/build/engine" \
    --specpath "$ROOT_DIR/build" \
    "$ROOT_DIR/engine/main.py"

xcrun --sdk macosx swiftc \
    -target arm64-apple-macosx11.0 \
    "$ROOT_DIR/macos/main.swift" \
    -o "$ROOT_DIR/dist/HWPXEPUBMaker" \
    -framework AppKit -framework Foundation

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp "$ROOT_DIR/dist/HWPXEPUBMaker" "$APP_DIR/Contents/MacOS/HWPXEPUBMaker"
cp "$ROOT_DIR/dist/epub_engine" "$APP_DIR/Contents/Resources/epub_engine"
cp "$ROOT_DIR/assets/AppIcon.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
cp "$ROOT_DIR/macos/Info.plist" "$APP_DIR/Contents/Info.plist"
cp "$ROOT_DIR/THIRD_PARTY_NOTICES.txt" "$APP_DIR/Contents/Resources/THIRD_PARTY_NOTICES.txt"
mkdir -p "$APP_DIR/Contents/Resources/Licenses" "$APP_DIR/Contents/Resources/Source"
cp -R "$ROOT_DIR/licenses/." "$APP_DIR/Contents/Resources/Licenses/"
cp -R "$ROOT_DIR/engine" "$APP_DIR/Contents/Resources/Source/engine"
cp -R "$ROOT_DIR/macos" "$APP_DIR/Contents/Resources/Source/macos"
cp "$ROOT_DIR/build_app.sh" "$APP_DIR/Contents/Resources/Source/build_app.sh"
cp "$ROOT_DIR/README.md" "$APP_DIR/Contents/Resources/Source/README.md"
chmod +x "$APP_DIR/Contents/MacOS/HWPXEPUBMaker" "$APP_DIR/Contents/Resources/epub_engine"
codesign --force --deep --sign - "$APP_DIR"
echo "$APP_DIR"
