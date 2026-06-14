export type PrimitiveType =
  | 'formula_line'
  | 'text_note'
  | 'highlight_line'
  | 'highlight_curve'
  | 'dimension_line'
  | 'dimension_curve'
  | 'freehand_dimension_marker'
  | 'arrow'
  | 'box'
  | 'circle'
  | 'angle_mark'
  | 'point_label'
  | 'segment_label'
  | 'graph_point'
  | 'graph_curve'
  | 'graph_tangent'
  | 'shaded_area'
  | 'choice_mark'
  | 'freehand_annotation'
  | 'unsupported_annotation';

export interface ReviewItem {
  element_id: string;
  type: PrimitiveType;
  requires_human_review: boolean;
  review_reason?: string;
}
