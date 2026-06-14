from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


PrimitiveType = Literal[
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


class CandidateBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(CandidateBaseModel):
    source: str
    bbox: list[float] = Field(min_length=4, max_length=4)


class StylePreset(CandidateBaseModel):
    source: Literal["system_builtin"]
    preset_id: str
    preset_version: str
    description: str | None = None


class Page(CandidateBaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Region(CandidateBaseModel):
    id: str
    type: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    preserve_original: bool = True


class Element(CandidateBaseModel):
    id: str
    type: PrimitiveType
    source_region: str | None = None
    color: str | None = None
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
    requires_human_review: bool = False
    auto_correctable: bool = False
    evidence: Evidence
    bbox: list[float] = Field(min_length=4, max_length=4)
    geometry: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    interaction: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    revision_history: list[dict[str, Any]] = Field(default_factory=list)
    text: str | None = None
    display_text: str | None = None
    label: str | None = None
    review_reason: str | None = None


class CandidateSpec(CandidateBaseModel):
    job_id: str
    version: int = Field(ge=1)
    source_images: dict[str, str]
    style: StylePreset
    page: Page
    regions: list[Region] = Field(default_factory=list)
    elements: list[Element] = Field(default_factory=list)
    uncertainties: list[dict[str, Any]] = Field(default_factory=list)


class ValidationIssue(CandidateBaseModel):
    issue_id: str
    type: str
    severity: Literal["low", "medium", "high"]
    element_id: str | None = None
    message: str
    auto_correctable: bool = False


class ValidationReport(CandidateBaseModel):
    report_id: str
    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
