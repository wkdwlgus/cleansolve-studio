import { describe, expect, it } from 'vitest';
import { interactionPolicy, isInteractionAllowed } from './interactionPolicy';

describe('interaction policy contracts', () => {
  it('allows freehand dimension marker target anchor drags', () => {
    expect(interactionPolicy.freehand_dimension_marker).toContain('drag_target_anchor_start');
    expect(interactionPolicy.freehand_dimension_marker).toContain('drag_target_anchor_end');
  });

  it('reports allowed interactions before canvas handlers are enabled', () => {
    expect(isInteractionAllowed('freehand_dimension_marker', 'drag_target_anchor_start')).toBe(true);
    expect(isInteractionAllowed('freehand_dimension_marker', 'drag_target_anchor_end')).toBe(true);
    expect(isInteractionAllowed('freehand_dimension_marker', 'drag_curve_control_point')).toBe(false);
  });
});
