#!/usr/bin/env python3
"""Local-only helper for matching user-provided MVP image samples.

This script is intentionally not part of the product runtime. It reads large
local files from image/ and writes generated review artifacts to var/datasets/.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from math import inf
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:
    import fitz
except ModuleNotFoundError:
    print(
        "PyMuPDF is required. Install it with: python -m pip install pymupdf",
        file=sys.stderr,
    )
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_ROOT = REPO_ROOT / "image"
OUTPUT_BASE = REPO_ROOT / "var" / "datasets"

PILOT_INDICES = (1, 2, 3, 10, 20, 30, 50, 80, 110, 147)
TOTAL_SAMPLE_COUNT = 147
RENDER_DPI = 200
SEARCH_DPI = 80
BBOX_PADDING_PX = 24
TEMPLATE_SCALES = (
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
    0.85,
    0.90,
    0.95,
    1.00,
    1.05,
    1.10,
    1.15,
)
HIGH_CONFIDENCE_THRESHOLD = 0.55
MEDIUM_CONFIDENCE_THRESHOLD = 0.35
AMBIGUOUS_SCORE_DELTA = 0.03

PDF_PAIR_NAMES = {
    "기말1.pdf": "기말1 원본.pdf",
    "기말2.pdf": "기말2 원본.pdf",
    "기말3 .pdf": "기말3 원본.pdf",
    "미적분3단원.pdf": "미적분3단원 원본.pdf",
    "미적분4단원.pdf": "미적분4단원 원본.pdf",
}


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    def padded(self, padding: int, page_width: int, page_height: int) -> "BBox":
        x0 = max(0, self.x - padding)
        y0 = max(0, self.y - padding)
        x1 = min(page_width, self.x + self.width + padding)
        y1 = min(page_height, self.y + self.height + padding)
        return BBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0)

    def scaled(self, scale_x: float, scale_y: float) -> "BBox":
        x = int(round(self.x * scale_x))
        y = int(round(self.y * scale_y))
        width = int(round(self.width * scale_x))
        height = int(round(self.height * scale_y))
        return BBox(x=x, y=y, width=width, height=height)

    def as_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class PdfPair:
    clean_pdf: Path
    original_pdf: Path
    page_count: int


@dataclass(frozen=True)
class MatchCandidate:
    score: float
    runner_up_score: float | None
    clean_pdf: Path
    original_pdf: Path
    page_index: int
    search_bbox: BBox
    search_page_size: tuple[int, int]
    scale: float

    @property
    def ambiguous(self) -> bool:
        if self.runner_up_score is None:
            return False
        return self.score - self.runner_up_score < AMBIGUOUS_SCORE_DELTA


def normalized_name(path: Path | str) -> str:
    return unicodedata.normalize("NFC", Path(path).name)


def find_file_by_normalized_name(folder: Path, expected_name: str) -> Path:
    expected = unicodedata.normalize("NFC", expected_name)
    matches: list[Path] = []
    for path in folder.iterdir():
        if normalized_name(path) == expected:
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise RuntimeError(f"Duplicate normalized filenames under {folder}: {names}")
    raise FileNotFoundError(f"Missing required file under {folder}: {expected_name}")


def pdf_page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as document:
        return int(document.page_count)


def load_pdf_pairs() -> list[PdfPair]:
    clean_folder = IMAGE_ROOT / "clean_solution_pages"
    original_folder = IMAGE_ROOT / "original_pages"
    pairs: list[PdfPair] = []

    for clean_name, original_name in PDF_PAIR_NAMES.items():
        clean_pdf = find_file_by_normalized_name(clean_folder, clean_name)
        original_pdf = find_file_by_normalized_name(original_folder, original_name)
        clean_count = pdf_page_count(clean_pdf)
        original_count = pdf_page_count(original_pdf)
        if clean_count != original_count:
            raise ValueError(
                f"Page count mismatch: {clean_pdf.name}={clean_count}, "
                f"{original_pdf.name}={original_count}"
            )
        pairs.append(
            PdfPair(
                clean_pdf=clean_pdf,
                original_pdf=original_pdf,
                page_count=clean_count,
            )
        )

    return pairs


def render_pdf_page(pdf_path: Path, page_index: int, dpi: int = RENDER_DPI) -> Image.Image:
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as document:
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return Image.frombytes(
            "RGB",
            (pixmap.width, pixmap.height),
            pixmap.samples,
        )


def load_rgb_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def to_gray(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)


def to_foreground_mask(image: Image.Image) -> np.ndarray:
    gray = to_gray(image)
    _, mask = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
    return mask


def resize_gray(gray: np.ndarray, scale: float) -> np.ndarray:
    height, width = gray.shape[:2]
    next_width = max(1, int(round(width * scale)))
    next_height = max(1, int(round(height * scale)))
    return cv2.resize(gray, (next_width, next_height), interpolation=cv2.INTER_AREA)


def match_template_on_page(page_gray: np.ndarray, template_gray: np.ndarray) -> tuple[float, BBox, float] | None:
    page_height, page_width = page_gray.shape[:2]
    best: tuple[float, BBox, float] | None = None

    for scale in TEMPLATE_SCALES:
        candidate_template = resize_gray(template_gray, scale)
        template_height, template_width = candidate_template.shape[:2]
        if template_width > page_width or template_height > page_height:
            continue

        result = cv2.matchTemplate(page_gray, candidate_template, cv2.TM_CCOEFF_NORMED)
        _, max_value, _, max_location = cv2.minMaxLoc(result)
        bbox = BBox(
            x=int(max_location[0]),
            y=int(max_location[1]),
            width=int(template_width),
            height=int(template_height),
        )
        if best is None or max_value > best[0]:
            best = (float(max_value), bbox, scale)

    return best


def find_best_match(index: int, gt_image: Image.Image, pdf_pairs: list[PdfPair]) -> MatchCandidate:
    search_ratio = SEARCH_DPI / RENDER_DPI
    template_width = max(1, int(round(gt_image.width * search_ratio)))
    template_height = max(1, int(round(gt_image.height * search_ratio)))
    search_template = gt_image.resize(
        (template_width, template_height),
        resample=Image.Resampling.LANCZOS,
    )
    template_gray = to_foreground_mask(search_template)
    best_match: MatchCandidate | None = None
    runner_up_score = -inf

    for pair in pdf_pairs:
        for page_index in range(pair.page_count):
            page_image = render_pdf_page(pair.clean_pdf, page_index, dpi=SEARCH_DPI)
            page_gray = to_foreground_mask(page_image)
            match = match_template_on_page(page_gray, template_gray)
            if match is None:
                continue

            score, bbox, scale = match
            if best_match is None or score > best_match.score:
                if best_match is not None:
                    runner_up_score = max(runner_up_score, best_match.score)
                best_match = MatchCandidate(
                    score=score,
                    runner_up_score=None,
                    clean_pdf=pair.clean_pdf,
                    original_pdf=pair.original_pdf,
                    page_index=page_index,
                    search_bbox=bbox,
                    search_page_size=page_image.size,
                    scale=scale,
                )
            else:
                runner_up_score = max(runner_up_score, score)

    if best_match is None:
        raise RuntimeError(f"No match candidate found for GT_{index:03d}.png")

    best_match = MatchCandidate(
        score=best_match.score,
        runner_up_score=None if runner_up_score == -inf else runner_up_score,
        clean_pdf=best_match.clean_pdf,
        original_pdf=best_match.original_pdf,
        page_index=best_match.page_index,
        search_bbox=best_match.search_bbox,
        search_page_size=best_match.search_page_size,
        scale=best_match.scale,
    )
    return best_match


def confidence_for(score: float) -> str:
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def relative_repo_path(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def sample_indices_for_mode(mode: str) -> tuple[int, ...]:
    if mode == "pilot":
        return PILOT_INDICES
    return tuple(range(1, TOTAL_SAMPLE_COUNT + 1))


def prepare_temp_output_folder(mode: str) -> tuple[Path, Path]:
    if OUTPUT_BASE.parent.exists() and OUTPUT_BASE.parent.is_symlink():
        raise RuntimeError(f"Refusing to write through symlinked output parent: {OUTPUT_BASE.parent}")
    if OUTPUT_BASE.exists() and OUTPUT_BASE.is_symlink():
        raise RuntimeError(f"Refusing to write through symlinked output folder: {OUTPUT_BASE}")

    output_root = OUTPUT_BASE / mode
    temp_root = OUTPUT_BASE / f".{mode}.tmp"

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    resolved_base = OUTPUT_BASE.resolve()
    resolved_repo = REPO_ROOT.resolve()
    if not resolved_base.is_relative_to(resolved_repo):
        raise RuntimeError(f"Refusing to write outside repository: {OUTPUT_BASE}")
    if temp_root.exists():
        if temp_root.is_symlink():
            raise RuntimeError(f"Refusing to delete symlinked temp folder: {temp_root}")
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)
    return output_root, temp_root


def replace_output_folder(output_root: Path, temp_root: Path) -> None:
    if output_root.exists():
        if output_root.is_symlink():
            raise RuntimeError(f"Refusing to replace symlinked output folder: {output_root}")
        shutil.rmtree(output_root)
    temp_root.rename(output_root)


def write_metadata(
    sample_dir: Path,
    index: int,
    match: MatchCandidate,
    original_bbox: BBox,
    confidence: str,
) -> None:
    metadata = {
        "sample_id": f"sample_{index:03d}",
        "source_index": index,
        "matched_clean_pdf": relative_repo_path(match.clean_pdf),
        "matched_original_pdf": relative_repo_path(match.original_pdf),
        "matched_page_index": match.page_index,
        "problem_bbox": original_bbox.as_dict(),
        "score": round(match.score, 6),
        "runner_up_score": (
            None if match.runner_up_score is None else round(match.runner_up_score, 6)
        ),
        "ambiguous": match.ambiguous,
        "confidence": confidence,
        "review_required": confidence != "high" or match.ambiguous,
        "template_scale": match.scale,
    }
    (sample_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_sample(
    output_root: Path,
    index: int,
    teacher_image: Image.Image,
    gt_image: Image.Image,
    match: MatchCandidate,
) -> Path:
    confidence = confidence_for(match.score)
    bucket = "samples" if confidence == "high" and not match.ambiguous else "review_needed"
    sample_dir = output_root / bucket / f"sample_{index:03d}"
    sample_dir.mkdir(parents=True, exist_ok=True)

    clean_page = render_pdf_page(match.clean_pdf, match.page_index)
    original_page = render_pdf_page(match.original_pdf, match.page_index)

    search_to_clean_x = clean_page.width / match.search_page_size[0]
    search_to_clean_y = clean_page.height / match.search_page_size[1]
    clean_bbox = match.search_bbox.scaled(search_to_clean_x, search_to_clean_y)

    clean_to_original_x = original_page.width / clean_page.width
    clean_to_original_y = original_page.height / clean_page.height
    original_bbox = clean_bbox.scaled(clean_to_original_x, clean_to_original_y).padded(
        BBOX_PADDING_PX,
        original_page.width,
        original_page.height,
    )
    crop_box = (
        original_bbox.x,
        original_bbox.y,
        original_bbox.x + original_bbox.width,
        original_bbox.y + original_bbox.height,
    )
    problem_crop = original_page.crop(crop_box)

    original_page.save(sample_dir / "original_page.png")
    clean_page.save(sample_dir / "clean_solution_page.png")
    problem_crop.save(sample_dir / "problem_crop.png")
    teacher_image.save(sample_dir / "teacher_solution.png")
    gt_image.save(sample_dir / "clean_solution.png")
    write_metadata(sample_dir, index, match, original_bbox, confidence)

    return sample_dir


def make_contact_sheet(output_root: Path, sample_dirs: list[Path]) -> None:
    rows: list[str] = []
    for sample_dir in sample_dirs:
        metadata = json.loads((sample_dir / "metadata.json").read_text(encoding="utf-8"))
        rel_dir = sample_dir.relative_to(output_root).as_posix()
        rows.append(
            "\n".join(
                [
                    "<section class=\"sample\">",
                    f"<h2>{html.escape(metadata['sample_id'])}</h2>",
                    "<p>"
                    f"score={metadata['score']} / "
                    f"confidence={html.escape(metadata['confidence'])} / "
                    f"page={metadata['matched_page_index'] + 1} / "
                    f"{html.escape(Path(metadata['matched_clean_pdf']).name)}"
                    "</p>",
                    "<div class=\"grid\">",
                    f"<figure><img src=\"{rel_dir}/problem_crop.png\"><figcaption>original crop</figcaption></figure>",
                    f"<figure><img src=\"{rel_dir}/teacher_solution.png\"><figcaption>teacher solution</figcaption></figure>",
                    f"<figure><img src=\"{rel_dir}/clean_solution.png\"><figcaption>clean solution</figcaption></figure>",
                    "</div>",
                    "</section>",
                ]
            )
        )

    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Clean Solve Studio Pilot Dataset Review</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 24px;
      color: #1f2933;
      background: #f7f8fa;
    }}
    h1 {{ margin-bottom: 8px; }}
    .sample {{
      border: 1px solid #d5dae1;
      background: white;
      margin: 18px 0;
      padding: 16px;
      border-radius: 8px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      align-items: start;
    }}
    figure {{ margin: 0; }}
    img {{
      display: block;
      max-width: 100%;
      border: 1px solid #e1e5ea;
      background: white;
    }}
    figcaption {{
      margin-top: 6px;
      color: #52606d;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <h1>Pilot Dataset Review</h1>
  <p>Generated samples: {len(sample_dirs)}</p>
  {''.join(rows)}
</body>
</html>
"""
    (output_root / "contact_sheet.html").write_text(html_text, encoding="utf-8")


