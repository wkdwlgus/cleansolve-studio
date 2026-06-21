from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from tools.style_lab.style_profile_schema import validate_style_profile


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.style_lab.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def build_style_lab_input_root(tmp_path: Path) -> Path:
    input_root = tmp_path / "style-lab"
    input_root.mkdir()
    Image.new("RGB", (16, 16), color=(255, 255, 255)).save(input_root / "core_contact_sheet.jpg")
    (input_root / "calibration_manifest.json").write_text(
        json.dumps(
            {
                "preset_id": "default_pretty_handwriting",
                "preset_version": "v1",
                "metrics_summary": {
                    "max_ink_sample_id": "GT_132",
                    "max_color_sample_id": "GT_135",
                },
            }
        ),
        encoding="utf-8",
    )
    (input_root / "style_tokens.skeleton.json").write_text(
        json.dumps(
            {
                "preset_id": "default_pretty_handwriting",
                "preset_version": "v1",
                "tokens": {},
            }
        ),
        encoding="utf-8",
    )
    return input_root


def test_extract_profile_mock_writes_output_json(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    output_path = tmp_path / "profile.json"
    result = run_cli(
        [
            "extract-profile",
            "--input-root",
            str(input_root),
            "--output-path",
            str(output_path),
            "--client",
            "mock",
        ]
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["client"] == "mock"
    assert payload["model"] == "gpt-5.5"
    assert payload["core_sample_count"] == 19
    assert payload["reference_image_count"] == 0
    validate_style_profile(json.loads(output_path.read_text(encoding="utf-8")))


def test_extract_profile_missing_core_sheet_returns_code_2(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    (input_root / "core_contact_sheet.jpg").unlink()
    result = run_cli(
        ["extract-profile", "--input-root", str(input_root), "--output-path", str(tmp_path / "profile.json")]
    )
    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "core_contact_sheet.jpg" in result.stderr
    assert "usage:" not in result.stderr


def test_extract_profile_output_parent_file_returns_code_2(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    parent_file = tmp_path / "not-dir"
    parent_file.write_text("file", encoding="utf-8")
    result = run_cli(
        ["extract-profile", "--input-root", str(input_root), "--output-path", str(parent_file / "profile.json")]
    )
    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "output path parent is not a directory" in result.stderr
    assert "usage:" not in result.stderr


def test_extract_profile_rejects_negative_max_reference_images(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--max-reference-images", "-1"])
    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "max-reference-images must be between 0 and 6" in result.stderr
    assert "usage:" not in result.stderr


def test_extract_profile_rejects_max_reference_images_over_six(tmp_path):
    input_root = build_style_lab_input_root(tmp_path)
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--max-reference-images", "7"])
    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "max-reference-images must be between 0 and 6" in result.stderr
    assert "usage:" not in result.stderr


def test_extract_profile_openai_without_api_key_returns_code_2(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    input_root = build_style_lab_input_root(tmp_path)
    result = run_cli(["extract-profile", "--input-root", str(input_root), "--client", "openai"])
    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "OPENAI_API_KEY is required for OpenAI style profile extraction" in result.stderr
    assert "usage:" not in result.stderr
