from pathlib import Path

from PIL import Image

from tools.style_lab.image_metrics import compute_image_metric, write_metrics_csv


def test_blank_white_image_has_zero_ink_ratio(tmp_path):
    path = tmp_path / "blank_white.png"
    Image.new("RGB", (80, 60), "white").save(path)

    metric = compute_image_metric("GT_001", path)

    assert metric.ink_ratio == 0
    assert metric.dark_ratio == 0
    assert metric.red_ratio == 0
    assert metric.blue_ratio == 0
    assert metric.aspect_ratio == 1.333333


def test_color_ratios_detect_black_red_and_blue_lines(simple_metric_images):
    black = compute_image_metric("GT_001", simple_metric_images["black"])
    red = compute_image_metric("GT_002", simple_metric_images["red"])
    blue = compute_image_metric("GT_003", simple_metric_images["blue"])

    assert black.dark_ratio > 0
    assert red.red_ratio > 0
    assert blue.blue_ratio > 0


def test_composite_solution_fixture_has_multiple_ink_channels(composite_solution_images):
    metric = compute_image_metric("GT_024", composite_solution_images["GT_024"])

    assert metric.width >= 640
    assert metric.height >= 900
    assert metric.ink_ratio > 0.01
    assert metric.dark_ratio > 0
    assert metric.red_ratio > 0
    assert metric.blue_ratio > 0


def test_write_metrics_csv_outputs_stable_header(tmp_path, simple_metric_images):
    metrics = [
        compute_image_metric("GT_001", simple_metric_images["black"]),
        compute_image_metric("GT_002", simple_metric_images["red"]),
    ]
    output = tmp_path / "metrics.csv"

    write_metrics_csv(metrics, output)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "sample_id,path,width,height,aspect_ratio,ink_ratio,dark_ratio,red_ratio,blue_ratio"
    assert lines[1].startswith("GT_001,")
    assert lines[2].startswith("GT_002,")
