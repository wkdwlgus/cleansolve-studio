from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessMetrics:
    total_jobs: int
    jobs_requiring_human_review: int
    total_visible_review_items: int
    jobs_over_review_item_budget: int


@dataclass(frozen=True)
class E2EMetrics:
    total_jobs: int
    approved_jobs: int
    jobs_with_render_artifact: int
    jobs_with_export_artifact: int
    jobs_with_correction_plan: int
    total_visible_review_items: int
    jobs_over_review_item_budget: int


def summarize_review_budget(metrics: HarnessMetrics) -> dict[str, float | bool]:
    hitl_exposure_rate = _rate(metrics.jobs_requiring_human_review, metrics.total_jobs)
    average_review_items = _rate(metrics.total_visible_review_items, metrics.total_jobs)
    has_jobs = metrics.total_jobs > 0

    return {
        "has_jobs": has_jobs,
        "hitl_exposure_rate": hitl_exposure_rate,
        "average_review_items": average_review_items,
        "passes_hitl_target": has_jobs and hitl_exposure_rate <= 0.2,
        "passes_average_review_item_target": has_jobs and average_review_items <= 1,
        "passes_review_item_budget": has_jobs and metrics.jobs_over_review_item_budget == 0,
    }


def summarize_e2e_metrics(metrics: E2EMetrics) -> dict[str, float | bool]:
    has_jobs = metrics.total_jobs > 0
    approval_rate = _rate(metrics.approved_jobs, metrics.total_jobs)
    render_artifact_rate = _rate(metrics.jobs_with_render_artifact, metrics.total_jobs)
    export_artifact_rate = _rate(metrics.jobs_with_export_artifact, metrics.total_jobs)
    correction_plan_rate = _rate(metrics.jobs_with_correction_plan, metrics.total_jobs)
    average_visible_review_items = _rate(metrics.total_visible_review_items, metrics.total_jobs)

    return {
        "has_jobs": has_jobs,
        "approval_rate": approval_rate,
        "render_artifact_rate": render_artifact_rate,
        "export_artifact_rate": export_artifact_rate,
        "correction_plan_rate": correction_plan_rate,
        "average_visible_review_items": average_visible_review_items,
        "passes_approval_target": has_jobs and approval_rate == 1.0,
        "passes_render_artifact_target": has_jobs and render_artifact_rate == 1.0,
        "passes_export_artifact_target": has_jobs and export_artifact_rate == 1.0,
        "passes_review_item_budget": has_jobs and metrics.jobs_over_review_item_budget == 0,
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
