from cleansolve_harness.e2e import E2EHarnessResult
from cleansolve_harness.metrics import E2EMetrics, HarnessMetrics, summarize_e2e_metrics, summarize_review_budget
from cleansolve_harness.runner import collect_e2e_metrics, collect_metrics
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, StylePreset


def make_spec(review_required_count: int) -> CandidateSpec:
    return CandidateSpec(
        job_id=f"job_{review_required_count}",
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
            for index in range(review_required_count)
        ],
    )


def make_e2e_result(
    *,
    job_id: str = "job_1",
    status: str = "APPROVED",
    revision_attempts: int = 1,
    visible_review_item_count: int = 0,
    correction_plan_count: int = 1,
    candidate_spec_artifact_id: str = "artifact_candidate_spec_1",
    validation_report_artifact_id: str = "artifact_validation_report_1",
    correction_plan_artifact_id: str = "artifact_correction_plan_1",
    render_artifact_id: str = "artifact_render_1",
    export_artifact_id: str = "artifact_export_1",
    export_size_bytes: int = 10,
) -> E2EHarnessResult:
    return E2EHarnessResult(
        job_id=job_id,
        status=status,
        revision_attempts=revision_attempts,
        visible_review_item_count=visible_review_item_count,
        correction_plan_count=correction_plan_count,
        candidate_spec_artifact_id=candidate_spec_artifact_id,
        validation_report_artifact_id=validation_report_artifact_id,
        correction_plan_artifact_id=correction_plan_artifact_id,
        render_artifact_id=render_artifact_id,
        export_artifact_id=export_artifact_id,
        export_size_bytes=export_size_bytes,
    )


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


def test_empty_review_budget_summary_does_not_pass_targets():
    metrics = HarnessMetrics(
        total_jobs=0,
        jobs_requiring_human_review=0,
        total_visible_review_items=0,
        jobs_over_review_item_budget=0,
    )

    summary = summarize_review_budget(metrics)

    assert summary["has_jobs"] is False
    assert summary["passes_hitl_target"] is False
    assert summary["passes_average_review_item_target"] is False
    assert summary["passes_review_item_budget"] is False


def test_collect_metrics_caps_visible_items_but_detects_over_budget_demand():
    metrics = collect_metrics([make_spec(review_required_count=4)])

    assert metrics.total_visible_review_items == 3
    assert metrics.jobs_requiring_human_review == 1
    assert metrics.jobs_over_review_item_budget == 1


def test_collect_metrics_counts_zero_review_required_items():
    metrics = collect_metrics([make_spec(review_required_count=0)])

    assert metrics.total_visible_review_items == 0
    assert metrics.jobs_requiring_human_review == 0
    assert metrics.jobs_over_review_item_budget == 0


def test_collect_metrics_counts_one_review_required_item():
    metrics = collect_metrics([make_spec(review_required_count=1)])

    assert metrics.total_visible_review_items == 1
    assert metrics.jobs_requiring_human_review == 1
    assert metrics.jobs_over_review_item_budget == 0


def test_collect_metrics_counts_exact_review_item_budget_without_overage():
    metrics = collect_metrics([make_spec(review_required_count=3)])

    assert metrics.total_visible_review_items == 3
    assert metrics.jobs_requiring_human_review == 1
    assert metrics.jobs_over_review_item_budget == 0


def test_summarize_e2e_metrics_passes_when_all_targets_are_met():
    metrics = E2EMetrics(
        total_jobs=2,
        approved_jobs=2,
        jobs_with_render_artifact=2,
        jobs_with_export_artifact=2,
        jobs_with_correction_plan=2,
        total_visible_review_items=0,
        jobs_over_review_item_budget=0,
    )

    summary = summarize_e2e_metrics(metrics)

    assert summary["has_jobs"] is True
    assert summary["approval_rate"] == 1.0
    assert summary["render_artifact_rate"] == 1.0
    assert summary["export_artifact_rate"] == 1.0
    assert summary["correction_plan_rate"] == 1.0
    assert summary["average_visible_review_items"] == 0.0
    assert summary["passes_approval_target"] is True
    assert summary["passes_render_artifact_target"] is True
    assert summary["passes_export_artifact_target"] is True
    assert summary["passes_review_item_budget"] is True


def test_summarize_e2e_metrics_does_not_pass_empty_input():
    metrics = E2EMetrics(
        total_jobs=0,
        approved_jobs=0,
        jobs_with_render_artifact=0,
        jobs_with_export_artifact=0,
        jobs_with_correction_plan=0,
        total_visible_review_items=0,
        jobs_over_review_item_budget=0,
    )

    summary = summarize_e2e_metrics(metrics)

    assert summary["has_jobs"] is False
    assert summary["approval_rate"] == 0.0
    assert summary["render_artifact_rate"] == 0.0
    assert summary["export_artifact_rate"] == 0.0
    assert summary["correction_plan_rate"] == 0.0
    assert summary["average_visible_review_items"] == 0.0
    assert summary["passes_approval_target"] is False
    assert summary["passes_render_artifact_target"] is False
    assert summary["passes_export_artifact_target"] is False
    assert summary["passes_review_item_budget"] is False


def test_collect_e2e_metrics_counts_artifacts_corrections_and_review_budget():
    results = [
        make_e2e_result(job_id="job_ok"),
        make_e2e_result(
            job_id="job_needs_review",
            status="REQUIRES_REVIEW",
            visible_review_item_count=4,
            correction_plan_count=0,
            render_artifact_id="",
            export_artifact_id="artifact_export_2",
            export_size_bytes=0,
        ),
    ]

    metrics = collect_e2e_metrics(results)

    assert metrics.total_jobs == 2
    assert metrics.approved_jobs == 1
    assert metrics.jobs_with_render_artifact == 1
    assert metrics.jobs_with_export_artifact == 1
    assert metrics.jobs_with_correction_plan == 1
    assert metrics.total_visible_review_items == 4
    assert metrics.jobs_over_review_item_budget == 1
