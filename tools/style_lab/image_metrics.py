from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageOps

from tools.style_lab.models import ImageMetric

METRICS_CSV_HEADER = [
    "sample_id",
    "path",
    "width",
    "height",
    "aspect_ratio",
    "ink_ratio",
    "dark_ratio",
    "red_ratio",
    "blue_ratio",
]


def _ratio(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def compute_image_metric(sample_id: str, path: Path) -> ImageMetric:
    with Image.open(path) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
        width, height = rgb.size
        pixels = list(rgb.getdata())

    total = len(pixels)
    ink = 0
    dark = 0
    red = 0
    blue = 0
    for r, g, b in pixels:
        if r < 245 or g < 245 or b < 245:
            ink += 1
        if r < 120 and g < 120 and b < 120:
            dark += 1
        if r > 150 and g < 130 and b < 130:
            red += 1
        if b > 130 and r < 150 and g < 170:
            blue += 1

    return ImageMetric(
        sample_id=sample_id,
        path=str(path),
        width=width,
        height=height,
        aspect_ratio=round(width / height, 6),
        ink_ratio=_ratio(ink, total),
        dark_ratio=_ratio(dark, total),
        red_ratio=_ratio(red, total),
        blue_ratio=_ratio(blue, total),
    )


def write_metrics_csv(metrics: list[ImageMetric], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(METRICS_CSV_HEADER)
        for metric in metrics:
            writer.writerow(metric.to_csv_row())
