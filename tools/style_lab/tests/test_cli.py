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
