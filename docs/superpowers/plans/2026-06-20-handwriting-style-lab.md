# Handwriting Style Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 승인된 손글씨 레퍼런스 세트를 deterministic Style Lab 산출물로 고정하는 Python CLI와 테스트 harness를 만든다.

**Architecture:** `tools/style_lab`는 런타임 workflow와 분리된 개발 도구다. 로컬 `/image/clean_solutions`의 승인 sample id를 읽고, manifest, metrics, contact sheet, style token skeleton을 생성한다. OpenAI API, renderer 튜닝, web UI 연결은 이번 계획에 포함하지 않는다.

**Tech Stack:** Python 3.13, pytest, Pillow, dataclasses, argparse, JSON/CSV 표준 라이브러리.

---

## File Structure

Create:

- `tools/style_lab/__init__.py`: package marker and public version.
- `tools/style_lab/models.py`: dataclasses, constants, `StyleLabInputError`.
- `tools/style_lab/reference_set.py`: approved core/extended reference set constants and validation.
- `tools/style_lab/image_metrics.py`: PIL-based image metrics and CSV writer.
- `tools/style_lab/contact_sheet.py`: deterministic contact sheet generator.
- `tools/style_lab/tokens.py`: style token skeleton builder.
- `tools/style_lab/manifest.py`: calibration manifest builder and JSON writer.
- `tools/style_lab/cli.py`: `python -m tools.style_lab.cli build` entrypoint.
- `tools/style_lab/README.md`: Korean operator/developer documentation.
- `tools/style_lab/tests/conftest.py`: composite solution fixture image generators.
- `tools/style_lab/tests/test_reference_set.py`
- `tools/style_lab/tests/test_image_metrics.py`
- `tools/style_lab/tests/test_contact_sheet.py`
- `tools/style_lab/tests/test_manifest.py`
- `tools/style_lab/tests/test_cli.py`

Modify:

- `pyproject.toml`: add `Pillow`.
- `pytest.ini`: add style lab tests to pytest testpaths and add `.` to pythonpath.
- `assets/style-presets/default_pretty_handwriting/preset.json`: add calibration contract fields.
- `docs/product/handwriting-style-reference-set.md`: add Style Lab command and output paths.

Generated but not committed:

- `image/style-lab/default_pretty_handwriting/v1/core_contact_sheet.jpg`
- `image/style-lab/default_pretty_handwriting/v1/extended_contact_sheet.jpg`
- `image/style-lab/default_pretty_handwriting/v1/calibration_manifest.json`
- `image/style-lab/default_pretty_handwriting/v1/style_tokens.skeleton.json`
- `image/style-lab/default_pretty_handwriting/v1/metrics.csv`

---

### Task 1: Reference Set Contract

**Files:**
- Create: `tools/style_lab/__init__.py`
- Create: `tools/style_lab/models.py`
- Create: `tools/style_lab/reference_set.py`
- Create: `tools/style_lab/tests/test_reference_set.py`
- Modify: `pyproject.toml`
- Modify: `pytest.ini`

- [ ] **Step 1: Write failing reference set tests**

Create `tools/style_lab/tests/test_reference_set.py`:

```python
from tools.style_lab.reference_set import (
    CORE_SAMPLE_IDS,
    EXTENDED_SAMPLE_IDS,
    build_reference_samples,
)


def test_core_and_extended_counts_match_approved_contract():
    assert len(CORE_SAMPLE_IDS) == 19
    assert len(EXTENDED_SAMPLE_IDS) == 26


def test_sample_ids_are_gt_three_digit_format():
    all_ids = CORE_SAMPLE_IDS + EXTENDED_SAMPLE_IDS

    assert all(sample_id.startswith("GT_") for sample_id in all_ids)
    assert all(len(sample_id) == 6 for sample_id in all_ids)
    assert all(sample_id[3:].isdigit() for sample_id in all_ids)


def test_core_and_extended_sets_do_not_overlap():
    assert set(CORE_SAMPLE_IDS).isdisjoint(set(EXTENDED_SAMPLE_IDS))


def test_build_reference_samples_assigns_tiers_roles_and_filenames():
    samples = build_reference_samples()

    assert len(samples) == 45
    assert samples[0].sample_id == "GT_024"
    assert samples[0].tier == "core"
    assert samples[0].filename == "GT_024.png"
    assert samples[0].role
    assert samples[-1].tier == "extended"
    assert samples[-1].filename == f"{samples[-1].sample_id}.png"
```

- [ ] **Step 2: Update dependency and pytest discovery before running tests**

Modify `pyproject.toml`:

