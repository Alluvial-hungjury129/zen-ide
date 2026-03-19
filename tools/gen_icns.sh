#!/bin/bash
# Generate macOS .icns file from zen_icon.png
set -e
[ ! -f zen_icon.png ] && echo "zen_icon.png not found" && exit 1

echo "🎨 Generating app icon..."
mkdir -p zen_icon.iconset
for size in 16 32 64 128 256 512; do
    sips -z $size $size zen_icon.png --out zen_icon.iconset/icon_${size}x${size}.png 2>/dev/null
done
# Retina variants
sips -z 32 32 zen_icon.png --out zen_icon.iconset/icon_16x16@2x.png 2>/dev/null
sips -z 64 64 zen_icon.png --out zen_icon.iconset/icon_32x32@2x.png 2>/dev/null
sips -z 256 256 zen_icon.png --out zen_icon.iconset/icon_128x128@2x.png 2>/dev/null
sips -z 512 512 zen_icon.png --out zen_icon.iconset/icon_256x256@2x.png 2>/dev/null
cp zen_icon.png zen_icon.iconset/icon_512x512@2x.png
iconutil -c icns zen_icon.iconset
rm -rf zen_icon.iconset
echo "✅ Generated zen_icon.icns"
