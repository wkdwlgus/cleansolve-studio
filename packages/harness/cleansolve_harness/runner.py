from __future__ import annotations

from cleansolve_spec.models import CandidateSpec
from cleansolve_spec.validation import visible_review_items

from .e2e import E2EHarnessResult
from .metrics import E2EMetrics, HarnessMetrics

REVIEW_ITEM_BUDGET = 3


def collect_metrics(specs: list[CandidateSpec]) -> HarnessMetrics:
    total_visible_review_items = 0
    jobs_requiring_human_review = 0
    jobs_over_review_item_budget = 0

    for spec in specs:
        visible_review_item_count = len(visible_review_items(spec))
        review_demand_count = sum(1 for element in spec.elements if element.requires_human_review)
        total_visible_review_items += visible_review_item_count

        if review_demand_count > 0:
            jobs_requiring_human_review += 1
        if review_demand_count > REVIEW_ITEM_BUDGET:
            jobs_over_review_item_budget += 1

    return HarnessMetrics(
        total_jobs=len(specs),
        jobs_requiring_human_review=jobs_requiring_human_review,
        total_visible_review_items=total_visible_review_items,
        jobs_over_review_item_budget=jobs_over_review_item_budget,
    )


def collect_e2e_metrics(results: list[E2EHarnessResult]) -> E2EMetrics:
    return E2EMetrics(
        total_jobs=len(results),
        approved_jobs=sum(1 for result in results if result.status == "APPROVED"),
        jobs_with_render_artifact=sum(1 for result in results if result.render_artifact_id),
        jobs_with_export_artifact=sum(
            1
            for result in results
            if result.export_artifact_id and result.export_size_bytes > 0
        ),
        jobs_with_correction_plan=sum(1 for result in results if result.correction_plan_count > 0),
        total_visible_review_items=sum(result.visible_review_item_count for result in results),
        jobs_over_review_item_budget=sum(
            1 for result in results if result.visible_review_item_count > REVIEW_ITEM_BUDGET
        ),
    )