```toml
[project]
dependencies = [
  "fastapi",
  "langgraph",
  "openai",
  "Pillow",
  "pydantic",
  "pytest",
  "python-multipart",
]
```

Modify `pytest.ini`:

```ini
[pytest]
testpaths =
    apps/api/tests
    packages/ai/tests
    packages/harness/tests
    packages/renderer/tests
    packages/spec/tests
    packages/workflow/tests
    tools/style_lab/tests
pythonpath =
    .
    apps/api
    packages/ai
    packages/harness
    packages/renderer
    packages/spec
    packages/workflow
```

Do not add `[tool.pytest.ini_options]` to `pyproject.toml`; this repository already uses `pytest.ini` as the pytest configuration source.

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
python -m pytest tools/style_lab/tests/test_reference_set.py -q
```

Expected: FAIL because `tools.style_lab.reference_set` does not exist.

- [ ] **Step 4: Implement reference models and constants**

Create `tools/style_lab/__init__.py`:

```python
"""Style Lab tools for CleanSolve Studio handwriting calibration."""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `tools/style_lab/models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


class StyleLabInputError(ValueError):
    """Raised when Style Lab input files or reference contracts are invalid."""


@dataclass(frozen=True)
class ReferenceSample:
    sample_id: str
    tier: Literal["core", "extended"]
    role: str
    filename: str

    def __post_init__(self) -> None:
        if self.tier not in {"core", "extended"}:
            raise StyleLabInputError(f"invalid sample tier: {self.tier}")
        if not self.sample_id.startswith("GT_") or len(self.sample_id) != 6 or not self.sample_id[3:].isdigit():
            raise StyleLabInputError(f"invalid sample id: {self.sample_id}")
        expected_filename = f"{self.sample_id}.png"
        if self.filename != expected_filename:
            raise StyleLabInputError(f"invalid filename for {self.sample_id}: {self.filename}")
        if not self.role.strip():
            raise StyleLabInputError(f"missing role for {self.sample_id}")

    def to_json(self) -> dict[str, str]:
        return asdict(self)
```

Create `tools/style_lab/reference_set.py`:

```python
from __future__ import annotations

from tools.style_lab.models import ReferenceSample, StyleLabInputError

CORE_SAMPLE_ROLES: dict[str, str] = {
    "GT_024": "빽빽한 기하 풀이, 도형 위 색상 보조선, 높은 잉크 밀도 기준",
    "GT_036": "여백이 큰 단일 적분 문제, 큰 수식 간격과 줄바꿈 기준",
    "GT_043": "긴 다단계 풀이, 작은 글씨와 색상 강조가 섞인 고밀도 레이아웃",
    "GT_049": "좌표 그래프, 면적 해칭, 파란색 주석 기준",
    "GT_058": "함수 그래프와 구간 표시, 그래프 아래 보조 도형 기준",
    "GT_067": "기하 도형 안 라벨, 보조선, 면적 계산 전개 기준",
    "GT_073": "곡선 그래프, 반복 해칭, 색상 곡선 주석 기준",
    "GT_079": "큰 적분 기호, 루트/분수 수식의 손글씨 질감 기준",
    "GT_082": "큰 좌표축 위 그래프, 도형과 옆 주석이 분리된 구성 기준",
    "GT_086": "한글 설명과 수식 전개가 섞인 문단형 풀이 기준",
    "GT_090": "점근선형 그래프, 그림 아래 compact 수식 전개 기준",
    "GT_099": "붉은 박스 강조, 색상별 수식 계층, 삼각함수 전개 기준",
    "GT_102": "원/삼각형 기하, 높은 파란색 사용량, 라벨 밀도 기준",
    "GT_116": "큰 기하 도형과 sparse 풀이의 균형 기준",
    "GT_132": "가장 높은 잉크 밀도 구간의 기하+수식 혼합 기준",
    "GT_135": "색상 보조선이 많은 기하 풀이, 빨강/파랑 교정 표기 기준",
    "GT_141": "긴 도형 풀이와 색상 수식 블록의 하단 배치 기준",
    "GT_146": "도형 없는 긴 기호 전개, 극한/함수식 줄맞춤 기준",
    "GT_147": "단계형 텍스트+수식 풀이, 색상별 결론 정리 기준",
}

EXTENDED_SAMPLE_IDS: list[str] = [
    "GT_001",
    "GT_003",
    "GT_009",
    "GT_010",
    "GT_019",
    "GT_023",
    "GT_028",
    "GT_037",
    "GT_056",
    "GT_063",
    "GT_075",
    "GT_080",
    "GT_088",
    "GT_091",
    "GT_094",
    "GT_101",
    "GT_104",
    "GT_117",
    "GT_122",
    "GT_129",
    "GT_131",
    "GT_134",
    "GT_137",
    "GT_140",
    "GT_142",
    "GT_145",
]

CORE_SAMPLE_IDS: list[str] = list(CORE_SAMPLE_ROLES)


def validate_reference_contract() -> None:
    if len(CORE_SAMPLE_IDS) != 19:
        raise StyleLabInputError(f"expected 19 core samples, got {len(CORE_SAMPLE_IDS)}")
    if len(EXTENDED_SAMPLE_IDS) != 26:
        raise StyleLabInputError(f"expected 26 extended samples, got {len(EXTENDED_SAMPLE_IDS)}")
    overlap = sorted(set(CORE_SAMPLE_IDS) & set(EXTENDED_SAMPLE_IDS))
    if overlap:
        raise StyleLabInputError(f"core and extended samples overlap: {', '.join(overlap)}")


def build_reference_samples() -> list[ReferenceSample]:
    validate_reference_contract()
    core = [
        ReferenceSample(sample_id=sample_id, tier="core", role=role, filename=f"{sample_id}.png")
        for sample_id, role in CORE_SAMPLE_ROLES.items()
    ]
    extended = [
        ReferenceSample(
            sample_id=sample_id,
            tier="extended",
            role="coverage supplement / regression candidate",
            filename=f"{sample_id}.png",
        )
        for sample_id in EXTENDED_SAMPLE_IDS
    ]
    return core + extended
```

