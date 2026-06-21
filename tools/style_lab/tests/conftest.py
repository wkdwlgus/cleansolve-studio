from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tools.style_lab.reference_set import CORE_SAMPLE_IDS, EXTENDED_SAMPLE_IDS


def _draw_formula_lines(draw: ImageDraw.ImageDraw, y_start: int, color: tuple[int, int, int]) -> None:
    y = y_start
    for index in range(8):
        x = 70
        draw.line((x, y, x + 140, y), fill=color, width=3)
        draw.line((x + 155, y - 8, x + 195, y + 8), fill=color, width=2)
        draw.line((x + 210, y, x + 300, y), fill=color, width=3)
        if index % 2 == 0:
            draw.line((x + 330, y - 10, x + 420, y - 10), fill=color, width=2)
            draw.line((x + 340, y + 10, x + 410, y + 10), fill=color, width=2)
        y += 42


def _draw_problem_text(draw: ImageDraw.ImageDraw) -> None:
    gray = (172, 172, 172)
    for row in range(5):
        y = 36 + row * 20
        draw.line((42, y, 430, y), fill=gray, width=1)
        draw.line((450, y, 590, y), fill=gray, width=1)


def _draw_paragraph_block(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    for row in range(5):
        yy = y + row * 24
        draw.line((x, yy, x + 120, yy), fill=(20, 20, 20), width=2)
        draw.line((x + 135, yy, x + 260, yy), fill=(20, 20, 20), width=2)
        draw.line((x + 278, yy, x + 330, yy), fill=(20, 20, 20), width=2)


def _draw_geometry(draw: ImageDraw.ImageDraw, variant: str) -> None:
    black = (26, 26, 26)
    blue = (50, 68, 190)
    red = (218, 90, 58)
    if variant in {"geometry", "paragraph", "steps"}:
        draw.polygon([(380, 220), (560, 525), (260, 530)], outline=black)
        draw.line((380, 220, 380, 530), fill=blue, width=3)
        draw.arc((286, 250, 548, 560), 200, 338, fill=red, width=3)
        draw.rectangle((318, 412, 445, 462), outline=red, width=2)
    else:
        draw.line((90, 540, 570, 540), fill=black, width=2)
        draw.line((130, 190, 130, 720), fill=black, width=2)
        draw.arc((150, 205, 510, 590), 20, 160, fill=blue, width=3)
        draw.line((210, 500, 410, 260), fill=red, width=3)


def _draw_hatching(draw: ImageDraw.ImageDraw) -> None:
    for offset in range(0, 96, 12):
        draw.line((285 + offset, 520, 320 + offset, 455), fill=(218, 90, 58), width=1)


def create_composite_solution_image(path: Path, variant: str) -> None:
    image = Image.new("RGB", (640, 900), "white")
    draw = ImageDraw.Draw(image)
    _draw_problem_text(draw)
    _draw_geometry(draw, variant)
    _draw_hatching(draw)
    if variant == "integral":
        _draw_formula_lines(draw, 410, (20, 20, 20))
        draw.arc((72, 365, 112, 455), 90, 270, fill=(20, 20, 20), width=4)
    elif variant == "graph":
        _draw_formula_lines(draw, 610, (20, 20, 20))
    else:
        _draw_formula_lines(draw, 590, (20, 20, 20))
    _draw_paragraph_block(draw, 48, 150)
    draw.line((80, 792, 420, 792), fill=(50, 68, 190), width=3)
    draw.line((92, 832, 300, 832), fill=(218, 90, 58), width=3)
    draw.rectangle((432, 760, 588, 825), outline=(218, 90, 58), width=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


@pytest.fixture
def simple_metric_images(tmp_path) -> dict[str, Path]:
    black = tmp_path / "black_line.png"
    red = tmp_path / "red_orange_line.png"
    blue = tmp_path / "blue_purple_line.png"
    for path, color in [
        (black, (20, 20, 20)),
        (red, (220, 82, 45)),
        (blue, (70, 65, 190)),
    ]:
        image = Image.new("RGB", (80, 60), "white")
        draw = ImageDraw.Draw(image)
        draw.line((10, 30, 70, 30), fill=color, width=4)
        image.save(path)
    return {"black": black, "red": red, "blue": blue}


@pytest.fixture
def composite_solution_images(tmp_path) -> dict[str, Path]:
    variants = {
        "GT_024": "geometry",
        "GT_049": "graph",
        "GT_079": "integral",
        "GT_086": "paragraph",
        "GT_147": "steps",
    }
    output: dict[str, Path] = {}
    for sample_id, variant in variants.items():
        path = tmp_path / f"{sample_id}.png"
        create_composite_solution_image(path, variant)
        output[sample_id] = path
    return output


@pytest.fixture
def approved_reference_image_root(tmp_path) -> Path:
    variants = ["geometry", "graph", "integral", "paragraph", "steps"]
    all_ids = CORE_SAMPLE_IDS + EXTENDED_SAMPLE_IDS
    for index, sample_id in enumerate(all_ids):
        create_composite_solution_image(tmp_path / f"{sample_id}.png", variants[index % len(variants)])
    return tmp_path
