import pytest
from cleansolve_api.spec_patch import (
    SpecPatchRejected,
    SpecPatchRequest,
    apply_spec_patch,
)
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, StylePreset


def make_spec() -> CandidateSpec:
    return CandidateSpec(
        job_id="job_test",
        version=1,
        source_images={
            "problem_image_id": "img_problem",
            "teacher_solution_image_id": "img_teacher",
        },
        style=StylePreset(
            source="system_builtin",
            preset_id="default_pretty_handwriting",
            preset_version="v1",
        ),
        page=Page(width=1000, height=800),
        elements=[
            Element(
                id="el_dimension",
                type="dimension_line",
                color="red",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[100, 100, 400, 260]),
                bbox=[100, 100, 400, 260],
                geometry={
                    "kind": "dimension_line",
                    "target_anchor_start": [120, 220],
                    "target_anchor_end": [360, 220],
                    "visible_start": [120, 180],
                    "visible_end": [360, 180],
                    "label_anchor": [240, 160],
                },
                label="1",
            ),
            Element(
                id="el_text",
                type="text_note",
                color="black",
                confidence=0.95,
                evidence=Evidence(source="teacher_solution_image", bbox=[50, 50, 100, 40]),
                bbox=[50, 50, 100, 40],
                geometry={"kind": "text_note", "anchor": [60, 60]},
                text="Given",
            ),
        ],
    )


def make_request(
    changes: dict[str, object],
    *,
    element_id: str = "el_dimension",
) -> SpecPatchRequest:
    return SpecPatchRequest(
        client_spec_version=1,
        element_id=element_id,
        operation="update_element",
        changes=changes,
    )


def test_allowed_dimension_target_anchor_patch_increments_version_and_records_revision_history():
    spec = make_spec()

    patched = apply_spec_patch(
        spec,
        make_request({"geometry.target_anchor_end": [380, 240]}),
    )

    element = patched.elements[0]
    assert patched.version == 2
    assert element.geometry["target_anchor_end"] == [380, 240]
    assert element.revision_history == [
        {
            "revision_id": "user_patch_v2",
            "source": "user_patch",
            "client_spec_version": 1,
            "result_spec_version": 2,
            "operation": "update_element",
            "changes": {"geometry.target_anchor_end": [380, 240]},
        }
    ]


def test_original_spec_object_is_not_mutated():
    spec = make_spec()

    patched = apply_spec_patch(
        spec,
        make_request({"geometry.target_anchor_end": [380, 240], "label": "2"}),
    )

    assert patched is not spec
    assert patched.elements[0] is not spec.elements[0]
    assert spec.version == 1
    assert spec.elements[0].geometry["target_anchor_end"] == [360, 220]
    assert spec.elements[0].label == "1"
    assert spec.elements[0].revision_history == []


def test_patch_values_do_not_alias_request_changes_or_revision_history():
    spec = make_spec()
    changes = {"geometry.target_anchor_end": [380, 240]}

    patched = apply_spec_patch(spec, make_request(changes))
    changes["geometry.target_anchor_end"][0] = 999
    patched.elements[0].geometry["target_anchor_end"][1] = 777

    assert patched.elements[0].geometry["target_anchor_end"] == [380, 777]
    assert patched.elements[0].revision_history[0]["changes"] == {
        "geometry.target_anchor_end": [380, 240]
    }


def test_disallowed_path_is_rejected_with_path_not_allowed_reason():
    spec = make_spec()

    with pytest.raises(SpecPatchRejected) as exc_info:
        apply_spec_patch(spec, make_request({"geometry.visible_strokes": []}))

    assert exc_info.value.reason == "path_not_allowed"
    assert exc_info.value.element_id == "el_dimension"
    assert exc_info.value.path == "geometry.visible_strokes"


def test_page_outside_point_is_rejected_with_invalid_point_reason():
    spec = make_spec()

    with pytest.raises(SpecPatchRejected) as exc_info:
        apply_spec_patch(spec, make_request({"geometry.target_anchor_end": [1001, 240]}))

    assert exc_info.value.reason == "invalid_point"
    assert exc_info.value.element_id == "el_dimension"
    assert exc_info.value.path == "geometry.target_anchor_end"


@pytest.mark.parametrize(
    ("element_id", "changes"),
    [
        ("el_dimension", {"label": ""}),
        ("el_dimension", {"color": ""}),
        ("el_text", {"text": ""}),
    ],
)
def test_empty_label_color_text_is_rejected(element_id, changes):
    spec = make_spec()

    with pytest.raises(SpecPatchRejected) as exc_info:
        apply_spec_patch(spec, make_request(changes, element_id=element_id))

    assert exc_info.value.reason == "invalid_string"


def test_unsupported_operation_is_rejected():
    spec = make_spec()
    request = SpecPatchRequest(
        client_spec_version=1,
        element_id="el_dimension",
        operation="delete_element",
        changes={"label": "2"},
    )

    with pytest.raises(SpecPatchRejected) as exc_info:
        apply_spec_patch(spec, request)

    assert exc_info.value.reason == "operation_not_allowed"
