import type { CandidateSpecElement, CandidateSpecPreview, SpecPatchRequest } from '../api/client';
import type { ReviewItem } from '../types/spec';

const TARGET_ANCHOR_EDIT_TYPES = new Set([
  'freehand_dimension_marker',
  'dimension_line',
  'dimension_curve'
]);

export interface TargetAnchorDraft {
  clientSpecVersion: number;
  elementId: string;
  startX: number;
  startY: number;
  endX: number;
  endY: number;
}

export function createTargetAnchorDraft(
  candidateSpec: CandidateSpecPreview | null,
  item: ReviewItem | null
): TargetAnchorDraft | null {
  if (!candidateSpec || !item || !TARGET_ANCHOR_EDIT_TYPES.has(item.type)) {
    return null;
  }

  const element = candidateSpec.elements.find((candidate) => candidate.id === item.element_id);
  if (!element || !TARGET_ANCHOR_EDIT_TYPES.has(element.type)) {
    return null;
  }

  const start = getPoint(element, 'target_anchor_start');
  const end = getPoint(element, 'target_anchor_end');
  if (!start || !end) {
    return null;
  }

  return {
    clientSpecVersion: candidateSpec.version,
    elementId: element.id,
    startX: start[0],
    startY: start[1],
    endX: end[0],
    endY: end[1]
  };
}

export function draftToSpecPatchRequest(draft: TargetAnchorDraft): SpecPatchRequest {
  return {
    client_spec_version: draft.clientSpecVersion,
    element_id: draft.elementId,
    operation: 'update_element',
    changes: {
      'geometry.target_anchor_start': [draft.startX, draft.startY],
      'geometry.target_anchor_end': [draft.endX, draft.endY]
    }
  };
}

function getPoint(element: CandidateSpecElement, key: string): [number, number] | null {
  const value = element.geometry?.[key];
  if (!Array.isArray(value) || value.length !== 2) {
    return null;
  }

  const [x, y] = value;
  if (!isFiniteNumber(x) || !isFiniteNumber(y)) {
    return null;
  }

  return [x, y];
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
