from __future__ import annotations

import json
from collections.abc import Mapping


STYLE_PROFILE_DEVELOPER_PROMPT = """
You extract a renderer-ready handwriting style profile from Style Lab artifacts.
Return only JSON that matches the provided schema. Do not create or describe a new image.
Propose concrete token candidates a renderer can use, while preserving math correctness over aesthetics.
Reflect Korean/formula integration in style_description.korean_text, style_description.formula,
tokens.text.size_ratio_to_formula, tokens.text.line_height_ratio,
tokens.formula.baseline_jitter_px, and tokens.stroke.black_width_px.
Do not invent certainty. If evidence is weak, set status to needs_review and explain uncertainties.
Do not output API keys, local paths, original filenames, or personal information.
""".strip()


def build_style_profile_user_prompt(
    *,
    preset_id: str,
    preset_version: str,
    manifest: dict[str, object],
    skeleton: dict[str, object],
    max_reference_images: int,
) -> str:
    metrics_summary = manifest.get("metrics_summary", {})
    core_count = _manifest_count(manifest, "core")
    extended_count = _manifest_count(manifest, "extended")
    token_key_paths = _token_key_paths(skeleton)
    artifact_names = [
        "core_contact_sheet.jpg",
        "calibration_manifest.json",
        "style_tokens.skeleton.json",
    ]

    return "\n".join(
        [
            "Create a style profile JSON for the handwriting renderer.",
            f"Preset: {preset_id} {preset_version}",
            f"Core sample count: {core_count}",
            f"Extended sample count: {extended_count}",
            "Metrics summary JSON:",
            json.dumps(metrics_summary, ensure_ascii=False, sort_keys=True),
            "Input artifact names:",
            json.dumps(artifact_names, ensure_ascii=False),
            f"Maximum attached reference images: {max_reference_images}",
            "Style token key paths:",
            json.dumps(token_key_paths, ensure_ascii=False),
            "Use the attached core contact sheet as the primary visual evidence.",
            "Use any additional attached reference images only as supporting evidence.",
        ]
    )


def _manifest_count(manifest: dict[str, object], tier: str) -> int:
    summary = manifest.get("metrics_summary")
    if isinstance(summary, Mapping):
        direct = summary.get(f"{tier}_count")
        if isinstance(direct, int):
            return direct

    direct = manifest.get(f"{tier}_sample_count")
    if isinstance(direct, int):
        return direct

    samples = manifest.get(f"{tier}_samples")
    if isinstance(samples, list):
        return len(samples)

    return 0


def _token_key_paths(value: object, prefix: str = "") -> list[str]:
    if not isinstance(value, Mapping):
        return [prefix] if prefix else []

    paths: list[str] = []
    for key in sorted(value):
        child_prefix = f"{prefix}.{key}" if prefix else str(key)
        child_paths = _token_key_paths(value[key], child_prefix)
        paths.extend(child_paths or [child_prefix])
    return paths