- [ ] **Step 5: Run reference tests**

Run:

```bash
python -m pytest tools/style_lab/tests/test_reference_set.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml pytest.ini tools/style_lab/__init__.py tools/style_lab/models.py tools/style_lab/reference_set.py tools/style_lab/tests/test_reference_set.py
git commit -m "feat(style-lab): add reference set contract"
```

---

### Task 2: Image Metrics and Composite Fixtures

**Files:**
- Create: `tools/style_lab/image_metrics.py`
- Create: `tools/style_lab/tests/conftest.py`
- Create: `tools/style_lab/tests/test_image_metrics.py`
- Modify: `tools/style_lab/models.py`

- [ ] **Step 1: Write failing metric tests**

Create `tools/style_lab/tests/test_image_metrics.py`:

```python
from pathlib import Path

from PIL import Image

from tools.style_lab.image_metrics import compute_image_metric, write_metrics_csv


def test_blank_white_image_has_zero_ink_ratio(tmp_path):
    path = tmp_path / "blank_white.png"
    Image.new("RGB", (80, 60), "white").save(path)

    metric = compute_image_metric("GT_001", path)

    assert metric.ink_ratio == 0
    assert metric.dark_ratio == 0
    assert metric.red_ratio == 0
    assert metric.blue_ratio == 0
    assert metric.aspect_ratio == 1.333333


def test_color_ratios_detect_black_red_and_blue_lines(simple_metric_images):
    black = compute_image_metric("GT_001", simple_metric_images["black"])
    red = compute_image_metric("GT_002", simple_metric_images["red"])
    blue = compute_image_metric("GT_003", simple_metric_images["blue"])

    assert black.dark_ratio > 0
    assert red.red_ratio > 0
    assert blue.blue_ratio > 0


def test_composite_solution_fixture_has_multiple_ink_channels(composite_solution_images):
    metric = compute_image_metric("GT_024", composite_solution_images["GT_024"])

    assert metric.width >= 640
    assert metric.height >= 900
    assert metric.ink_ratio > 0.01
    assert metric.dark_ratio > 0
    assert metric.red_ratio > 0
    assert metric.blue_ratio > 0


def test_write_metrics_csv_outputs_stable_header(tmp_path, simple_metric_images):
    metrics = [
        compute_image_metric("GT_001", simple_metric_images["black"]),
        compute_image_metric("GT_002", simple_metric_images["red"]),
    ]
    output = tmp_path / "metrics.csv"

    write_metrics_csv(metrics, output)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "sample_id,path,width,height,aspect_ratio,ink_ratio,dark_ratio,red_ratio,blue_ratio"
    assert lines[1].startswith("GT_001,")
    assert lines[2].startswith("GT_002,")
```

- [ ] **Step 2: Create test fixture generators**

Create `tools/style_lab/tests/conftest.py`:

```python
from __future__ import annotations

from collections.abc import Callable
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
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
python -m pytest tools/style_lab/tests/test_image_metrics.py -q
```

Expected: FAIL because `tools.style_lab.image_metrics` does not exist or `ImageMetric` is missing.

- [ ] **Step 4: Implement image metric model and module**

Append to `tools/style_lab/models.py`:

