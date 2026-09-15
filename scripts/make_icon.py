"""Generate assets/orderflow.ico — a small order-flow icon, no dependencies.

Draws natively at 16/32/64/128 px (no downscaling, so the small sizes stay
legible): dark rounded tile, bid/ask volume bars, and a price trail across them.
Writes PNG payloads straight into an ICO container (Vista+ format).
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

BG = (11, 18, 32)          # app-dark tile
EDGE = (30, 45, 74)
GREEN = (74, 222, 128)     # bid volume
RED = (248, 113, 113)      # ask volume
AMBER = (251, 191, 36)     # price trail
OUT = Path(__file__).resolve().parents[1] / "assets" / "orderflow.ico"


def canvas(size: int) -> list[list[tuple[int, int, int]]]:
    return [[EDGE for _ in range(size)] for _ in range(size)]


def put(px, x, y, colour) -> None:
    if 0 <= y < len(px) and 0 <= x < len(px[0]):
        px[y][x] = colour


def rect(px, x0, y0, x1, y1, colour) -> None:
    for y in range(y0, y1):
        for x in range(x0, x1):
            put(px, x, y, colour)


def draw(size: int) -> list[list[tuple[int, int, int]]]:
    px = canvas(size)
    # inner panel (leaves a 1px border at small sizes)
    b = 1 if size <= 32 else 2
    rect(px, b, b, size - b, size - b, BG)

    # volume bars: bottom-aligned, alternating bid/ask, chunky enough for 16px
    bars = 5
    span = size - 2 * b - 2
    gap = max(1, span // (bars * 4))
    width = max(1, (span - gap * (bars - 1)) // bars)
    heights = (0.34, 0.55, 0.42, 0.72, 0.58)
    left = b + 1
    tops = []
    for i, h in enumerate(heights):
        x0 = left + i * (width + gap)
        y1 = size - b - 1
        y0 = y1 - max(2, int((size - 2 * b - 2) * h))
        rect(px, x0, y0, x0 + width, y1, GREEN if i % 2 == 0 else RED)
        tops.append((x0 + width // 2, y0))

    # price trail across the bar tops
    thickness = 1 if size <= 32 else 2
    for i in range(len(tops) - 1):
        (x0, y0), (x1, y1) = tops[i], tops[i + 1]
        steps = max(1, x1 - x0)
        for s in range(steps + 1):
            t = s / steps
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            rect(px, x, y, x + width, y + thickness, AMBER)
    return px


def png_bytes(px) -> bytes:
    size = len(px)
    raw = b"".join(b"\x00" + b"".join(struct.pack("BBB", *px[y][x]) for x in range(size)) for y in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def main() -> int:
    sizes = (16, 32, 64, 128)
    images = [png_bytes(draw(s)) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, blob in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0,
                               0, 0, 1, 32, len(blob), offset)
        blobs += blob
        offset += len(blob)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(header + entries + blobs)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, sizes {sizes})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
