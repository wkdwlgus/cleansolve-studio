import json
import subprocess
import sys
from pathlib import Path

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
    expected_artifacts = {
        "core_contact_sheet": output_root / "core_contact_sheet.jpg",
        "extended_contact_sheet": output_root / "extended_contact_sheet.jpg",
        "calibration_manifest": output_root / "calibration_manifest.json",
        "style_tokens": output_root / "style_tokens.skeleton.json",
        "metrics": output_root / "metrics.csv",
    }
    assert payload["artifacts"] == {
        key: str(path) for key, path in expected_artifacts.items()
    }
    for artifact_path in payload["artifacts"].values():
        assert Path(artifact_path).exists()
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


def test_cli_build_returns_code_2_for_invalid_existing_image(tmp_path, approved_reference_image_root):
    (approved_reference_image_root / "GT_024.png").write_bytes(b"not a png")

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
    assert "Traceback" not in result.stderr


def test_cli_build_returns_code_2_when_output_root_is_existing_file(
    tmp_path, approved_reference_image_root
):
    output_root = tmp_path / "out"
    output_root.write_text("not a directory", encoding="utf-8")

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

    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert str(output_root) in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_build_validates_columns_before_writing_artifacts(
    tmp_path, approved_reference_image_root
):
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
            "--columns",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "columns" in result.stderr
    assert not any(output_root.glob("*"))


def test_cli_build_returns_style_lab_error_for_non_integer_columns(
    tmp_path, approved_reference_image_root
):
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
            "--columns",
            "abc",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "columns" in result.stderr
    assert "usage:" not in result.stderr


def test_cli_build_returns_style_lab_error_for_non_integer_dimension(
    tmp_path, approved_reference_image_root
):
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
            "--contact-sheet-width",
            "wide",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "contact-sheet-width" in result.stderr
    assert "usage:" not in result.stderr


def test_cli_build_rejects_artifact_path_directory_before_writing_partial_artifacts(
    tmp_path, approved_reference_image_root
):
    output_root = tmp_path / "out"
    output_root.mkdir()
    existing_entries = {"extended_contact_sheet.jpg"}
    (output_root / "extended_contact_sheet.jpg").mkdir()

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

    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert "extended_contact_sheet.jpg" in result.stderr
    assert "Traceback" not in result.stderr
    assert {path.name for path in output_root.iterdir()} == existing_entries


def test_cli_build_returns_code_2_when_nested_output_parent_is_file(
    tmp_path, approved_reference_image_root
):
    blocked_parent = tmp_path / "notdir"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    output_root = blocked_parent / "child" / "out"

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

    assert result.returncode == 2
    assert result.stderr.startswith("Style Lab input error:")
    assert str(blocked_parent) in result.stderr
    assert "Traceback" not in result.stderr