```python
@dataclass(frozen=True)
class ImageMetric:
    sample_id: str
    path: str
    width: int
    height: int
    aspect_ratio: float
    ink_ratio: float
    dark_ratio: float
    red_ratio: float
    blue_ratio: float

    def to_csv_row(self) -> list[str]:
        return [
            self.sample_id,
            self.path,
            str(self.width),
            str(self.height),
            f"{self.aspect_ratio:.6f}",
            f"{self.ink_ratio:.6f}",
            f"{self.dark_ratio:.6f}",
            f"{self.red_ratio:.6f}",
            f"{self.blue_ratio:.6f}",
        ]
```

Create `tools/style_lab/image_metrics.py`:

```python
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
```

- [ ] **Step 5: Run image metric tests**

Run:

```bash
python -m pytest tools/style_lab/tests/test_image_metrics.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/style_lab/models.py tools/style_lab/image_metrics.py tools/style_lab/tests/conftest.py tools/style_lab/tests/test_image_metrics.py
git commit -m "feat(style-lab): compute reference image metrics"
```

---

### Task 3: Contact Sheet Generator

**Files:**
- Create: `tools/style_lab/contact_sheet.py`
- Create: `tools/style_lab/tests/test_contact_sheet.py`

- [ ] **Step 1: Write failing contact sheet tests**

Create `tools/style_lab/tests/test_contact_sheet.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tools/style_lab/tests/test_contact_sheet.py -q
```

Expected: FAIL because `tools.style_lab.contact_sheet` does not exist.

- [ ] **Step 3: Implement contact sheet generator**

Create `tools/style_lab/contact_sheet.py`:

```python
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
    sheet_height = PADDING + TITLE_HEIGHT + rows * (LABEL_HEIGHT + cell_height) + (rows - 1) * CELL_GAP + PADDING
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
        draw.rectangle((x, cell_y, x + cell_width - 1, cell_y + cell_height - 1), outline=(208, 208, 208), width=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=JPEG_QUALITY)
```

- [ ] **Step 4: Run contact sheet tests**

Run:

```bash
python -m pytest tools/style_lab/tests/test_contact_sheet.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/style_lab/contact_sheet.py tools/style_lab/tests/test_contact_sheet.py
git commit -m "feat(style-lab): generate deterministic contact sheets"
```

---

### Task 4: Manifest and Style Token Skeleton

**Files:**
- Create: `tools/style_lab/tokens.py`
- Create: `tools/style_lab/manifest.py`
- Create: `tools/style_lab/tests/test_manifest.py`

- [ ] **Step 1: Write failing manifest tests**

Create `tools/style_lab/tests/test_manifest.py`:

```python
import json

from tools.style_lab.image_metrics import compute_image_metric
from tools.style_lab.manifest import build_calibration_manifest, write_json
from tools.style_lab.reference_set import build_reference_samples
from tools.style_lab.tokens import build_style_token_skeleton


def _leaf_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _leaf_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _leaf_values(child)
    else:
        yield value


def test_build_style_token_skeleton_has_null_token_leaves():
    skeleton = build_style_token_skeleton(
        preset_id="default_pretty_handwriting",
        preset_version="v1",
        core_count=19,
        extended_count=26,
    )

    assert skeleton["schema_version"] == "style_tokens.v0"
    assert skeleton["status"] == "skeleton_pending_ai_calibration"
    assert skeleton["reference_contract"]["core_count"] == 19
    token_leaf_values = list(_leaf_values(skeleton["tokens"]))
    assert token_leaf_values
    assert set(token_leaf_values) == {None}


def test_build_calibration_manifest_summarizes_metrics(composite_solution_images):
    samples = build_reference_samples()[:5]
    metrics = [
        compute_image_metric(sample.sample_id, composite_solution_images[sample.sample_id])
        for sample in samples
        if sample.sample_id in composite_solution_images
    ]

    manifest = build_calibration_manifest(
        preset_id="default_pretty_handwriting",
        preset_version="v1",
        samples=build_reference_samples(),
        metrics=metrics,
        artifacts={
            "core_contact_sheet": "out/core_contact_sheet.jpg",
            "extended_contact_sheet": "out/extended_contact_sheet.jpg",
            "calibration_manifest": "out/calibration_manifest.json",
            "style_tokens": "out/style_tokens.skeleton.json",
            "metrics": "out/metrics.csv",
        },
    )

    assert manifest["preset_id"] == "default_pretty_handwriting"
    assert manifest["preset_version"] == "v1"
    assert manifest["source"] == "system_builtin"
    assert manifest["calibration_status"] == "reference_contract_ready"
    assert len(manifest["core_samples"]) == 19
    assert len(manifest["extended_samples"]) == 26
    assert manifest["metrics_summary"]["core_count"] == 19
    assert manifest["metrics_summary"]["extended_count"] == 26
    assert manifest["metrics_summary"]["mean_ink_ratio"] > 0
    assert manifest["metrics_summary"]["max_ink_sample_id"]
    assert manifest["metrics_summary"]["max_color_sample_id"]


def test_write_json_uses_utf8_and_stable_indentation(tmp_path):
    output = tmp_path / "manifest.json"

    write_json({"b": 1, "a": "한글"}, output)

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == {"a": "한글", "b": 1}
    assert output.read_text(encoding="utf-8").endswith("\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tools/style_lab/tests/test_manifest.py -q
```

