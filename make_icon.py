#!/usr/bin/env python3
"""
Generates WhaleTracker.app/Contents/Resources/AppIcon.icns.

Only needed when the icon should change - the .icns is committed, so a normal
checkout already has it. Requires Pillow:  pip install pillow
"""
import os
import struct

from PIL import Image, ImageDraw

OUT = os.path.join("WhaleTracker.app", "Contents", "Resources", "AppIcon.icns")

BG = (13, 13, 26, 255)
EDGE = (42, 42, 77, 255)
CYAN = (34, 227, 255, 255)
LIME = (157, 255, 60, 255)
VIOLET = (139, 92, 255, 255)

# OSType -> pixel size, covering every slot macOS asks for
SLOTS = [(b"icp4", 16), (b"icp5", 32), (b"ic11", 32), (b"ic12", 64),
         (b"ic07", 128), (b"ic13", 256), (b"ic08", 256), (b"ic14", 512),
         (b"ic09", 512), (b"ic10", 1024)]


def draw(size):
    """The artwork: dark rounded tile, cyan tracking ring, lime bolt."""
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = int(s * 0.22)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius, fill=BG, outline=EDGE,
                        width=max(1, int(s * 0.012)))

    # tracking ring, open at the bottom right like a radar sweep
    pad = s * 0.20
    d.arc([pad, pad, s - pad, s - pad], start=120, end=40,
          fill=CYAN, width=max(1, int(s * 0.045)))
    # a violet tick marking the locked target
    d.arc([pad, pad, s - pad, s - pad], start=44, end=74,
          fill=VIOLET, width=max(1, int(s * 0.045)))

    # lightning bolt through the middle
    bolt = [(0.56, 0.17), (0.33, 0.55), (0.47, 0.55),
            (0.42, 0.83), (0.67, 0.44), (0.52, 0.44), (0.60, 0.17)]
    d.polygon([(x * s, y * s) for x, y in bolt], fill=LIME)

    return img.resize((size, size), Image.LANCZOS)


def main():
    entries = []
    for ostype, size in SLOTS:
        from io import BytesIO
        buf = BytesIO()
        draw(size).save(buf, format="PNG")
        payload = buf.getvalue()
        entries.append(ostype + struct.pack(">I", len(payload) + 8) + payload)

    body = b"".join(entries)
    blob = b"icns" + struct.pack(">I", len(body) + 8) + body

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as handle:
        handle.write(blob)
    print("wrote %s  (%d slots, %.1f KB)" % (OUT, len(SLOTS), len(blob) / 1024.0))


if __name__ == "__main__":
    main()
