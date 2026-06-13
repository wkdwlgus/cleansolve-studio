from cleansolve_harness.metrics import HarnessMetrics, summarize_review_budget
from cleansolve_harness.runner import collect_metrics
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, StylePreset


def test_review_budget_passes_when_exposure_rate_is_under_target():
    metrics = HarnessMetrics(
        total_jobs=5,
        jobs_requiring_human_review=1,
        total_visible_review_items=3,
        jobs_over_review_item_budget=0,
    )

    summary = summarize_review_budget(metrics)

    assert summary["hitl_exposure_rate"] == 0.2
    assert summary["average_review_items"] == 0.6
    assert summary["passes_hitl_target"] is True


def test_review_budget_fails_when_any_job_exceeds_three_items():
    metrics = HarnessMetrics(
        total_jobs=2,
        jobs_requiring_human_review=1,
        total_visible_review_items=4,
        jobs_over_review_item_budget=1,
    )

    summary = summarize_review_budget(metrics)

    assert summary["passes_review_item_budget"] is False


def test_collect_metrics_detects_jobs_over_review_item_budget():
    spec = CandidateSpec(
        job_id="job_over_budget",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id=f"el_{index}",
                type="formula_line",
                confidence=0.8,
                requires_human_review=True,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
                bbox=[10, 10, 100, 40],
            )
            for index in range(4)
        ],
    )

    metrics = collect_metrics([spec])

    assert metrics.total_visible_review_items == 4
    assert metrics.jobs_requiring_human_review == 1
    assert metrics.jobs_over_review_item_budget == 1