Expected: FAIL because `tools.style_lab.manifest` and `tools.style_lab.tokens` do not exist.

- [ ] **Step 3: Implement token skeleton builder**

Create `tools/style_lab/tokens.py`:

```python
from __future__ import annotations


def build_style_token_skeleton(
    *,
    preset_id: str,
    preset_version: str,
    core_count: int,
    extended_count: int,
) -> dict[str, object]:
    return {
        "preset_id": preset_id,
        "preset_version": preset_version,
        "schema_version": "style_tokens.v0",
        "status": "skeleton_pending_ai_calibration",
        "reference_contract": {
            "core_count": core_count,
            "extended_count": extended_count,
            "reference_set_doc": "docs/product/handwriting-style-reference-set.md",
        },
        "tokens": {
            "stroke": {
                "black_width_px": None,
                "blue_width_px": None,
                "red_width_px": None,
                "jitter_px": None,
                "opacity": None,
            },
            "text": {
                "korean_baseline_jitter_px": None,
                "letter_spacing_px": None,
                "line_height_ratio": None,
                "size_ratio_to_formula": None,
            },
            "formula": {
                "baseline_jitter_px": None,
                "fraction_bar_width_px": None,
                "symbol_slant_deg": None,
                "vertical_compactness": None,
            },
            "diagram": {
                "label_offset_px": None,
                "annotation_line_width_px": None,
                "hatching_gap_px": None,
                "hatching_angle_jitter_deg": None,
            },
            "palette": {
                "black": None,
                "blue": None,
                "red_orange": None,
            },
        },
    }
```

- [ ] **Step 4: Implement manifest builder**

Create `tools/style_lab/manifest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from tools.style_lab.models import ImageMetric, ReferenceSample


def _round_mean(values: list[float]) -> float:
    return round(mean(values), 6) if values else 0.0


def _max_color_metric(metrics: list[ImageMetric]) -> ImageMetric | None:
    if not metrics:
        return None
    return max(metrics, key=lambda metric: (metric.red_ratio + metric.blue_ratio, metric.sample_id))


def build_metrics_summary(samples: list[ReferenceSample], metrics: list[ImageMetric]) -> dict[str, object]:
    core_count = sum(1 for sample in samples if sample.tier == "core")
    extended_count = sum(1 for sample in samples if sample.tier == "extended")
    max_ink = max(metrics, key=lambda metric: (metric.ink_ratio, metric.sample_id), default=None)
    max_color = _max_color_metric(metrics)
    return {
        "core_count": core_count,
        "extended_count": extended_count,
        "mean_ink_ratio": _round_mean([metric.ink_ratio for metric in metrics]),
        "mean_dark_ratio": _round_mean([metric.dark_ratio for metric in metrics]),
        "mean_red_ratio": _round_mean([metric.red_ratio for metric in metrics]),
        "mean_blue_ratio": _round_mean([metric.blue_ratio for metric in metrics]),
        "max_ink_sample_id": max_ink.sample_id if max_ink else None,
        "max_color_sample_id": max_color.sample_id if max_color else None,
    }


def build_calibration_manifest(
    *,
    preset_id: str,
    preset_version: str,
    samples: list[ReferenceSample],
    metrics: list[ImageMetric],
    artifacts: dict[str, str],
) -> dict[str, object]:
    return {
        "preset_id": preset_id,
        "preset_version": preset_version,
        "source": "system_builtin",
        "calibration_status": "reference_contract_ready",
        "created_by": "tools.style_lab",
        "reference_set_doc": "docs/product/handwriting-style-reference-set.md",
        "core_samples": [sample.to_json() for sample in samples if sample.tier == "core"],
        "extended_samples": [sample.to_json() for sample in samples if sample.tier == "extended"],
        "artifacts": artifacts,
        "metrics_summary": build_metrics_summary(samples, metrics),
    }


def write_json(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
```

- [ ] **Step 5: Run manifest tests**

Run:

