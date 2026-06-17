import hashlib
import struct
import zlib

import pytest

from cleansolve_renderer.export_png import render_export_png


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def chunk_payloads(png_bytes: bytes, chunk_type: bytes) -> list[bytes]:
    offset = len(PNG_SIGNATURE)
    payloads: list[bytes] = []
    while offset < len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        current_type = png_bytes[offset + 4 : offset + 8]
        payload = png_bytes[offset + 8 : offset + 8 + length]
        if current_type == chunk_type:
            payloads.append(payload)
        offset += 12 + length
    return payloads


def text_chunks(png_bytes: bytes) -> dict[str, str]:
    chunks: dict[str, str] = {}
    for payload in chunk_payloads(png_bytes, b"tEXt"):
        key, value = payload.split(b"\x00", 1)
        chunks[key.decode("latin-1")] = value.decode("utf-8")
    return chunks


def test_render_export_png_writes_valid_signature_and_ihdr_dimensions():
    png = render_export_png(width=17, height=11, svg="<svg></svg>", metadata={})

    assert png.startswith(PNG_SIGNATURE)
    ihdr = chunk_payloads(png, b"IHDR")[0]
    width, height, bit_depth, color_type = struct.unpack(">IIBB", ihdr[:10])
    assert (width, height) == (17, 11)
    assert bit_depth == 8
    assert color_type == 2


def test_render_export_png_embeds_required_and_caller_metadata():
    svg = "<svg>overlay</svg>"
    png = render_export_png(
        width=2,
        height=2,
        svg=svg,
        metadata={"CleanSolve-Job-ID": "job_123"},
    )

    chunks = text_chunks(png)
    assert chunks["CleanSolve-Export-Version"] == "m6-png-prototype-v1"
    assert chunks["CleanSolve-SVG-SHA256"] == hashlib.sha256(svg.encode("utf-8")).hexdigest()
    assert chunks["CleanSolve-Source"] == "deterministic-overlay-svg"
    assert chunks["CleanSolve-Job-ID"] == "job_123"


def test_render_export_png_writes_caller_metadata_in_sorted_order_after_required_chunks():
    png = render_export_png(
        width=1,
        height=1,
        svg="<svg></svg>",
        metadata={"b-key": "2", "a-key": "1"},
    )

    ordered_keys = [payload.split(b"\x00", 1)[0].decode("latin-1") for payload in chunk_payloads(png, b"tEXt")]
    assert ordered_keys == [
        "CleanSolve-Export-Version",
        "CleanSolve-SVG-SHA256",
        "CleanSolve-Source",
        "a-key",
        "b-key",
    ]


def test_render_export_png_writes_white_rgb_rows_with_no_filter_bytes():
    width = 2
    height = 3
    png = render_export_png(width=width, height=height, svg="<svg></svg>", metadata={})

    idat = b"".join(chunk_payloads(png, b"IDAT"))
    expected_raw = (b"\x00" + (b"\xff\xff\xff" * width)) * height
    assert zlib.decompress(idat) == expected_raw
    assert idat == zlib.compress(expected_raw, level=9)


def test_render_export_png_is_deterministic_for_same_input():
    kwargs = {
        "width": 3,
        "height": 4,
        "svg": "<svg><path /></svg>",
        "metadata": {"b": "2", "a": "1"},
    }

    assert render_export_png(**kwargs) == render_export_png(**kwargs)


@pytest.mark.parametrize(("width", "height"), [(0, 1), (1, 0), (-1, 1), (1, -1)])
def test_render_export_png_rejects_non_positive_dimensions(width, height):
    with pytest.raises(ValueError, match="width and height must be positive integers"):
        render_export_png(width=width, height=height, svg="<svg></svg>", metadata={})


@pytest.mark.parametrize(("width", "height"), [(1.5, 1), (1, "2"), (True, 1), (1, False)])
def test_render_export_png_rejects_non_integer_dimensions(width, height):
    with pytest.raises(ValueError, match="width and height must be positive integers"):
        render_export_png(width=width, height=height, svg="<svg></svg>", metadata={})


def test_render_export_png_rejects_images_larger_than_export_limit():
    with pytest.raises(ValueError, match="export image dimensions exceed 10000000 pixels"):
        render_export_png(width=100_001, height=100, svg="<svg></svg>", metadata={})
