from __future__ import annotations

import copy
import math
from typing import Any

from pydantic import BaseModel, Field

from cleansolve_spec.models import CandidateSpec, Element


class SpecPatchRequest(BaseModel):
    client_spec_version: int = Field(ge=1)
    element_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    changes: dict[str, Any] = Field(min_length=1)


class SpecPatchRejected(Exception):
    def __init__(
        self,
        *,
        reason: str,
        element_id: str,
        path: str | None = None,
        value: Any = None,
    ):
        super().__init__(reason)
        self.reason = reason
        self.element_id = element_id
        self.path = path
        self.value = value

    def fields(self) -> dict[str, Any]:
        fields = {
            "reason": self.reason,
            "element_id": self.element_id,
        }
        if self.path is not None:
            fields["path"] = self.path
        if self.value is not None:
            fields["value"] = self.value
        return fields


POINT_PATHS_BY_TYPE: dict[str, set[str]] = {
    "formula_line": {"geometry.anchor"},
    "text_note": {"geometry.anchor"},
    "highlight_line": {"geometry.start", "geometry.end"},
    "highlight_curve": {"geometry.start", "geometry.end"},
    "arrow": {"geometry.start", "geometry.end"},
    "circle": {"geometry.center"},
    "point_label": {"geometry.point", "geometry.label_anchor"},
    "segment_label": {"geometry.start", "geometry.end", "geometry.label_anchor"},
    "dimension_line": {
        "geometry.target_anchor_start",
        "geometry.target_anchor_end",
        "geometry.visible_start",
        "geometry.visible_end",
        "geometry.label_anchor",
    },
    "dimension_curve": {
        "geometry.target_anchor_start",
        "geometry.target_anchor_end",
        "geometry.visible_start",
        "geometry.visible_end",
        "geometry.label_anchor",
    },
    "freehand_dimension_marker": {
        "geometry.target_anchor_start",
        "geometry.target_anchor_end",
        "geometry.label_anchor",
    },
}

STRING_PATHS_BY_TYPE: dict[str, set[str]] = {
    "formula_line": {"text", "display_text"},
    "text_note": {"text", "display_text"},
    "point_label": {"label"},
    "segment_label": {"label"},
    "dimension_line": {"label"},
    "dimension_curve": {"label"},
    "freehand_dimension_marker": {"label"},
}

CONTROL_POINT_PATHS_BY_TYPE: dict[str, set[str]] = {
    "highlight_curve": {"geometry.control_points"},
    "dimension_curve": {"geometry.control_points", "geometry.curve_control_points"},
}

BBOX_PATHS_BY_TYPE: dict[str, set[str]] = {
    "box": {"bbox", "geometry.bbox"},
    "circle": {"bbox", "geometry.bbox"},
}

RADIUS_PATHS_BY_TYPE: dict[str, set[str]] = {
    "circle": {"geometry.radius"},
}

COLOR_EDITABLE_TYPES = {
    "formula_line",
    "text_note",
    "highlight_line",
    "highlight_curve",
    "dimension_line",
    "dimension_curve",
    "freehand_dimension_marker",
    "arrow",
    "box",
    "circle",
    "point_label",
    "segment_label",
}


def apply_spec_patch(spec: CandidateSpec, request: SpecPatchRequest) -> CandidateSpec:
    if request.operation != "update_element":
        raise SpecPatchRejected(
            reason="operation_not_allowed",
            element_id=request.element_id,
        )
    element = _find_element(spec, request.element_id)
    _validate_changes(spec, element, request.changes)

    patched = spec.model_copy(deep=True)
    patched.version += 1
    patched_element = _find_element(patched, request.element_id)

    for path, value in request.changes.items():
        _set_path(patched_element, path, value)

    patched_element.revision_history.append(
        {
            "revision_id": f"user_patch_v{patched.version}",
            "source": "user_patch",
            "client_spec_version": request.client_spec_version,
            "result_spec_version": patched.version,
            "operation": request.operation,
            "changes": copy.deepcopy(request.changes),
        }
    )
    return patched