def run(mode: str) -> None:
    if not IMAGE_ROOT.exists():
        raise FileNotFoundError(f"Input folder does not exist: {IMAGE_ROOT}")

    output_root, temp_root = prepare_temp_output_folder(mode)

    pdf_pairs = load_pdf_pairs()
    sample_dirs: list[Path] = []

    try:
        for index in sample_indices_for_mode(mode):
            teacher_path = IMAGE_ROOT / "teacher_solutions" / f"B_{index:03d}.png"
            gt_path = IMAGE_ROOT / "clean_solutions" / f"GT_{index:03d}.png"
            if not teacher_path.exists():
                raise FileNotFoundError(f"Missing teacher solution: {teacher_path}")
            if not gt_path.exists():
                raise FileNotFoundError(f"Missing clean solution: {gt_path}")

            print(f"Matching sample_{index:03d}...", flush=True)
            teacher_image = load_rgb_image(teacher_path)
            gt_image = load_rgb_image(gt_path)
            match = find_best_match(index, gt_image, pdf_pairs)
            sample_dir = save_sample(temp_root, index, teacher_image, gt_image, match)
            sample_dirs.append(sample_dir)

            confidence = confidence_for(match.score)
            ambiguity = " ambiguous" if match.ambiguous else ""
            print(
                f"  {confidence}{ambiguity} score={match.score:.4f} "
                f"page={match.page_index + 1} clean={match.clean_pdf.name}",
                flush=True,
            )

        make_contact_sheet(temp_root, sample_dirs)
        replace_output_folder(output_root, temp_root)
        print(
            f"Wrote {len(sample_dirs)} samples to {output_root}",
        )
        print(f"Review: {output_root / 'contact_sheet.html'}")
    except BaseException:
        if temp_root.exists() and not temp_root.is_symlink():
            shutil.rmtree(temp_root)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("pilot", "full"),
        required=True,
        help="pilot writes 10 review samples; full writes all 147 samples.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.mode)


if __name__ == "__main__":
    main()
