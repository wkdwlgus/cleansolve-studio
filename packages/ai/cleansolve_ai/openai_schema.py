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

BBOX_SCHEMA = {
    "type": "array",
    "minItems": 4,
    "maxItems": 4,
    "items": {"type": "number"},
}

STRING_LIST_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
}

STROKE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [],
    "properties": {
        "stroke_id": {"type": "string"},
        "points": {"type": "array", "items": POINT_SCHEMA},
    },
}

GEOMETRY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [],
    "properties": {
        "anchor": POINT_SCHEMA,
        "start": POINT_SCHEMA,
        "end": POINT_SCHEMA,
        "visible_start": POINT_SCHEMA,
        "visible_end": POINT_SCHEMA,
        "target_anchor_start": POINT_SCHEMA,
        "target_anchor_end": POINT_SCHEMA,
        "label_anchor": POINT_SCHEMA,
        "point": POINT_SCHEMA,
        "center": POINT_SCHEMA,
        "control_points": {"type": "array", "items": POINT_SCHEMA},
        "curve_control_points": {"type": "array", "items": POINT_SCHEMA},
        "visible_strokes": {"type": "array", "items": STROKE_SCHEMA},
        "bbox": BBOX_SCHEMA,
        "radius": {"type": "number"},
        "kind": {"type": "string"},
        "label": {"type": "string"},
        "text": {"type": "string"},
        "stroke_continuity": {"type": "string"},
    },
}

ELEMENT_STYLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [],
    "properties": {
        "stroke_width": {"type": "number"},
        "opacity": {"type": "number"},
        "font_size": {"type": "number"},
        "font_family": {"type": "string"},
        "font_weight": {"type": "string"},
        "fill": {"type": "string"},
        "stroke": {"type": "string"},
        "stroke_dasharray": {"type": "string"},
    },
}

INTERACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [],
    "properties": {
        "locked": {"type": "boolean"},
        "editable": {"type": "boolean"},
        "selectable": {"type": "boolean"},
    },
}

VALIDATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [],
    "properties": {
        "status": {"type": "string"},
        "issues": STRING_LIST_SCHEMA,
        "message": {"type": "string"},
    },
}

PATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [],
    "properties": {
        "geometry.anchor": POINT_SCHEMA,
        "geometry.start": POINT_SCHEMA,
        "geometry.end": POINT_SCHEMA,
        "geometry.visible_start": POINT_SCHEMA,
        "geometry.visible_end": POINT_SCHEMA,
        "geometry.target_anchor_start": POINT_SCHEMA,
        "geometry.target_anchor_end": POINT_SCHEMA,
        "geometry.label_anchor": POINT_SCHEMA,
        "geometry.visible_strokes": {"type": "array", "items": STROKE_SCHEMA},
        "text": {"type": ["string", "null"]},
        "label": {"type": ["string", "null"]},
        "review_reason": {"type": ["string", "null"]},
    },
}

REVISION_HISTORY_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [],
    "properties": {
        "revision_id": {"type": "string"},
        "source": {"type": "string"},
        "patch": PATCH_SCHEMA,
    },
}

UNCERTAINTY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [],
    "properties": {
        "id": {"type": "string"},
        "element_id": {"type": ["string", "null"]},
        "message": {"type": "string"},
        "reason": {"type": "string"},
        "bbox": BBOX_SCHEMA,
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "requires_human_review": {"type": "boolean"},
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