def _find_element(spec: CandidateSpec, element_id: str) -> Element:
    for element in spec.elements:
        if element.id == element_id:
            return element
    raise SpecPatchRejected(reason="element_not_found", element_id=element_id)


def _validate_changes(spec: CandidateSpec, element: Element, changes: dict[str, Any]) -> None:
    allowed_paths = _allowed_paths(element.type)
    for path, value in changes.items():
        if path not in allowed_paths:
            raise SpecPatchRejected(
                reason="path_not_allowed",
                element_id=element.id,
                path=path,
                value=value,
            )
        _validate_value(spec, element, path, value)


def _allowed_paths(element_type: str) -> set[str]:
    paths: set[str] = set()
    paths.update(POINT_PATHS_BY_TYPE.get(element_type, set()))
    paths.update(STRING_PATHS_BY_TYPE.get(element_type, set()))
    paths.update(CONTROL_POINT_PATHS_BY_TYPE.get(element_type, set()))
    paths.update(BBOX_PATHS_BY_TYPE.get(element_type, set()))
    paths.update(RADIUS_PATHS_BY_TYPE.get(element_type, set()))
    if element_type in COLOR_EDITABLE_TYPES:
        paths.add("color")
    return paths


def _validate_value(spec: CandidateSpec, element: Element, path: str, value: Any) -> None:
    if path in POINT_PATHS_BY_TYPE.get(element.type, set()):
        if not _is_point_inside_page(value, spec):
            raise _rejected("invalid_point", element, path, value)
        return

    if path in BBOX_PATHS_BY_TYPE.get(element.type, set()):
        if not _is_bbox_inside_page(value, spec):
            raise _rejected("invalid_bbox", element, path, value)
        return

    if path in CONTROL_POINT_PATHS_BY_TYPE.get(element.type, set()):
        if not _is_control_point_list_inside_page(value, spec):
            raise _rejected("invalid_control_points", element, path, value)
        return

    if path in STRING_PATHS_BY_TYPE.get(element.type, set()) or path == "color":
        if not _is_non_empty_string(value):
            raise _rejected("invalid_string", element, path, value)
        return

    if path in RADIUS_PATHS_BY_TYPE.get(element.type, set()):
        if not _is_positive_finite_number(value):
            raise _rejected("invalid_number", element, path, value)


def _rejected(reason: str, element: Element, path: str, value: Any) -> SpecPatchRejected:
    return SpecPatchRejected(reason=reason, element_id=element.id, path=path, value=value)


def _is_point_inside_page(value: Any, spec: CandidateSpec) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    x, y = value
    return (
        _is_finite_number(x)
        and _is_finite_number(y)
        and 0 <= x <= spec.page.width
        and 0 <= y <= spec.page.height
    )


def _is_bbox_inside_page(value: Any, spec: CandidateSpec) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    x, y, width, height = value
    return (
        _is_finite_number(x)
        and _is_finite_number(y)
        and _is_positive_finite_number(width)
        and _is_positive_finite_number(height)
        and x >= 0
        and y >= 0
        and x + width <= spec.page.width
        and y + height <= spec.page.height
    )


def _is_control_point_list_inside_page(value: Any, spec: CandidateSpec) -> bool:
    if not isinstance(value, list) or len(value) not in {1, 2}:
        return False
    return all(_is_point_inside_page(point, spec) for point in value)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value != ""


def _is_positive_finite_number(value: Any) -> bool:
    return _is_finite_number(value) and value > 0


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _set_path(element: Element, path: str, value: Any) -> None:
    copied_value = copy.deepcopy(value)
    if path.startswith("geometry."):
        key = path.removeprefix("geometry.")
        element.geometry[key] = copied_value
        return
    setattr(element, path, copied_value)
