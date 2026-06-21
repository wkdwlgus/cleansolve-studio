from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from tools.style_lab.contact_sheet import build_contact_sheet
from tools.style_lab.image_metrics import compute_image_metric, write_metrics_csv
from tools.style_lab.manifest import build_calibration_manifest, write_json
from tools.style_lab.models import ImageMetric, ReferenceSample, StyleLabInputError
from tools.style_lab.reference_set import CORE_SAMPLE_IDS, EXTENDED_SAMPLE_IDS, build_reference_samples
from tools.style_lab.tokens import build_style_token_skeleton


class StyleLabArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise StyleLabInputError(message)


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


def _validate_existing_ancestors(path: Path) -> None:
    current = _nearest_existing_path(path)
    if current.exists() and not current.is_dir():
        raise StyleLabInputError(f"output path parent is not a directory: {current}")


def _nearest_existing_path(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _validate_artifact_paths(artifacts: dict[str, str]) -> None:
    invalid = [
        artifact
        for artifact in artifacts.values()
        if Path(artifact).exists() and not Path(artifact).is_file()
    ]
    if invalid:
        raise StyleLabInputError(f"artifact path is not a file: {', '.join(invalid)}")


def _validate_writable_directory(path: Path, label: str) -> None:
    if not os.access(path, os.W_OK | os.X_OK):
        raise StyleLabInputError(f"{label} is not writable: {path}")


def _validate_output_permissions(output_root: Path, artifacts: dict[str, str]) -> None:
    if output_root.exists():
        _validate_writable_directory(output_root, "output root")
    else:
        nearest_output_parent = _nearest_existing_path(output_root.parent)
        _validate_writable_directory(nearest_output_parent, "output root parent")

    for artifact in artifacts.values():
        artifact_path = Path(artifact)
        if artifact_path.exists():
            if not os.access(artifact_path, os.W_OK):
                raise StyleLabInputError(f"artifact path is not writable: {artifact_path}")
        else:
            nearest_artifact_parent = _nearest_existing_path(artifact_path.parent)
            _validate_writable_directory(nearest_artifact_parent, "artifact parent")


def _parse_positive_int(value: object, option_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise StyleLabInputError(f"{option_name} must be an integer: {value}") from exc
    if parsed <= 0:
        raise StyleLabInputError(f"{option_name} must be greater than 0")
    return parsed


def _validate_output_options(
    args: argparse.Namespace,
    output_root: Path,
    artifacts: dict[str, str],
) -> tuple[int, int, int]:
    _validate_existing_ancestors(output_root)
    if output_root.exists() and not output_root.is_dir():
        raise StyleLabInputError(f"output root is not a directory: {output_root}")
    for artifact_path in artifacts.values():
        _validate_existing_ancestors(Path(artifact_path).parent)
    _validate_artifact_paths(artifacts)
    _validate_output_permissions(output_root, artifacts)
    columns = _parse_positive_int(args.columns, "columns")
    contact_sheet_width = _parse_positive_int(args.contact_sheet_width, "contact-sheet-width")
    contact_sheet_height = _parse_positive_int(args.contact_sheet_height, "contact-sheet-height")
    return columns, contact_sheet_width, contact_sheet_height


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

    columns, contact_sheet_width, contact_sheet_height = _validate_output_options(
        args,
        output_root,
        artifacts,
    )
    _validate_sample_files(samples, image_root)
    metrics = _compute_metrics(samples, image_root)
    try:
        write_metrics_csv(metrics, Path(artifacts["metrics"]))
    except OSError as exc:
        raise StyleLabInputError(f"failed to write output artifact {artifacts['metrics']}: {exc}") from exc

    try:
        build_contact_sheet(
            samples=core_samples,
            image_root=image_root,
            output_path=Path(artifacts["core_contact_sheet"]),
            title=f"{args.preset_id} {args.preset_version} core reference set",
            cell_width=contact_sheet_width,
            cell_height=contact_sheet_height,
            columns=columns,
        )
    except UnidentifiedImageError as exc:
        raise StyleLabInputError(f"unreadable reference image while building core contact sheet: {exc}") from exc
    except OSError as exc:
        raise StyleLabInputError(
            f"failed to write output artifact {artifacts['core_contact_sheet']}: {exc}"
        ) from exc

    try:
        build_contact_sheet(
            samples=extended_samples,
            image_root=image_root,
            output_path=Path(artifacts["extended_contact_sheet"]),
            title=f"{args.preset_id} {args.preset_version} extended calibration set",
            cell_width=contact_sheet_width,
            cell_height=contact_sheet_height,
            columns=columns,
        )
    except UnidentifiedImageError as exc:
        raise StyleLabInputError(
            f"unreadable reference image while building extended contact sheet: {exc}"
        ) from exc
    except OSError as exc:
        raise StyleLabInputError(
            f"failed to write output artifact {artifacts['extended_contact_sheet']}: {exc}"
        ) from exc

    manifest = build_calibration_manifest(
        preset_id=args.preset_id,
        preset_version=args.preset_version,
        samples=samples,
        metrics=metrics,
        artifacts=artifacts,
    )
    try:
        write_json(manifest, Path(artifacts["calibration_manifest"]))
    except OSError as exc:
        raise StyleLabInputError(
            f"failed to write output artifact {artifacts['calibration_manifest']}: {exc}"
        ) from exc
    skeleton = build_style_token_skeleton(
        preset_id=args.preset_id,
        preset_version=args.preset_version,
        core_count=len(CORE_SAMPLE_IDS),
        extended_count=len(EXTENDED_SAMPLE_IDS),
    )
    try:
        write_json(skeleton, Path(artifacts["style_tokens"]))
    except OSError as exc:
        raise StyleLabInputError(
            f"failed to write output artifact {artifacts['style_tokens']}: {exc}"
        ) from exc

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
    parser = StyleLabArgumentParser(prog="python -m tools.style_lab.cli")
    subparsers = parser.add_subparsers(
        dest="command",
        parser_class=StyleLabArgumentParser,
        required=True,
    )

    build = subparsers.add_parser("build")
    build.add_argument("--image-root", default="image/clean_solutions")
    build.add_argument("--output-root", default="image/style-lab/default_pretty_handwriting/v1")
    build.add_argument("--preset-id", default="default_pretty_handwriting")
    build.add_argument("--preset-version", default="v1")
    build.add_argument("--contact-sheet-width", default="320")
    build.add_argument("--contact-sheet-height", default="460")
    build.add_argument("--columns", default="5")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
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
