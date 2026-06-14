import pytest
from pydantic import ValidationError

from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, Region, StylePreset
from cleansolve_spec.validation import validate_candidate_spec, visible_review_items


def make_spec(element: Element) -> CandidateSpec:
    return CandidateSpec(
        job_id="job_test",
        version=1,
        source_images={
            "problem_image_id": "problem_test",
            "teacher_solution_image_id": "solution_test",
        },
        style=StylePreset(
            source="system_builtin",
            preset_id="default_pretty_handwriting",
            preset_version="v1",
        ),
        page=Page(width=1080, height=1920),
        regions=[],
        elements=[element],
        uncertainties=[],
    )


def test_dimension_curve_requires_target_anchors():
    element = Element(
        id="el_dim",
        type="dimension_curve",
        color="red",
        confidence=0.85,
        needs_review=True,
        evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 100]),
        bbox=[10, 10, 100, 100],
        geometry={"kind": "dimension_curve", "label_anchor": [50, 50]},
    )

    report = validate_candidate_spec(make_spec(element))

    assert report.passed is False
    assert report.issues[0].type == "missing_dimension_target_anchor"


def test_needs_review_is_not_user_visible_by_default():
    element = Element(
        id="el_formula",
        type="formula_line",
        color="blue",
        confidence=0.61,
        needs_review=True,
        requires_human_review=False,
        evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
        bbox=[10, 10, 100, 40],
    )

    items = visible_review_items(make_spec(element))

    assert items == []


def test_review_item_budget_limits_visible_items_to_three():
    elements = [
        Element(
            id=f"el_{index}",
            type="formula_line",
            color="red",
            confidence=0.4,
            needs_review=True,
            requires_human_review=True,
            evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
            bbox=[10, 10, 100, 40],
        )
        for index in range(5)
    ]
    spec = make_spec(elements[0])
    spec.elements = elements

    items = visible_review_items(spec)

    assert [item["element_id"] for item in items] == ["el_0", "el_1", "el_2"]


def test_element_rejects_misspelled_requires_human_review_field():
    with pytest.raises(ValidationError):
        Element(
            id="el_formula",
            type="formula_line",
            color="blue",
            confidence=0.61,
            needs_review=True,
            requires_human_reveiw=True,
            evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
            bbox=[10, 10, 100, 40],
        )


def test_package_exports_region():
    from cleansolve_spec import Region as ExportedRegion

    assert ExportedRegion is Region


def test_dimension_anchors_must_be_finite_two_number_points_inside_page():
    element = Element(
        id="el_dim",
        type="dimension_curve",
        color="red",
        confidence=0.85,
        evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 100]),
        bbox=[10, 10, 100, 100],
        geometry={
            "kind": "dimension_curve",
            "target_anchor_start": ["not-a-number", 50],
            "target_anchor_end": [50, 3000],
            "label": "1",
            "label_anchor": [50],
        },
    )

    report = validate_candidate_spec(make_spec(element))
    issue_types = [issue.type for issue in report.issues]

    assert report.passed is False
    assert issue_types.count("invalid_dimension_target_anchor") == 2
    assert "invalid_dimension_label_anchor" in issue_types


def test_validate_candidate_spec_reports_evidence_bbox_out_of_bounds():
    element = Element(
        id="el_formula",
        type="formula_line",
        color="blue",
        confidence=0.8,
        evidence=Evidence(source="teacher_solution_image", bbox=[10, -1, 100, 40]),
        bbox=[10, 10, 100, 40],
    )

    report = validate_candidate_spec(make_spec(element))

    assert report.passed is False
    assert [issue.type for issue in report.issues] == ["evidence_bbox_out_of_bounds"]


def test_validate_candidate_spec_reports_region_bbox_out_of_bounds():
    element = Element(
        id="el_formula",
        type="formula_line",
        color="blue",
        confidence=0.8,
        evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
        bbox=[10, 10, 100, 40],
    )
    spec = make_spec(element)
    spec.regions = [
        Region(
            id="region_problem",
            type="problem",
            bbox=[0, 0, 1200, 100],
        )
    ]

    report = validate_candidate_spec(spec)

    assert report.passed is False
    assert [issue.type for issue in report.issues] == ["region_bbox_out_of_bounds"]
