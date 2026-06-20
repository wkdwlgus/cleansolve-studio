from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from tools.style_lab.contact_sheet import build_contact_sheet
from tools.style_lab.image_metrics import compute_image_metric, write_metrics_csv
from tools.style_lab.manifest import build_calibration_manifest, write_json
from tools.style_lab.models import ImageMetric, ReferenceSample, StyleLabInputError
from tools.style_lab.reference_set import CORE_SAMPLE_IDS, EXTENDED_SAMPLE_IDS, build_reference_samples
from tools.style_lab.tokens import build_style_token_skeleton


def _artifact_paths(output_root: Path) -> dict[str, str]:
    return {
        "core_contact_sheet": str(output_root / "core_contact_sheet.jpg"),
        "extended_contact_sheet": str(output_root / "extended_contact_sheet.jpg"),
        "calibration_manifest": str(output_root / "calibration_manifest.json"),
        "style_tokens": str(output_root / "style_tokens.skeleton.json"),
        "metrics": str(output_root / "metrics.csv"),
    }


def _validate_sample_files(samples: list[ReferenceSample], image_root: Path) -> None:
    missing = [sample.filename for sample in samples if not (image_root / sample.filename).exists()]
    if missing:
        raise StyleLabInputError(f"missing reference images: {', '.join(missing)}")
    invalid: list[str] = []
    for sample in samples:
        path = image_root / sample.filename
        if not path.is_file():
            invalid.append(sample.filename)
            continue
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, UnidentifiedImageError):
            invalid.append(sample.filename)
    if invalid:
        raise StyleLabInputError(f"unreadable reference images: {', '.join(invalid)}")


def _validate_output_options(args: argparse.Namespace, output_root: Path) -> None:
    if output_root.exists() and not output_root.is_dir():
        raise StyleLabInputError(f"output root is not a directory: {output_root}")
    if output_root.parent.exists() and not output_root.parent.is_dir():
        raise StyleLabInputError(f"output root parent is not a directory: {output_root.parent}")
    if args.columns <= 0:
        raise StyleLabInputError("columns must be greater than 0")
    if args.contact_sheet_width <= 0 or args.contact_sheet_height <= 0:
        raise StyleLabInputError("contact sheet dimensions must be greater than 0")


def _compute_metrics(samples: list[ReferenceSample], image_root: Path) -> list[ImageMetric]:
    metrics = []
    for sample in samples:
        try:
            metrics.append(compute_image_metric(sample.sample_id, image_root / sample.filename))
        except (OSError, UnidentifiedImageError) as exc:
            raise StyleLabInputError(f"unreadable reference image: {sample.filename}") from exc
    return metrics


def build_style_lab(args: argparse.Namespace) -> dict[str, object]:
    image_root = Path(args.image_root)
    output_root = Path(args.output_root)
    samples = build_reference_samples()
    core_samples = [sample for sample in samples if sample.tier == "core"]
    extended_samples = [sample for sample in samples if sample.tier == "extended"]
    artifacts = _artifact_paths(output_root)

    _validate_output_options(args, output_root)
    _validate_sample_files(samples, image_root)
    metrics = _compute_metrics(samples, image_root)
    write_metrics_csv(metrics, Path(artifacts["metrics"]))

    try:
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
    except (OSError, UnidentifiedImageError) as exc:
        raise StyleLabInputError(f"unreadable reference image while building contact sheets: {exc}") from exc

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
