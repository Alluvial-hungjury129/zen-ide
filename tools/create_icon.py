#!/usr/bin/env python3
"""
Create a minimal icon for Zen IDE
This creates a PNG that can be converted to .icns format
"""

from PIL import Image, ImageDraw

# Create a 1024x1024 image (standard icon size)
size = 1024
img = Image.new("RGBA", (size, size), color=(0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Dark background with rounded corners
background_color = (30, 30, 30, 255)  # #1e1e1e
padding = 100
corner_radius = 150


# Draw rounded rectangle background
def draw_rounded_rectangle(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
    draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
    draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
    draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)


draw_rounded_rectangle(
    draw,
    [padding, padding, size - padding, size - padding],
    corner_radius,
    background_color,
)

# Draw minimal geometric design - a clean square bracket representing code structure
line_color = (212, 212, 212, 255)  # #d4d4d4
line_width = 50
bracket_size = 450

center_x = size // 2
center_y = size // 2

# Left bracket
x_left = center_x - bracket_size // 2
y_top = center_y - bracket_size // 2
y_bottom = center_y + bracket_size // 2

# Vertical line
draw.rectangle([x_left, y_top, x_left + line_width, y_bottom], fill=line_color)
# Top horizontal
draw.rectangle([x_left, y_top, x_left + bracket_size // 3, y_top + line_width], fill=line_color)
# Bottom horizontal
draw.rectangle(
    [x_left, y_bottom - line_width, x_left + bracket_size // 3, y_bottom],
    fill=line_color,
)

# Right bracket (mirrored)
x_right = center_x + bracket_size // 2
# Vertical line
draw.rectangle([x_right - line_width, y_top, x_right, y_bottom], fill=line_color)
# Top horizontal
draw.rectangle([x_right - bracket_size // 3, y_top, x_right, y_top + line_width], fill=line_color)
# Bottom horizontal
draw.rectangle(
    [x_right - bracket_size // 3, y_bottom - line_width, x_right, y_bottom],
    fill=line_color,
)

# Save the icon
output_path = "zen_icon.png"
img.save(output_path, "PNG")
print(f"✅ Icon created: {output_path}")
print("\nTo convert to .icns for macOS:")
print("1. Create iconset folder: mkdir zen_icon.iconset")
print("2. Create required sizes:")
print(f"   sips -z 16 16 {output_path} --out zen_icon.iconset/icon_16x16.png")
print(f"   sips -z 32 32 {output_path} --out zen_icon.iconset/icon_16x16@2x.png")
print(f"   sips -z 32 32 {output_path} --out zen_icon.iconset/icon_32x32.png")
print(f"   sips -z 64 64 {output_path} --out zen_icon.iconset/icon_32x32@2x.png")
print(f"   sips -z 128 128 {output_path} --out zen_icon.iconset/icon_128x128.png")
print(f"   sips -z 256 256 {output_path} --out zen_icon.iconset/icon_128x128@2x.png")
print(f"   sips -z 256 256 {output_path} --out zen_icon.iconset/icon_256x256.png")
print(f"   sips -z 512 512 {output_path} --out zen_icon.iconset/icon_256x256@2x.png")
print(f"   sips -z 512 512 {output_path} --out zen_icon.iconset/icon_512x512.png")
print(f"   sips -z 1024 1024 {output_path} --out zen_icon.iconset/icon_512x512@2x.png")
print("3. Convert to .icns: iconutil -c icns zen_icon.iconset")
print("4. This creates zen_icon.icns which can be used with py2app")
