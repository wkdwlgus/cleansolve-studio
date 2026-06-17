from __future__ import annotations

import binascii
import hashlib
import struct
import zlib


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXPORT_VERSION = "m6-png-prototype-v1"
SOURCE = "deterministic-overlay-svg"
MAX_EXPORT_PIXELS = 10_000_000


def render_export_png(
    *,
    width: int,
    height: int,
    svg: str,
    metadata: dict[str, str],
) -> bytes:
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("width and height must be positive integers")
    if width * height > MAX_EXPORT_PIXELS:
        raise ValueError(f"export image dimensions exceed {MAX_EXPORT_PIXELS} pixels")

    svg_bytes = svg.encode("utf-8")
    raw_row = b"\x00" + (b"\xff\xff\xff" * width)
    raw_image = raw_row * height

    chunks = [
        _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
        _text_chunk("CleanSolve-Export-Version", EXPORT_VERSION),
        _text_chunk("CleanSolve-SVG-SHA256", hashlib.sha256(svg_bytes).hexdigest()),
        _text_chunk("CleanSolve-Source", SOURCE),
    ]
    chunks.extend(_text_chunk(key, metadata[key]) for key in sorted(metadata))
    chunks.extend(
        [
            _chunk(b"IDAT", zlib.compress(raw_image, level=9)),
            _chunk(b"IEND", b""),
        ]
    )
    return PNG_SIGNATURE + b"".join(chunks)


def _chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(chunk_type + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def _text_chunk(key: str, value: str) -> bytes:
    return _chunk(b"tEXt", key.encode("ascii") + b"\x00" + value.encode("utf-8"))
