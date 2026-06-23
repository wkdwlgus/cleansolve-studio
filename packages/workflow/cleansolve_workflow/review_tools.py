from __future__ import annotations

from typing import cast

from .review_contract import ReviewToolName


class ReviewToolRejected(ValueError):
    pass


ALLOWED_REVIEW_TOOLS: tuple[ReviewToolName, ...] = (
    "inspect_content",
    "inspect_layout",
    "inspect_style",
    "compute_visual_diff",
    "patch_candidate_spec",
    "request_handwriting_asset",
    "rerender",
    "mark_approved",
    "escalate_hitl",
)


def ensure_allowed_tool(tool_name: str) -> ReviewToolName:
    if tool_name not in ALLOWED_REVIEW_TOOLS:
        raise ReviewToolRejected("review tool is not allowlisted")
    return cast(ReviewToolName, tool_name)
