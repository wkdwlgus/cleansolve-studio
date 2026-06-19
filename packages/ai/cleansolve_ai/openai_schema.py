PRIMITIVE_TYPES = [
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
    "angle_mark",
    "point_label",
    "segment_label",
    "graph_point",
    "graph_curve",
    "graph_tangent",
    "shaded_area",
    "choice_mark",
    "freehand_annotation",
    "unsupported_annotation",
]

POINT_SCHEMA = {
    "type": "array",
    "minItems": 2,
    "maxItems": 2,
    "items": {"type": "number"},
}

NULLABLE_POINT_SCHEMA = {
    "type": ["array", "null"],
    "minItems": 2,
    "maxItems": 2,
    "items": {"type": "number"},
}

BBOX_SCHEMA = {
    "type": "array",
    "minItems": 4,
    "maxItems": 4,
    "items": {"type": "number"},
}

NULLABLE_BBOX_SCHEMA = {
    "type": ["array", "null"],
    "minItems": 4,
    "maxItems": 4,
    "items": {"type": "number"},
}

STRING_LIST_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
}

NULLABLE_STRING_LIST_SCHEMA = {
    "type": ["array", "null"],
    "items": {"type": "string"},
}

STROKE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["stroke_id", "points"],
    "properties": {
        "stroke_id": {"type": "string"},
        "points": {"type": "array", "items": POINT_SCHEMA},
    },
}

GEOMETRY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "anchor",
        "start",
        "end",
        "visible_start",
        "visible_end",
        "target_anchor_start",
        "target_anchor_end",
        "label_anchor",
        "point",
        "center",
        "control_points",
        "curve_control_points",
        "visible_strokes",
        "bbox",
        "radius",
        "kind",
        "label",
        "text",
        "stroke_continuity",
    ],
    "properties": {
        "anchor": NULLABLE_POINT_SCHEMA,
        "start": NULLABLE_POINT_SCHEMA,
        "end": NULLABLE_POINT_SCHEMA,
        "visible_start": NULLABLE_POINT_SCHEMA,
        "visible_end": NULLABLE_POINT_SCHEMA,
        "target_anchor_start": NULLABLE_POINT_SCHEMA,
        "target_anchor_end": NULLABLE_POINT_SCHEMA,
        "label_anchor": NULLABLE_POINT_SCHEMA,
        "point": NULLABLE_POINT_SCHEMA,
        "center": NULLABLE_POINT_SCHEMA,
        "control_points": {"type": ["array", "null"], "items": POINT_SCHEMA},
        "curve_control_points": {"type": ["array", "null"], "items": POINT_SCHEMA},
        "visible_strokes": {"type": ["array", "null"], "items": STROKE_SCHEMA},
        "bbox": NULLABLE_BBOX_SCHEMA,
        "radius": {"type": ["number", "null"]},
        "kind": {"type": ["string", "null"]},
        "label": {"type": ["string", "null"]},
        "text": {"type": ["string", "null"]},
        "stroke_continuity": {"type": ["string", "null"]},
    },
}

ELEMENT_STYLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "stroke_width",
        "opacity",
        "font_size",
        "font_family",
        "font_weight",
        "fill",
        "stroke",
        "stroke_dasharray",
    ],
    "properties": {
        "stroke_width": {"type": ["number", "null"]},
        "opacity": {"type": ["number", "null"]},
        "font_size": {"type": ["number", "null"]},
        "font_family": {"type": ["string", "null"]},
        "font_weight": {"type": ["string", "null"]},
        "fill": {"type": ["string", "null"]},
        "stroke": {"type": ["string", "null"]},
        "stroke_dasharray": {"type": ["string", "null"]},
    },
}

INTERACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["locked", "editable", "selectable"],
    "properties": {
        "locked": {"type": ["boolean", "null"]},
        "editable": {"type": ["boolean", "null"]},
        "selectable": {"type": ["boolean", "null"]},
    },
}

VALIDATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "issues", "message"],
    "properties": {
        "status": {"type": ["string", "null"]},
        "issues": NULLABLE_STRING_LIST_SCHEMA,
        "message": {"type": ["string", "null"]},
    },
}

PATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "geometry.anchor",
        "geometry.start",
        "geometry.end",
        "geometry.visible_start",
        "geometry.visible_end",
        "geometry.target_anchor_start",
        "geometry.target_anchor_end",
        "geometry.label_anchor",
        "geometry.visible_strokes",
        "text",
        "label",
        "review_reason",
    ],
    "properties": {
        "geometry.anchor": NULLABLE_POINT_SCHEMA,
        "geometry.start": NULLABLE_POINT_SCHEMA,
        "geometry.end": NULLABLE_POINT_SCHEMA,
        "geometry.visible_start": NULLABLE_POINT_SCHEMA,
        "geometry.visible_end": NULLABLE_POINT_SCHEMA,
        "geometry.target_anchor_start": NULLABLE_POINT_SCHEMA,
        "geometry.target_anchor_end": NULLABLE_POINT_SCHEMA,
        "geometry.label_anchor": NULLABLE_POINT_SCHEMA,
        "geometry.visible_strokes": {"type": ["array", "null"], "items": STROKE_SCHEMA},
        "text": {"type": ["string", "null"]},
        "label": {"type": ["string", "null"]},
        "review_reason": {"type": ["string", "null"]},
    },
}

REVISION_HISTORY_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["revision_id", "source", "patch"],
    "properties": {
        "revision_id": {"type": ["string", "null"]},
        "source": {"type": ["string", "null"]},
        "patch": PATCH_SCHEMA,
    },
}

UNCERTAINTY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "id",
        "element_id",
        "message",
        "reason",
        "bbox",
        "confidence",
        "requires_human_review",
    ],
    "properties": {
        "id": {"type": ["string", "null"]},
        "element_id": {"type": ["string", "null"]},
        "message": {"type": ["string", "null"]},
        "reason": {"type": ["string", "null"]},
        "bbox": NULLABLE_BBOX_SCHEMA,
        "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
        "requires_human_review": {"type": ["boolean", "null"]},
    },
}

CANDIDATE_SPEC_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "job_id",
        "version",
        "source_images",
        "style",
        "page",
        "regions",
        "elements",
        "uncertainties",
    ],
    "properties": {
        "job_id": {"type": "string"},
        "version": {"type": "integer", "const": 1},
        "source_images": {
            "type": "object",
            "additionalProperties": False,
            "required": ["problem_image_id", "teacher_solution_image_id"],
            "properties": {
                "problem_image_id": {"type": "string"},
                "teacher_solution_image_id": {"type": "string"},
            },
        },
        "style": {
            "type": "object",
            "additionalProperties": False,
            "required": ["source", "preset_id", "preset_version", "description"],
            "properties": {
                "source": {"type": "string", "const": "system_builtin"},
                "preset_id": {"type": "string", "const": "default_pretty_handwriting"},
                "preset_version": {"type": "string", "const": "v1"},
                "description": {"type": ["string", "null"]},
            },
        },
        "page": {
            "type": "object",
            "additionalProperties": False,
            "required": ["width", "height"],
            "properties": {
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
            },
        },
        "regions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "type", "bbox", "preserve_original"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "bbox": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {"type": "number"},
                    },
                    "preserve_original": {"type": "boolean"},
                },
            },
        },
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "type",
                    "source_region",
                    "color",
                    "confidence",
                    "needs_review",
                    "requires_human_review",
                    "auto_correctable",
                    "evidence",
                    "bbox",
                    "geometry",
                    "style",
                    "interaction",
                    "validation",
                    "revision_history",
                    "text",
                    "display_text",
                    "label",
                    "review_reason",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": PRIMITIVE_TYPES},
                    "source_region": {"type": ["string", "null"]},
                    "color": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "needs_review": {"type": "boolean"},
                    "requires_human_review": {"type": "boolean"},
                    "auto_correctable": {"type": "boolean"},
                    "evidence": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["source", "bbox"],
                        "properties": {
                            "source": {"type": "string"},
                            "bbox": {
                                "type": "array",
                                "minItems": 4,
                                "maxItems": 4,
                                "items": {"type": "number"},
                            },
                        },
                    },
                    "bbox": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {"type": "number"},
                    },
                    "geometry": GEOMETRY_SCHEMA,
                    "style": ELEMENT_STYLE_SCHEMA,
                    "interaction": INTERACTION_SCHEMA,
                    "validation": VALIDATION_SCHEMA,
                    "revision_history": {
                        "type": "array",
                        "items": REVISION_HISTORY_ITEM_SCHEMA,
                    },
                    "text": {"type": ["string", "null"]},
                    "display_text": {"type": ["string", "null"]},
                    "label": {"type": ["string", "null"]},
                    "review_reason": {"type": ["string", "null"]},
                },
            },
        },
        "uncertainties": {"type": "array", "items": UNCERTAINTY_SCHEMA},
    },
}
