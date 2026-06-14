import type { PrimitiveType } from '../types/spec';
import type { ReviewItem } from '../types/spec';

export const interactionPolicy: Record<PrimitiveType, string[]> = {
  formula_line: ['choose_candidate', 'edit_text', 'move', 'adjust_line_spacing', 'change_color'],
  text_note: ['choose_candidate', 'edit_text', 'move', 'change_color'],
  highlight_line: ['drag_start', 'drag_end', 'move', 'change_color', 'adjust_width'],
  highlight_curve: ['drag_start', 'drag_end', 'drag_control_point', 'move', 'change_color', 'adjust_width'],
  dimension_line: [
    'drag_target_anchor_start',
    'drag_target_anchor_end',
    'drag_visible_offset',
    'drag_label',
    'choose_endpoint_style',
    'change_color'
  ],
  dimension_curve: [
    'drag_target_anchor_start',
    'drag_target_anchor_end',
    'drag_curve_control_point',
    'drag_curve_offset',
    'drag_label',
    'choose_endpoint_style',
    'change_color'
  ],
  freehand_dimension_marker: [
    'drag_target_anchor_start',
    'drag_target_anchor_end',
    'move_visible_stroke_group',
    'adjust_stroke_point',
    'drag_label',
    'change_color',
    'preserve_stroke_continuity'
  ],
  arrow: ['drag_start', 'drag_end', 'choose_arrow_head', 'drag_label', 'change_color'],
  box: ['resize', 'move', 'change_color', 'adjust_width'],
  circle: ['resize', 'move', 'change_color', 'adjust_width'],
  angle_mark: ['drag_vertex', 'drag_start_ray', 'drag_end_ray', 'adjust_radius', 'drag_label', 'change_color'],
  point_label: ['drag_point', 'drag_label', 'change_color'],
  segment_label: ['drag_label', 'change_color'],
  graph_point: ['drag_point', 'drag_label', 'snap_to_graph', 'change_color'],
  graph_curve: ['drag_control_point', 'drag_endpoint', 'change_color'],
  graph_tangent: ['drag_control_point', 'drag_endpoint', 'drag_tangent_point', 'change_color'],
  shaded_area: ['drag_polygon_handle', 'adjust_opacity', 'change_color', 'drag_label'],
  choice_mark: ['move', 'change_color'],
  freehand_annotation: ['move', 'scale', 'adjust_opacity', 'redraw'],
  unsupported_annotation: ['view_source_crop', 'keep_original', 'manual_edit']
};

export function isInteractionAllowed(type: PrimitiveType, action: string): boolean {
  return interactionPolicy[type].includes(action);
}

export function isReviewActionAllowed(item: ReviewItem | undefined, action: string): boolean {
  if (!item || item.requires_human_review !== true || item.resolved === true) {
    return false;
  }

  return isInteractionAllowed(item.type, action);
}
