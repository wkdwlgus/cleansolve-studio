from __future__ import annotations

from cleansolve_spec.models import CandidateSpec
from cleansolve_spec.validation import visible_review_items

from .metrics import HarnessMetrics

REVIEW_ITEM_BUDGET = 3


def collect_metrics(specs: list[CandidateSpec]) -> HarnessMetrics:
    total_visible_review_items = 0
    jobs_requiring_human_review = 0
    jobs_over_review_item_budget = 0

    for spec in specs:
        review_items = visible_review_items(spec, budget=len(spec.elements))
        review_item_count = len(review_items)
        total_visible_review_items += review_item_count

        if review_item_count > 0:
            jobs_requiring_human_review += 1
        if review_item_count > REVIEW_ITEM_BUDGET:
            jobs_over_review_item_budget += 1

    return HarnessMetrics(
        total_jobs=len(specs),
        jobs_requiring_human_review=jobs_requiring_human_review,
        total_visible_review_items=total_visible_review_items,
        jobs_over_review_item_budget=jobs_over_review_item_budget,
    )