```bash
python -m pytest tools/style_lab/tests/test_manifest.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/style_lab/tokens.py tools/style_lab/manifest.py tools/style_lab/tests/test_manifest.py
git commit -m "feat(style-lab): build calibration manifest"
```

---

### Task 5: CLI, Preset Metadata, and Korean Docs

**Files:**
- Create: `tools/style_lab/cli.py`
- Create: `tools/style_lab/README.md`
- Create: `tools/style_lab/tests/test_cli.py`
- Modify: `assets/style-presets/default_pretty_handwriting/preset.json`
- Modify: `docs/product/handwriting-style-reference-set.md`

- [ ] **Step 1: Write failing CLI tests**

Create `tools/style_lab/tests/test_cli.py`:

```python
import json
import subprocess
import sys

from PIL import Image


def test_cli_build_outputs_all_artifacts(tmp_path, approved_reference_image_root):
    output_root = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.style_lab.cli",
            "build",
            "--image-root",
            str(approved_reference_image_root),
            "--output-root",
            str(output_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["core_count"] == 19
    assert payload["extended_count"] == 26
    for artifact_path in payload["artifacts"].values():
        assert artifact_path
        assert (output_root / artifact_path.split("/")[-1]).exists()
    with Image.open(output_root / "core_contact_sheet.jpg") as image:
        assert image.size[0] > 0
        assert image.size[1] > 0
    with Image.open(output_root / "extended_contact_sheet.jpg") as image:
        assert image.size[0] > 0
        assert image.size[1] > 0


def test_cli_build_returns_code_2_for_missing_images(tmp_path, approved_reference_image_root):
    (approved_reference_image_root / "GT_024.png").unlink()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.style_lab.cli",
            "build",
            "--image-root",
            str(approved_reference_image_root),
            "--output-root",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "GT_024.png" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tools/style_lab/tests/test_cli.py -q
```

Expected: FAIL because `tools.style_lab.cli` does not exist.

- [ ] **Step 3: Implement CLI**

Create `tools/style_lab/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.style_lab.contact_sheet import build_contact_sheet
from tools.style_lab.image_metrics import compute_image_metric, write_metrics_csv
from tools.style_lab.manifest import build_calibration_manifest, write_json
from tools.style_lab.models import StyleLabInputError
from tools.style_lab.reference_set import CORE_SAMPLE_IDS, EXTENDED_SAMPLE_IDS, build_reference_samples
from tools.style_lab.tokens import build_style_token_skeleton


def _relative_artifacts(output_root: Path) -> dict[str, str]:
    return {
        "core_contact_sheet": str(output_root / "core_contact_sheet.jpg"),
        "extended_contact_sheet": str(output_root / "extended_contact_sheet.jpg"),
        "calibration_manifest": str(output_root / "calibration_manifest.json"),
        "style_tokens": str(output_root / "style_tokens.skeleton.json"),
        "metrics": str(output_root / "metrics.csv"),
    }


def _validate_sample_files(samples, image_root: Path) -> None:
    missing = [sample.filename for sample in samples if not (image_root / sample.filename).exists()]
    if missing:
        raise StyleLabInputError(f"missing reference images: {', '.join(missing)}")


def build_style_lab(args: argparse.Namespace) -> dict[str, object]:
    image_root = Path(args.image_root)
    output_root = Path(args.output_root)
    samples = build_reference_samples()
    core_samples = [sample for sample in samples if sample.tier == "core"]
    extended_samples = [sample for sample in samples if sample.tier == "extended"]
    artifacts = _relative_artifacts(output_root)

    _validate_sample_files(samples, image_root)
    metrics = [compute_image_metric(sample.sample_id, image_root / sample.filename) for sample in samples]
    write_metrics_csv(metrics, Path(artifacts["metrics"]))
    build_contact_sheet(
        samples=core_samples,
        image_root=image_root,
        output_path=Path(artifacts["core_contact_sheet"]),
        title=f"{args.preset_id} {args.preset_version} core reference set",
        cell_width=args.contact_sheet_width,
        cell_height=args.contact_sheet_height,
        columns=args.columns,
    )
    build_contact_sheet(
        samples=extended_samples,
        image_root=image_root,
        output_path=Path(artifacts["extended_contact_sheet"]),
        title=f"{args.preset_id} {args.preset_version} extended calibration set",
        cell_width=args.contact_sheet_width,
        cell_height=args.contact_sheet_height,
        columns=args.columns,
    )
    manifest = build_calibration_manifest(
        preset_id=args.preset_id,
        preset_version=args.preset_version,
        samples=samples,
        metrics=metrics,
        artifacts=artifacts,
    )
    write_json(manifest, Path(artifacts["calibration_manifest"]))
    skeleton = build_style_token_skeleton(
        preset_id=args.preset_id,
        preset_version=args.preset_version,
        core_count=len(CORE_SAMPLE_IDS),
        extended_count=len(EXTENDED_SAMPLE_IDS),
    )
    write_json(skeleton, Path(artifacts["style_tokens"]))
    return {
        "status": "ok",
        "preset_id": args.preset_id,
        "preset_version": args.preset_version,
        "core_count": len(CORE_SAMPLE_IDS),
        "extended_count": len(EXTENDED_SAMPLE_IDS),
        "output_root": str(output_root),
        "artifacts": artifacts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.style_lab.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--image-root", default="image/clean_solutions")
    build.add_argument("--output-root", default="image/style-lab/default_pretty_handwriting/v1")
    build.add_argument("--preset-id", default="default_pretty_handwriting")
    build.add_argument("--preset-version", default="v1")
    build.add_argument("--contact-sheet-width", type=int, default=320)
    build.add_argument("--contact-sheet-height", type=int, default=460)
    build.add_argument("--columns", type=int, default=5)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            payload = build_style_lab(args)
        else:
            parser.error(f"unknown command: {args.command}")
    except StyleLabInputError as exc:
        print(f"Style Lab input error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python -m pytest tools/style_lab/tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Update preset metadata**

Modify `assets/style-presets/default_pretty_handwriting/preset.json` to exactly preserve existing fields and add these siblings:

```json
{
  "preset_id": "default_pretty_handwriting",
  "preset_version": "v1",
  "source": "system_builtin",
  "description": "Default operator-managed handwriting style preset for the MVP.",
  "calibration_status": "reference_contract_ready",
  "reference_set": {
    "doc": "docs/product/handwriting-style-reference-set.md",
    "core_count": 19,
    "extended_count": 26
  },
  "style_lab": {
    "default_image_root": "image/clean_solutions",
    "default_output_root": "image/style-lab/default_pretty_handwriting/v1",
    "manifest_filename": "calibration_manifest.json",
    "style_tokens_filename": "style_tokens.skeleton.json"
  },
  "rendering_notes": {
    "formula_priority": "accuracy_first",
    "text_style": "clean_handwritten",
    "color_preservation": true
  }
}
```

- [ ] **Step 6: Add Korean Style Lab README**

Create `tools/style_lab/README.md`:

```markdown
# Handwriting Style Lab

