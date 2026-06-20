from pathlib import Path

import pytest
from PIL import Image

from tools.style_lab.contact_sheet import build_contact_sheet
from tools.style_lab.models import ReferenceSample, StyleLabInputError


def _sample(sample_id: str) -> ReferenceSample:
    return ReferenceSample(
        sample_id=sample_id,
        tier="core",
        role="test fixture",
        filename=f"{sample_id}.png",
    )


def test_contact_sheet_creates_rgb_image_with_expected_dimensions(tmp_path, composite_solution_images):
    image_root = tmp_path / "images"
    image_root.mkdir()
    for sample_id, path in composite_solution_images.items():
        path.replace(image_root / f"{sample_id}.png")
    samples = [_sample(sample_id) for sample_id in composite_solution_images]
    output = tmp_path / "sheet.jpg"

    build_contact_sheet(
        samples=samples,
        image_root=image_root,
        output_path=output,
        title="Core Sheet",
        cell_width=120,
        cell_height=160,
        columns=3,
    )

    with Image.open(output) as sheet:
        assert sheet.mode == "RGB"
        assert sheet.size == (420, 474)


def test_contact_sheet_contains_dark_pixels_in_first_label_area(tmp_path, composite_solution_images):
    image_root = tmp_path / "images"
    image_root.mkdir()
    first_path = composite_solution_images["GT_024"]
    first_path.replace(image_root / "GT_024.png")
    output = tmp_path / "sheet.jpg"

    build_contact_sheet(
        samples=[_sample("GT_024")],
        image_root=image_root,
        output_path=output,
        title="Core Sheet",
        cell_width=120,
        cell_height=160,
        columns=1,
    )

    with Image.open(output).convert("RGB") as sheet:
        label_crop = sheet.crop((16, 64, 136, 94))
        assert any(r < 80 and g < 80 and b < 80 for r, g, b in label_crop.getdata())


def test_contact_sheet_raises_for_missing_reference_image(tmp_path):
    output = tmp_path / "sheet.jpg"

    with pytest.raises(StyleLabInputError, match="missing reference images: GT_024.png"):
        build_contact_sheet(
            samples=[_sample("GT_024")],
            image_root=tmp_path,
            output_path=output,
            title="Core Sheet",
            cell_width=120,
            cell_height=160,
            columns=1,
        )
