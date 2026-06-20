from __future__ import annotations

from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from tools.style_lab.models import ReferenceSample, StyleLabInputError

PADDING = 16
TITLE_HEIGHT = 48
LABEL_HEIGHT = 30
CELL_GAP = 14
JPEG_QUALITY = 92


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _missing_images(samples: list[ReferenceSample], image_root: Path) -> list[str]:
    return [sample.filename for sample in samples if not (image_root / sample.filename).exists()]


def build_contact_sheet(
    *,
    samples: list[ReferenceSample],
    image_root: Path,
    output_path: Path,
    title: str,
    cell_width: int,
    cell_height: int,
    columns: int,
) -> None:
    missing = _missing_images(samples, image_root)
    if missing:
        raise StyleLabInputError(f"missing reference images: {', '.join(missing)}")
    if columns <= 0:
        raise StyleLabInputError("columns must be greater than 0")
    if cell_width <= 0 or cell_height <= 0:
        raise StyleLabInputError("cell dimensions must be greater than 0")

    rows = ceil(len(samples) / columns) if samples else 1
    sheet_width = PADDING + columns * cell_width + (columns - 1) * CELL_GAP + PADDING
    sheet_height = (
        PADDING
        + TITLE_HEIGHT
        + rows * (LABEL_HEIGHT + cell_height)
        + (rows - 1) * CELL_GAP
        + PADDING
    )
    sheet = Image.new("RGB", (sheet_width, sheet_height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = _load_font(24)
    label_font = _load_font(18)
    draw.text((PADDING, PADDING), title, fill=(20, 20, 20), font=title_font)

    for index, sample in enumerate(samples):
        row, column = divmod(index, columns)
        x = PADDING + column * (cell_width + CELL_GAP)
        y = PADDING + TITLE_HEIGHT + row * (LABEL_HEIGHT + cell_height + CELL_GAP)
        draw.text((x + 4, y + 5), sample.sample_id, fill=(0, 0, 0), font=label_font)
        cell_y = y + LABEL_HEIGHT
        with Image.open(image_root / sample.filename) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            rgb.thumbnail((cell_width, cell_height), Image.Resampling.LANCZOS)
            framed = Image.new("RGB", (cell_width, cell_height), "white")
            offset_x = (cell_width - rgb.width) // 2
            offset_y = (cell_height - rgb.height) // 2
            framed.paste(rgb, (offset_x, offset_y))
        sheet.paste(framed, (x, cell_y))
        draw.rectangle(
            (x, cell_y, x + cell_width - 1, cell_y + cell_height - 1),
            outline=(208, 208, 208),
            width=1,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=JPEG_QUALITY)
