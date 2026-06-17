import { describe, expect, it } from 'vitest';
import type { CandidateSpecPreview } from '../api/client';
import type { ReviewItem } from '../types/spec';
import { createTargetAnchorDraft, draftToSpecPatchRequest } from './editDraft';

const candidateSpec: CandidateSpecPreview = {
  job_id: 'job_test',
  version: 3,
  page: { width: 1080, height: 1920 },
  elements: [
    {
      id: 'el_dimension',
      type: 'freehand_dimension_marker',
      geometry: {
        target_anchor_start: [180, 820],
        target_anchor_end: [540, 850],
        label_anchor: [280, 610]
      }
    },
    {
      id: 'el_text',
      type: 'text_note',
      geometry: { anchor: [20, 30] },
      text: 'x=1'
    }
  ]
};

function reviewItem(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    element_id: 'el_dimension',
    type: 'freehand_dimension_marker',
    requires_human_review: true,
    resolved: false,
    review_reason: 'Endpoint needs operator review.',
    ...overrides
  };
}

describe('edit draft helpers', () => {
  it('creates a target anchor draft for supported dimension review items', () => {
    const draft = createTargetAnchorDraft(candidateSpec, reviewItem());

    expect(draft).toEqual({
      clientSpecVersion: 3,
      elementId: 'el_dimension',
      startX: 180,
      startY: 820,
      endX: 540,
      endY: 850
    });
  });

  it('returns null for unsupported review item types', () => {
    const draft = createTargetAnchorDraft(
      candidateSpec,
      reviewItem({ element_id: 'el_text', type: 'text_note' })
    );

    expect(draft).toBeNull();
  });

  it('returns null when target anchors are missing', () => {
    const draft = createTargetAnchorDraft(candidateSpec, reviewItem({ element_id: 'el_text' }));

    expect(draft).toBeNull();
  });

  it('converts a draft into a spec patch request', () => {
    const request = draftToSpecPatchRequest({
      clientSpecVersion: 3,
      elementId: 'el_dimension',
      startX: 180,
      startY: 820,
      endX: 610,
      endY: 380
    });

    expect(request).toEqual({
      client_spec_version: 3,
      element_id: 'el_dimension',
      operation: 'update_element',
      changes: {
        'geometry.target_anchor_start': [180, 820],
        'geometry.target_anchor_end': [610, 380]
      }
    });
  });
});
