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
    assert output.read_text(encoding="utf-8") == '{\n  "a": "한글",\n  "b": 1\n}\n'
