# MVP Dataset Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only dataset preparation tool that turns the user-provided `image/` folder into pilot problem-level samples for M2, without committing large images.

**Architecture:** Add a small `tools/datasets` Python package with focused modules for inventory validation, PDF pair mapping, image matching, metadata writing, and contact sheet generation. The script writes generated images only under `var/datasets/**`, which remains ignored, and uses a pilot-first workflow so 147-way matching is not trusted before visual review.

**Tech Stack:** Python 3.13, pytest, Pydantic-free dataclasses, Pillow, OpenCV, numpy, PyMuPDF for local PDF rendering, browser companion for pilot contact sheet review.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-06-15-mvp-dataset-preparation-design.md`
- Current input root: `image/`
- Existing ignore file: `.gitignore`
- Existing pytest config: `pyproject.toml`

## Scope Rules

Do not commit any file under:

- `image/`
- `var/datasets/`
- `.superpowers/`

Do not implement:

- M2 candidate spec generation
- OpenAI/OCR matching
- web upload UI
- export
- automatic full 147-sample approval

## File Structure

Create:

- `tools/datasets/requirements.txt`
  - Dataset preparation-only dependencies.
- `tools/datasets/cleansolve_dataset/__init__.py`
  - Empty package marker.
- `tools/datasets/cleansolve_dataset/models.py`
  - Shared dataclasses, constants, confidence classification, metadata serialization.
- `tools/datasets/cleansolve_dataset/inventory.py`
  - Input folder scanning, numbered PNG validation, fixed PDF pair mapping, page count validation.
- `tools/datasets/cleansolve_dataset/matching.py`
  - Grayscale conversion, template scale candidates, OpenCV matching, bbox padding/clamping, abnormal crop checks.
- `tools/datasets/cleansolve_dataset/rendering.py`
  - PyMuPDF import guard and PDF page rendering.
- `tools/datasets/cleansolve_dataset/preparation.py`
  - Pilot/full orchestration and sample directory writing.
- `tools/datasets/prepare_mvp_dataset.py`
  - CLI entry point.
- `tools/datasets/tests/test_inventory.py`
- `tools/datasets/tests/test_matching.py`
- `tools/datasets/tests/test_metadata.py`
- `tools/datasets/tests/test_preparation.py`

Modify:

- `.gitignore`
  - Add `/image/` and `/.superpowers/`.
- `pyproject.toml`
  - Add `tools/datasets/tests` to `testpaths`.
  - Add `tools/datasets` to `pythonpath`.

Do not modify:

- `apps/**`
- `packages/**`
- `fixtures/manual/**`
- `docs/product/mvp-roadmap.md`

## Constants

Use these exact constants in `tools/datasets/cleansolve_dataset/models.py`:

```python
PILOT_INDICES = (1, 2, 3, 10, 20, 30, 50, 80, 110, 147)
TOTAL_SAMPLE_COUNT = 147
RENDER_DPI = 200
BBOX_PADDING_PX = 24
TEMPLATE_SCALES = (0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15)
HIGH_CONFIDENCE_THRESHOLD = 0.86
MEDIUM_CONFIDENCE_THRESHOLD = 0.72
AMBIGUOUS_SCORE_DELTA = 0.01
MIN_CROP_WIDTH_RATIO = 0.15
MIN_CROP_HEIGHT_RATIO = 0.08
MAX_CROP_WIDTH_RATIO = 0.95
MAX_CROP_HEIGHT_RATIO = 0.95
```

Use this exact PDF pair mapping in `inventory.py`:

```python
PDF_PAIR_NAMES = {
    "기말1.pdf": "기말1 원본.pdf",
    "기말2.pdf": "기말2 원본.pdf",
    "기말3 .pdf": "기말3 원본.pdf",
    "미적분3단원.pdf": "미적분3단원 원본.pdf",
    "미적분4단원.pdf": "미적분4단원 원본.pdf",
}
```

## Task 1: Ignore Local Dataset Inputs And Wire Test Paths

**Files:**

- Modify: `.gitignore`
- Modify: `pyproject.toml`
- Create: `tools/datasets/requirements.txt`

- [ ] **Step 1: Add local dataset ignores**

Update `.gitignore` by appending these exact lines if they do not already exist:

```gitignore
/image/
/.superpowers/
```

- [ ] **Step 2: Add dataset test path and pythonpath**

Update `pyproject.toml`.

Expected final pytest sections:

```toml
[tool.pytest.ini_options]
testpaths = [
  "apps/api/tests",
  "packages/ai/tests",
  "packages/harness/tests",
  "packages/renderer/tests",
  "packages/spec/tests",
  "packages/workflow/tests",
  "tools/datasets/tests",
]
pythonpath = [
  "apps/api",
  "packages/ai",
  "packages/harness",
  "packages/renderer",
  "packages/spec",
  "packages/workflow",
  "tools/datasets",
]
```

- [ ] **Step 3: Add dataset-only requirements file**

Create `tools/datasets/requirements.txt` with exactly:

```text
pymupdf
pillow
opencv-python
numpy
```

- [ ] **Step 4: Verify ignore behavior**

Run:

```bash
git check-ignore image image/original_pages .superpowers
git status --short image | head
```

Expected:

- `git check-ignore` prints the three ignored paths.
- `git status --short image | head` prints nothing.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add .gitignore pyproject.toml tools/datasets/requirements.txt
git commit -m "chore(dataset): ignore local image inputs"
```

## Task 2: Dataset Models And Metadata Serialization

**Files:**

- Create: `tools/datasets/cleansolve_dataset/__init__.py`
- Create: `tools/datasets/cleansolve_dataset/models.py`
- Create: `tools/datasets/tests/test_metadata.py`

- [ ] **Step 1: Write failing metadata tests**

Create `tools/datasets/tests/test_metadata.py`:

```python
from pathlib import Path

from cleansolve_dataset.models import (
    BBox,
    MatchMetadata,
    MatchResult,
    classify_confidence,
    metadata_to_json_dict,
    review_required_for_confidence,
)


def test_classify_confidence_uses_fixed_thresholds():
    assert classify_confidence(0.86) == "high"
    assert classify_confidence(0.72) == "medium"
    assert classify_confidence(0.71) == "low"


def test_review_required_only_false_for_high_confidence():
    assert review_required_for_confidence("high") is False
    assert review_required_for_confidence("medium") is True
    assert review_required_for_confidence("low") is True


def test_metadata_to_json_dict_has_exact_shape():
    metadata = MatchMetadata(
        sample_id="sample_001",
        source_index=1,
        teacher_solution_file=Path("image/teacher_solutions/B_001.png"),
        clean_solution_file=Path("image/clean_solutions/GT_001.png"),
        matched_source_pdf=Path("image/clean_solution_pages/기말1.pdf"),
        matched_original_pdf=Path("image/original_pages/기말1 원본.pdf"),
        matched_page_index=0,
        problem_bbox=BBox(x=12, y=24, width=300, height=400),
        matching=MatchResult(
            method="clean_solution_template_match",
            score=0.94,
            confidence="high",
            review_required=False,
            reason=None,
        ),
    )

    assert metadata_to_json_dict(metadata) == {
        "sample_id": "sample_001",
        "source_index": 1,
        "teacher_solution_file": "image/teacher_solutions/B_001.png",
        "clean_solution_file": "image/clean_solutions/GT_001.png",
        "matched_source_pdf": "image/clean_solution_pages/기말1.pdf",
        "matched_original_pdf": "image/original_pages/기말1 원본.pdf",
        "matched_page_index": 0,
        "problem_bbox": {
            "x": 12,
            "y": 24,
            "width": 300,
            "height": 400,
        },
        "matching": {
            "method": "clean_solution_template_match",
            "score": 0.94,
            "confidence": "high",
            "review_required": False,
            "reason": None,
        },
    }
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tools/datasets/tests/test_metadata.py -q
```

Expected:

- Collection fails because `cleansolve_dataset.models` does not exist.

- [ ] **Step 3: Implement models**

Create empty `tools/datasets/cleansolve_dataset/__init__.py`.

Create `tools/datasets/cleansolve_dataset/models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

Confidence = Literal["high", "medium", "low"]

PILOT_INDICES = (1, 2, 3, 10, 20, 30, 50, 80, 110, 147)
TOTAL_SAMPLE_COUNT = 147
RENDER_DPI = 200
BBOX_PADDING_PX = 24
TEMPLATE_SCALES = (0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15)
HIGH_CONFIDENCE_THRESHOLD = 0.86
MEDIUM_CONFIDENCE_THRESHOLD = 0.72
AMBIGUOUS_SCORE_DELTA = 0.01
MIN_CROP_WIDTH_RATIO = 0.15
MIN_CROP_HEIGHT_RATIO = 0.08
MAX_CROP_WIDTH_RATIO = 0.95
MAX_CROP_HEIGHT_RATIO = 0.95


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class MatchResult:
    method: str
    score: float
    confidence: Confidence
    review_required: bool
    reason: str | None


@dataclass(frozen=True)
class MatchMetadata:
    sample_id: str
    source_index: int
    teacher_solution_file: Path
    clean_solution_file: Path
    matched_source_pdf: Path
    matched_original_pdf: Path
    matched_page_index: int
    problem_bbox: BBox
    matching: MatchResult


def classify_confidence(score: float) -> Confidence:
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def review_required_for_confidence(confidence: Confidence) -> bool:
    return confidence != "high"


def _json_ready(value):
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def metadata_to_json_dict(metadata: MatchMetadata) -> dict[str, object]:
    return _json_ready(asdict(metadata))
```

- [ ] **Step 4: Run metadata tests and verify GREEN**

Run:

```bash
python -m pytest tools/datasets/tests/test_metadata.py -q
```

Expected:

- `3 passed`.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add tools/datasets/cleansolve_dataset/__init__.py tools/datasets/cleansolve_dataset/models.py tools/datasets/tests/test_metadata.py
git commit -m "feat(dataset): add metadata models"
```

## Task 3: Input Inventory Validation

**Files:**

- Create: `tools/datasets/cleansolve_dataset/inventory.py`
- Create: `tools/datasets/tests/test_inventory.py`

- [ ] **Step 1: Write failing inventory tests**

Create `tools/datasets/tests/test_inventory.py`:

```python
from pathlib import Path

import pytest

from cleansolve_dataset.inventory import (
    DatasetInputError,
    PDF_PAIR_NAMES,
    collect_numbered_pngs,
    expected_numbered_png_name,
    validate_required_input_dirs,
)


def test_expected_numbered_png_name_formats_three_digits():
    assert expected_numbered_png_name("B", 1) == "B_001.png"
    assert expected_numbered_png_name("GT", 147) == "GT_147.png"


def test_collect_numbered_pngs_requires_complete_sequence(tmp_path):
    folder = tmp_path / "teacher_solutions"
    folder.mkdir()
    for index in (1, 2, 4):
        (folder / expected_numbered_png_name("B", index)).write_bytes(b"png")

    with pytest.raises(DatasetInputError) as exc_info:
        collect_numbered_pngs(folder, "B", expected_count=4)

    assert "missing files: B_003.png" in str(exc_info.value)


def test_collect_numbered_pngs_returns_paths_by_index(tmp_path):
    folder = tmp_path / "clean_solutions"
    folder.mkdir()
    for index in (1, 2, 3):
        (folder / expected_numbered_png_name("GT", index)).write_bytes(b"png")

    result = collect_numbered_pngs(folder, "GT", expected_count=3)

    assert list(result) == [1, 2, 3]
    assert result[2] == folder / "GT_002.png"


def test_validate_required_input_dirs_rejects_missing_folder(tmp_path):
    (tmp_path / "original_pages").mkdir()
    (tmp_path / "clean_solution_pages").mkdir()
    (tmp_path / "teacher_solutions").mkdir()

    with pytest.raises(DatasetInputError) as exc_info:
        validate_required_input_dirs(tmp_path)

    assert "clean_solutions" in str(exc_info.value)


def test_pdf_pair_names_are_fixed():
    assert PDF_PAIR_NAMES == {
        "기말1.pdf": "기말1 원본.pdf",
        "기말2.pdf": "기말2 원본.pdf",
        "기말3 .pdf": "기말3 원본.pdf",
        "미적분3단원.pdf": "미적분3단원 원본.pdf",
        "미적분4단원.pdf": "미적분4단원 원본.pdf",
    }
```

- [ ] **Step 2: Run inventory tests and verify RED**

Run:

```bash
python -m pytest tools/datasets/tests/test_inventory.py -q
```

Expected:

- Collection fails because `cleansolve_dataset.inventory` does not exist.

- [ ] **Step 3: Implement inventory helpers**

Create `tools/datasets/cleansolve_dataset/inventory.py`:

```python
from __future__ import annotations

from pathlib import Path

from .models import TOTAL_SAMPLE_COUNT

PDF_PAIR_NAMES = {
    "기말1.pdf": "기말1 원본.pdf",
    "기말2.pdf": "기말2 원본.pdf",
    "기말3 .pdf": "기말3 원본.pdf",
    "미적분3단원.pdf": "미적분3단원 원본.pdf",
    "미적분4단원.pdf": "미적분4단원 원본.pdf",
}

REQUIRED_INPUT_DIRS = (
    "original_pages",
    "clean_solution_pages",
    "teacher_solutions",
    "clean_solutions",
)


class DatasetInputError(RuntimeError):
    pass


def expected_numbered_png_name(prefix: str, index: int) -> str:
    return f"{prefix}_{index:03d}.png"


def validate_required_input_dirs(input_root: Path) -> None:
    missing = [
        folder_name
        for folder_name in REQUIRED_INPUT_DIRS
        if not (input_root / folder_name).is_dir()
    ]
    if missing:
        raise DatasetInputError(f"missing required input directories: {', '.join(missing)}")


def collect_numbered_pngs(
    folder: Path,
    prefix: str,
    expected_count: int = TOTAL_SAMPLE_COUNT,
) -> dict[int, Path]:
    files_by_index: dict[int, Path] = {}
    missing_names: list[str] = []
    for index in range(1, expected_count + 1):
        name = expected_numbered_png_name(prefix, index)
        path = folder / name
        if not path.exists():
            missing_names.append(name)
        else:
            files_by_index[index] = path

    if missing_names:
        raise DatasetInputError(f"missing files: {', '.join(missing_names)}")

    return files_by_index
```

- [ ] **Step 4: Run inventory tests and verify GREEN**

Run:

```bash
python -m pytest tools/datasets/tests/test_inventory.py -q
```

Expected:

- `5 passed`.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add tools/datasets/cleansolve_dataset/inventory.py tools/datasets/tests/test_inventory.py
git commit -m "feat(dataset): validate input inventory"
```

## Task 4: Image Matching Helpers

**Files:**

- Create: `tools/datasets/cleansolve_dataset/matching.py`
- Create: `tools/datasets/tests/test_matching.py`

- [ ] **Step 1: Write failing matching tests**

Create `tools/datasets/tests/test_matching.py`:

```python
import numpy as np

from cleansolve_dataset.matching import (
    apply_padding_and_clamp,
    crop_is_abnormal,
    find_template_match,
)
from cleansolve_dataset.models import BBox


def test_apply_padding_and_clamp_stays_inside_page():
    padded = apply_padding_and_clamp(
        BBox(x=5, y=10, width=50, height=60),
        page_width=100,
        page_height=120,
        padding=24,
    )

    assert padded == BBox(x=0, y=0, width=79, height=94)


def test_crop_is_abnormal_for_too_small_and_too_large_boxes():
    assert crop_is_abnormal(BBox(0, 0, 10, 100), page_width=1000, page_height=1000)
    assert crop_is_abnormal(BBox(0, 0, 990, 100), page_width=1000, page_height=1000)
    assert not crop_is_abnormal(BBox(0, 0, 400, 300), page_width=1000, page_height=1000)


def test_find_template_match_finds_synthetic_template_location():
    page = np.zeros((120, 160), dtype=np.uint8)
    template = np.zeros((20, 30), dtype=np.uint8)
    template[5:15, 8:22] = 255
    page[40:60, 70:100] = template

    result = find_template_match(page, template, scales=(1.0,))

    assert result.bbox == BBox(x=70, y=40, width=30, height=20)
    assert result.score > 0.99
    assert result.scale == 1.0
```

- [ ] **Step 2: Run matching tests and verify RED**

Run:

```bash
python -m pytest tools/datasets/tests/test_matching.py -q
```

Expected:

- Collection fails because `cleansolve_dataset.matching` does not exist.

- [ ] **Step 3: Implement matching helpers**

Create `tools/datasets/cleansolve_dataset/matching.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .models import (
    BBOX_PADDING_PX,
    MAX_CROP_HEIGHT_RATIO,
    MAX_CROP_WIDTH_RATIO,
    MIN_CROP_HEIGHT_RATIO,
    MIN_CROP_WIDTH_RATIO,
    TEMPLATE_SCALES,
    BBox,
)


@dataclass(frozen=True)
class TemplateMatch:
    bbox: BBox
    score: float
    second_best_score: float | None
    scale: float


def apply_padding_and_clamp(
    bbox: BBox,
    page_width: int,
    page_height: int,
    padding: int = BBOX_PADDING_PX,
) -> BBox:
    x0 = max(0, bbox.x - padding)
    y0 = max(0, bbox.y - padding)
    x1 = min(page_width, bbox.x + bbox.width + padding)
    y1 = min(page_height, bbox.y + bbox.height + padding)
    return BBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0)


def crop_is_abnormal(bbox: BBox, page_width: int, page_height: int) -> bool:
    width_ratio = bbox.width / page_width
    height_ratio = bbox.height / page_height
    return (
        width_ratio < MIN_CROP_WIDTH_RATIO
        or height_ratio < MIN_CROP_HEIGHT_RATIO
        or width_ratio > MAX_CROP_WIDTH_RATIO
        or height_ratio > MAX_CROP_HEIGHT_RATIO
    )


def to_grayscale_array(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


def _resize_template(template: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return template
    width = max(1, round(template.shape[1] * scale))
    height = max(1, round(template.shape[0] * scale))
    return cv2.resize(template, (width, height), interpolation=cv2.INTER_AREA)


def find_template_match(
    page: np.ndarray,
    template: np.ndarray,
    scales: tuple[float, ...] = TEMPLATE_SCALES,
) -> TemplateMatch:
    page_gray = to_grayscale_array(page)
    template_gray = to_grayscale_array(template)
    candidates: list[TemplateMatch] = []

    for scale in scales:
        scaled_template = _resize_template(template_gray, scale)
        template_height, template_width = scaled_template.shape[:2]
        page_height, page_width = page_gray.shape[:2]
        if template_width > page_width or template_height > page_height:
            continue

        result = cv2.matchTemplate(page_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
        _, max_value, _, max_location = cv2.minMaxLoc(result)
        candidates.append(
            TemplateMatch(
                bbox=BBox(
                    x=int(max_location[0]),
                    y=int(max_location[1]),
                    width=int(template_width),
                    height=int(template_height),
                ),
                score=float(max_value),
                second_best_score=None,
                scale=scale,
            )
        )

    if not candidates:
        raise ValueError("template does not fit inside page at any configured scale")

    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    best = candidates[0]
    second_best = candidates[1].score if len(candidates) > 1 else None
    return TemplateMatch(
        bbox=best.bbox,
        score=best.score,
        second_best_score=second_best,
        scale=best.scale,
    )
```

- [ ] **Step 4: Run matching tests and verify GREEN**

Run:

```bash
python -m pytest tools/datasets/tests/test_matching.py -q
```

Expected:

- `3 passed`.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add tools/datasets/cleansolve_dataset/matching.py tools/datasets/tests/test_matching.py
git commit -m "feat(dataset): add template matching helpers"
```

## Task 5: Rendering Guard And Preparation Orchestrator

**Files:**

- Create: `tools/datasets/cleansolve_dataset/rendering.py`
- Create: `tools/datasets/cleansolve_dataset/preparation.py`
- Create: `tools/datasets/tests/test_preparation.py`

- [ ] **Step 1: Write failing preparation tests**

Create `tools/datasets/tests/test_preparation.py`:

```python
from pathlib import Path

from PIL import Image

from cleansolve_dataset.models import PILOT_INDICES
from cleansolve_dataset.preparation import (
    output_bucket_for_review_required,
    sample_directory_name,
    select_indices_for_mode,
    write_sample_files,
)


def test_select_indices_for_mode_uses_fixed_pilot_subset():
    assert select_indices_for_mode("pilot") == PILOT_INDICES
    assert select_indices_for_mode("full") == tuple(range(1, 148))


def test_sample_directory_name_uses_three_digits():
    assert sample_directory_name(1) == "sample_001"
    assert sample_directory_name(147) == "sample_147"


def test_output_bucket_for_review_required():
    assert output_bucket_for_review_required(False) == "mvp_samples"
    assert output_bucket_for_review_required(True) == "mvp_review_needed"


def test_write_sample_files_creates_expected_files(tmp_path):
    original_page = Image.new("RGB", (20, 20), "white")
    clean_page = Image.new("RGB", (20, 20), "white")
    problem_crop = Image.new("RGB", (10, 10), "white")
    teacher_path = tmp_path / "B_001.png"
    clean_path = tmp_path / "GT_001.png"
    Image.new("RGB", (10, 10), "white").save(teacher_path)
    Image.new("RGB", (10, 10), "white").save(clean_path)
    metadata = {"sample_id": "sample_001", "matching": {"review_required": False}}

    output_dir = write_sample_files(
        output_root=tmp_path / "out",
        sample_index=1,
        review_required=False,
        original_page=original_page,
        clean_solution_page=clean_page,
        problem_crop=problem_crop,
        teacher_solution_path=teacher_path,
        clean_solution_path=clean_path,
        metadata=metadata,
    )

    assert output_dir.name == "sample_001"
    assert (output_dir / "original_page.png").exists()
    assert (output_dir / "clean_solution_page.png").exists()
    assert (output_dir / "problem_crop.png").exists()
    assert (output_dir / "teacher_solution.png").exists()
    assert (output_dir / "clean_solution.png").exists()
    assert (output_dir / "metadata.json").exists()
```

- [ ] **Step 2: Run preparation tests and verify RED**

Run:

```bash
python -m pytest tools/datasets/tests/test_preparation.py -q
```

Expected:

- Collection fails because `cleansolve_dataset.preparation` does not exist.

- [ ] **Step 3: Implement rendering import guard**

Create `tools/datasets/cleansolve_dataset/rendering.py`:

```python
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .models import RENDER_DPI


class DatasetDependencyError(RuntimeError):
    pass


def require_fitz():
    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise DatasetDependencyError(
            "PyMuPDF is required. Run: python -m pip install -r tools/datasets/requirements.txt"
        ) from exc
    return fitz


def render_pdf_pages(pdf_path: Path, dpi: int = RENDER_DPI) -> list[Image.Image]:
    fitz = require_fitz()
    document = fitz.open(pdf_path)
    pages: list[Image.Image] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    try:
        for page in document:
            pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            pages.append(image)
    finally:
        document.close()
    return pages
```

- [ ] **Step 4: Implement preparation helpers**

Create `tools/datasets/cleansolve_dataset/preparation.py`:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

from PIL import Image

from .models import PILOT_INDICES, TOTAL_SAMPLE_COUNT

Mode = Literal["pilot", "full"]


def select_indices_for_mode(mode: Mode) -> tuple[int, ...]:
    if mode == "pilot":
        return PILOT_INDICES
    if mode == "full":
        return tuple(range(1, TOTAL_SAMPLE_COUNT + 1))
    raise ValueError(f"unsupported mode: {mode}")


def sample_directory_name(sample_index: int) -> str:
    return f"sample_{sample_index:03d}"


def output_bucket_for_review_required(review_required: bool) -> str:
    return "mvp_review_needed" if review_required else "mvp_samples"


def write_sample_files(
    output_root: Path,
    sample_index: int,
    review_required: bool,
    original_page: Image.Image,
    clean_solution_page: Image.Image,
    problem_crop: Image.Image,
    teacher_solution_path: Path,
    clean_solution_path: Path,
    metadata: dict[str, object],
) -> Path:
    bucket = output_bucket_for_review_required(review_required)
    output_dir = output_root / bucket / sample_directory_name(sample_index)
    output_dir.mkdir(parents=True, exist_ok=True)

    original_page.save(output_dir / "original_page.png")
    clean_solution_page.save(output_dir / "clean_solution_page.png")
    problem_crop.save(output_dir / "problem_crop.png")
    shutil.copy2(teacher_solution_path, output_dir / "teacher_solution.png")
    shutil.copy2(clean_solution_path, output_dir / "clean_solution.png")
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_dir
```

- [ ] **Step 5: Run preparation tests and verify GREEN**

Run:

```bash
python -m pytest tools/datasets/tests/test_preparation.py -q
```

Expected:

- `4 passed`.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add tools/datasets/cleansolve_dataset/rendering.py tools/datasets/cleansolve_dataset/preparation.py tools/datasets/tests/test_preparation.py
git commit -m "feat(dataset): add preparation helpers"
```

## Task 6: CLI Script And Pilot Execution

**Files:**

- Create: `tools/datasets/prepare_mvp_dataset.py`
- Modify: `tools/datasets/cleansolve_dataset/preparation.py`
- Test manually against `image/`

- [ ] **Step 1: Extend preparation module with real orchestration**

Append these functions to `tools/datasets/cleansolve_dataset/preparation.py`:

```python
import numpy as np

from .inventory import (
    PDF_PAIR_NAMES,
    collect_numbered_pngs,
    validate_required_input_dirs,
)
from .matching import (
    apply_padding_and_clamp,
    crop_is_abnormal,
    find_template_match,
)
from .models import (
    AMBIGUOUS_SCORE_DELTA,
    BBox,
    MatchMetadata,
    MatchResult,
    classify_confidence,
    metadata_to_json_dict,
    review_required_for_confidence,
)
from .rendering import render_pdf_pages
```

Then add:

```python
def _image_to_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"))


def _candidate_reason(confidence: str, ambiguous: bool, abnormal: bool) -> str | None:
    reasons: list[str] = []
    if confidence != "high":
        reasons.append("score_below_high_threshold")
    if ambiguous:
        reasons.append("ambiguous_top_scores")
    if abnormal:
        reasons.append("abnormal_crop_size")
    return ",".join(reasons) if reasons else None


def prepare_dataset(input_root: Path, output_root: Path, mode: Mode) -> list[Path]:
    validate_required_input_dirs(input_root)
    teacher_files = collect_numbered_pngs(input_root / "teacher_solutions", "B")
    clean_files = collect_numbered_pngs(input_root / "clean_solutions", "GT")
    indices = select_indices_for_mode(mode)

    rendered_clean_pages_by_name = {
        clean_pdf_name: render_pdf_pages(input_root / "clean_solution_pages" / clean_pdf_name)
        for clean_pdf_name in PDF_PAIR_NAMES
    }
    rendered_original_pages_by_name = {
        original_pdf_name: render_pdf_pages(input_root / "original_pages" / original_pdf_name)
        for original_pdf_name in PDF_PAIR_NAMES.values()
    }

    for clean_pdf_name, original_pdf_name in PDF_PAIR_NAMES.items():
        if len(rendered_clean_pages_by_name[clean_pdf_name]) != len(rendered_original_pages_by_name[original_pdf_name]):
            raise RuntimeError(f"page count mismatch: {clean_pdf_name} vs {original_pdf_name}")

    output_dirs: list[Path] = []
    for index in indices:
        template = Image.open(clean_files[index]).convert("RGB")
        template_array = _image_to_array(template)
        best = None
        best_clean_pdf_name = None
        best_page_index = None
        best_clean_page = None

        for clean_pdf_name, pages in rendered_clean_pages_by_name.items():
            for page_index, page_image in enumerate(pages):
                match = find_template_match(_image_to_array(page_image), template_array)
                if best is None or match.score > best.score:
                    best = match
                    best_clean_pdf_name = clean_pdf_name
                    best_page_index = page_index
                    best_clean_page = page_image

        if best is None or best_clean_pdf_name is None or best_page_index is None or best_clean_page is None:
            raise RuntimeError(f"no template match found for GT_{index:03d}.png")

        original_pdf_name = PDF_PAIR_NAMES[best_clean_pdf_name]
        original_page = rendered_original_pages_by_name[original_pdf_name][best_page_index]
        padded_bbox = apply_padding_and_clamp(
            best.bbox,
            page_width=original_page.width,
            page_height=original_page.height,
        )
        problem_crop = original_page.crop(
            (
                padded_bbox.x,
                padded_bbox.y,
                padded_bbox.x + padded_bbox.width,
                padded_bbox.y + padded_bbox.height,
            )
        )
        confidence = classify_confidence(best.score)
        ambiguous = (
            best.second_best_score is not None
            and best.score - best.second_best_score < AMBIGUOUS_SCORE_DELTA
        )
        abnormal = crop_is_abnormal(padded_bbox, original_page.width, original_page.height)
        review_required = (
            review_required_for_confidence(confidence)
            or ambiguous
            or abnormal
        )
        reason = _candidate_reason(confidence, ambiguous, abnormal)
        metadata = MatchMetadata(
            sample_id=sample_directory_name(index),
            source_index=index,
            teacher_solution_file=teacher_files[index],
            clean_solution_file=clean_files[index],
            matched_source_pdf=input_root / "clean_solution_pages" / best_clean_pdf_name,
            matched_original_pdf=input_root / "original_pages" / original_pdf_name,
            matched_page_index=best_page_index,
            problem_bbox=padded_bbox,
            matching=MatchResult(
                method="clean_solution_template_match",
                score=round(best.score, 6),
                confidence=confidence,
                review_required=review_required,
                reason=reason,
            ),
        )
        output_dirs.append(
            write_sample_files(
                output_root=output_root,
                sample_index=index,
                review_required=review_required,
                original_page=original_page,
                clean_solution_page=best_clean_page,
                problem_crop=problem_crop,
                teacher_solution_path=teacher_files[index],
                clean_solution_path=clean_files[index],
                metadata=metadata_to_json_dict(metadata),
            )
        )

    return output_dirs
```

- [ ] **Step 2: Create CLI entry point**

Create `tools/datasets/prepare_mvp_dataset.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from cleansolve_dataset.preparation import prepare_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare local MVP image dataset samples.")
    parser.add_argument("--mode", choices=("pilot", "full"), required=True)
    parser.add_argument("--input-root", default="image")
    parser.add_argument("--output-root", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = (
        Path(args.output_root)
        if args.output_root
        else Path("var/datasets/pilot" if args.mode == "pilot" else "var/datasets/full")
    )
    output_dirs = prepare_dataset(
        input_root=Path(args.input_root),
        output_root=output_root,
        mode=args.mode,
    )
    print(f"wrote {len(output_dirs)} sample directories under {output_root}")
    for output_dir in output_dirs:
        print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run pilot command**

Run:

```bash
python tools/datasets/prepare_mvp_dataset.py --mode pilot
```

Expected:

- If PyMuPDF is missing, install with:

```bash
python -m pip install -r tools/datasets/requirements.txt
```

- Then rerun pilot command.
- Command prints `wrote 10 sample directories under var/datasets/pilot`.

- [ ] **Step 4: Inspect generated pilot files**

Run:

```bash
find var/datasets/pilot -maxdepth 3 -type f | sort | head -80
find var/datasets/pilot -name metadata.json | wc -l
```

Expected:

- Metadata count is `10`.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add tools/datasets/cleansolve_dataset/preparation.py tools/datasets/prepare_mvp_dataset.py
git commit -m "feat(dataset): generate pilot samples"
```

## Task 7: Pilot Contact Sheet

**Files:**

- Create: `tools/datasets/cleansolve_dataset/contact_sheet.py`
- Modify: `tools/datasets/prepare_mvp_dataset.py`
- Test manually with browser companion

- [ ] **Step 1: Implement contact sheet generator**

Create `tools/datasets/cleansolve_dataset/contact_sheet.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def generate_contact_sheet(samples_root: Path, output_path: Path) -> Path:
    metadata_paths = sorted(samples_root.glob("*/*/metadata.json"))
    rows: list[str] = []
    for metadata_path in metadata_paths:
        sample_dir = metadata_path.parent
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        matching = metadata["matching"]
        problem_crop_src = (sample_dir / "problem_crop.png").relative_to(output_path.parent).as_posix()
        teacher_src = (sample_dir / "teacher_solution.png").relative_to(output_path.parent).as_posix()
        clean_src = (sample_dir / "clean_solution.png").relative_to(output_path.parent).as_posix()
        rows.append(
            f"""
<section class="sample">
  <h2>{metadata["sample_id"]}</h2>
  <p>score={matching["score"]} confidence={matching["confidence"]} review_required={matching["review_required"]} reason={matching["reason"]}</p>
  <div class="grid">
    <figure><img src="{problem_crop_src}"><figcaption>problem_crop</figcaption></figure>
    <figure><img src="{teacher_src}"><figcaption>teacher_solution</figcaption></figure>
    <figure><img src="{clean_src}"><figcaption>clean_solution</figcaption></figure>
  </div>
</section>
"""
        )

    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>MVP Dataset Pilot Contact Sheet</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; }}
    .sample {{ border-top: 1px solid #ddd; padding: 18px 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; align-items: start; }}
    img {{ max-width: 100%; border: 1px solid #ddd; background: white; }}
    figcaption {{ margin-top: 6px; color: #555; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>MVP Dataset Pilot Contact Sheet</h1>
  {''.join(rows)}
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
```

- [ ] **Step 2: Add CLI flag**

Modify `tools/datasets/prepare_mvp_dataset.py`:

```python
from cleansolve_dataset.contact_sheet import generate_contact_sheet
```

Add argument:

```python
parser.add_argument("--contact-sheet", action="store_true")
```

After `prepare_dataset(...)`, add:

```python
    if args.contact_sheet:
        contact_sheet_path = generate_contact_sheet(output_root, output_root / "contact_sheet.html")
        print(f"contact sheet: {contact_sheet_path}")
```

- [ ] **Step 3: Generate pilot contact sheet**

Run:

```bash
python tools/datasets/prepare_mvp_dataset.py --mode pilot --contact-sheet
```

Expected:

- Prints `contact sheet: var/datasets/pilot/contact_sheet.html`.
- File exists.

- [ ] **Step 4: Open contact sheet in browser companion**

Use the browser companion or local browser to inspect:

```text
var/datasets/pilot/contact_sheet.html
```

Expected:

- 10 sample rows are visible.
- Each row shows `problem_crop`, `teacher_solution`, and `clean_solution`.
- Do not run `--mode full` yet.

- [ ] **Step 5: Commit Task 7**

Run:

```bash
git add tools/datasets/cleansolve_dataset/contact_sheet.py tools/datasets/prepare_mvp_dataset.py
git commit -m "feat(dataset): add pilot contact sheet"
```

## Task 8: Final Verification And Handoff

**Files:**

- No code changes unless verification exposes a defect.

- [ ] **Step 1: Run full Python tests**

Run:

```bash
python -m pytest -q
```

Expected:

- All tests pass.

- [ ] **Step 2: Run dataset pilot smoke command**

Run:

```bash
python tools/datasets/prepare_mvp_dataset.py --mode pilot --contact-sheet
```

Expected:

- 10 sample directories are generated under `var/datasets/pilot`.
- `var/datasets/pilot/contact_sheet.html` exists.

- [ ] **Step 3: Verify ignored large data is not staged**

Run:

```bash
git status --short image var/datasets .superpowers
git check-ignore image var/datasets .superpowers
```

Expected:

- `git status --short ...` prints nothing.
- `git check-ignore` prints all paths.

- [ ] **Step 4: Run diff checks**

Run:

```bash
git diff --check
git diff --check origin/feat/mvp-roadmap..HEAD
```

Expected:

- Both commands exit 0.

- [ ] **Step 5: Stop before full dataset processing**

Do not run:

```bash
python tools/datasets/prepare_mvp_dataset.py --mode full
```

Instead, report:

```text
Pilot dataset preparation complete.
Please review `var/datasets/pilot/contact_sheet.html`.
Full 147-sample generation is intentionally blocked until pilot review.
```

## Plan Self-Review Checklist

- Spec coverage:
  - `/image/` and `/.superpowers/` ignore: Task 1.
  - Local-only output under `var/datasets`: Task 5 and Task 6.
  - metadata schema: Task 2 and Task 5.
  - fixed PDF mapping: Task 3.
  - PyMuPDF rendering: Task 5.
  - template matching thresholds/scales/padding: Task 4 and Task 6.
  - pilot-only first workflow: Task 6, Task 7, Task 8.
  - browser/contact sheet review: Task 7.
  - no full 147 auto-processing: Task 8.
- Placeholder scan:
  - No `TBD`, `TODO`, or "similar to" instructions.
- Type consistency:
  - `BBox`, `MatchResult`, `MatchMetadata`, `prepare_dataset`, `write_sample_files`, and CLI names match across tasks.