`tools/style_lab`은 `default_pretty_handwriting v1` 스타일을 캘리브레이션하기 위한 개발 도구입니다.

이 도구는 OpenAI API를 호출하지 않습니다. 승인된 손글씨 레퍼런스 이미지 세트를 읽고, 다음 단계의 GPT-5.5 스타일 분석과 deterministic renderer 튜닝이 사용할 기준 산출물을 만듭니다.

## 입력

기본 입력 위치는 `image/clean_solutions`입니다.

이 directory에는 `GT_024.png`처럼 승인된 core/extended sample id와 같은 이름의 PNG 파일이 있어야 합니다.

## 실행

```bash
python -m tools.style_lab.cli build \
  --image-root image/clean_solutions \
  --output-root image/style-lab/default_pretty_handwriting/v1
```

## 산출물

기본 산출물 위치는 `image/style-lab/default_pretty_handwriting/v1`입니다.

- `core_contact_sheet.jpg`
- `extended_contact_sheet.jpg`
- `calibration_manifest.json`
- `style_tokens.skeleton.json`
- `metrics.csv`

`image/`는 gitignore 대상이므로 위 산출물은 저장소에 커밋하지 않습니다.

## 범위

이번 도구는 레퍼런스 계약과 산출물 생성을 담당합니다.

다음 작업은 이 산출물을 입력으로 삼아 GPT-5.5 스타일 프로필 추출과 renderer 파라미터 튜닝을 진행합니다.
```

- [ ] **Step 7: Update reference set product doc**

Append to `docs/product/handwriting-style-reference-set.md`:

```markdown
## Style Lab 실행

승인된 레퍼런스 세트는 Style Lab의 기본 입력이다.

```bash
python -m tools.style_lab.cli build \
  --image-root image/clean_solutions \
  --output-root image/style-lab/default_pretty_handwriting/v1
```

생성되는 산출물은 다음과 같다.

- `image/style-lab/default_pretty_handwriting/v1/core_contact_sheet.jpg`
- `image/style-lab/default_pretty_handwriting/v1/extended_contact_sheet.jpg`
- `image/style-lab/default_pretty_handwriting/v1/calibration_manifest.json`
- `image/style-lab/default_pretty_handwriting/v1/style_tokens.skeleton.json`
- `image/style-lab/default_pretty_handwriting/v1/metrics.csv`

