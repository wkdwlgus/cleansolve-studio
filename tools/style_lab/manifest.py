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