이 산출물은 `/image` 아래에 생성되므로 git에 커밋하지 않는다.
```

- [ ] **Step 8: Run CLI and focused tests**

Run:

```bash
python -m pytest tools/style_lab/tests/test_cli.py -q
python -m pytest tools/style_lab/tests -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add assets/style-presets/default_pretty_handwriting/preset.json docs/product/handwriting-style-reference-set.md tools/style_lab/README.md tools/style_lab/cli.py tools/style_lab/tests/test_cli.py
git commit -m "feat(style-lab): add build cli and docs"
```

---

### Task 6: Local Real Corpus Build and Final Verification

**Files:**
- Generated only: `image/style-lab/default_pretty_handwriting/v1/*`
- No tracked source edits unless verification finds a bug.

- [ ] **Step 1: Run full Style Lab tests**

Run:

```bash
python -m pytest tools/style_lab/tests -q
```

Expected: PASS.

- [ ] **Step 2: Run existing Python tests**

Run:

```bash
python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/renderer/tests packages/spec/tests packages/workflow/tests -q
```

Expected: PASS.

- [ ] **Step 3: Build local real corpus artifacts**

Run:

```bash
python -m tools.style_lab.cli build \
  --image-root image/clean_solutions \
  --output-root image/style-lab/default_pretty_handwriting/v1
```

Expected stdout includes:

```json
"status": "ok"
```

Expected files exist:

```bash
test -s image/style-lab/default_pretty_handwriting/v1/core_contact_sheet.jpg
test -s image/style-lab/default_pretty_handwriting/v1/extended_contact_sheet.jpg
test -s image/style-lab/default_pretty_handwriting/v1/calibration_manifest.json
test -s image/style-lab/default_pretty_handwriting/v1/style_tokens.skeleton.json
test -s image/style-lab/default_pretty_handwriting/v1/metrics.csv
```

- [ ] **Step 4: Inspect generated manifest**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("image/style-lab/default_pretty_handwriting/v1/calibration_manifest.json").read_text(encoding="utf-8"))
assert manifest["calibration_status"] == "reference_contract_ready"
assert len(manifest["core_samples"]) == 19
assert len(manifest["extended_samples"]) == 26
assert manifest["metrics_summary"]["core_count"] == 19
assert manifest["metrics_summary"]["extended_count"] == 26
print(manifest["metrics_summary"])
PY
```

Expected: prints metrics summary without assertion failure.

- [ ] **Step 5: Confirm generated `/image` artifacts are ignored**

Run:

```bash
git status --short --ignored=matching image/style-lab | sed -n '1,80p'
```

Expected: generated files appear only as ignored `!! image/` or do not appear as tracked changes.

- [ ] **Step 6: Run whitespace diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 7: Commit any bugfixes if verification required source changes**

If Step 1-6 required source edits, commit the exact files that changed. For this plan, valid source files are under `tools/style_lab/`, `assets/style-presets/default_pretty_handwriting/preset.json`, `docs/product/handwriting-style-reference-set.md`, `pyproject.toml`, and `pytest.ini`.

```bash
git add tools/style_lab assets/style-presets/default_pretty_handwriting/preset.json docs/product/handwriting-style-reference-set.md pyproject.toml pytest.ini
git commit -m "fix(style-lab): address verification findings"
```

If no source edits were required, do not create an empty commit.

---

## Review and Branch Completion

After all tasks:

1. Request spec compliance review against `docs/superpowers/specs/2026-06-20-handwriting-style-lab-design.md`.
2. Request code quality review for the full branch.
3. Fix Critical and Important review findings.
4. Re-run:

```bash
python -m pytest tools/style_lab/tests -q
python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/renderer/tests packages/spec/tests packages/workflow/tests -q
git diff --check
```

5. Push branch.
6. Provide PR title and body.

Suggested PR title:

```text
feat: add handwriting style lab reference artifacts
```

Suggested PR body:

```markdown
## Summary
- Add `tools/style_lab` for deterministic generation of handwriting reference manifests, metrics, contact sheets, and style token skeletons.
- Record the approved `default_pretty_handwriting v1` calibration contract in the preset metadata and product docs.
- Add fixture-based tests that do not depend on local `/image` files while still exercising composite math-solution-like images.

## Test Plan
- [ ] `python -m pytest tools/style_lab/tests -q`
- [ ] `python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/renderer/tests packages/spec/tests packages/workflow/tests -q`
- [ ] `python -m tools.style_lab.cli build --image-root image/clean_solutions --output-root image/style-lab/default_pretty_handwriting/v1`
- [ ] `git diff --check`
```
