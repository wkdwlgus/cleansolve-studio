import { describe, expect, it } from 'vitest';
import type { ReviewItem } from '../types/spec';
import {
  filterHumanReviewItems,
  getPrimitiveTypeLabel,
  getReviewReasonText,
  primitiveTypeLabels
} from './reviewHelpers';

describe('review helper contracts', () => {
  const items: ReviewItem[] = [
    {
      element_id: 'auto-1',
      type: 'formula_line',
      requires_human_review: false,
      review_reason: '자동 처리 가능'
    },
    {
      element_id: 'human-1',
      type: 'freehand_dimension_marker',
      requires_human_review: true,
      review_reason: '치수 표시 연결점 확인 필요'
    },
    {
      element_id: 'human-2',
      type: 'text_note',
      requires_human_review: true,
      review_reason: '문구 확인 필요'
    },
    {
      element_id: 'human-3',
      type: 'dimension_line',
      requires_human_review: true,
      review_reason: '기준점 확인 필요'
    },
    {
      element_id: 'human-4',
      type: 'choice_mark',
      requires_human_review: true,
      review_reason: '선택 표시 확인 필요'
    }
  ];

  it('keeps only human review items and caps the review budget at three', () => {
    expect(filterHumanReviewItems(items).map((item) => item.element_id)).toEqual([
      'human-1',
      'human-2',
      'human-3'
    ]);
  });

  it('maps primitive IDs to Korean labels', () => {
    expect(getPrimitiveTypeLabel('freehand_dimension_marker')).toBe('손그림 치수 표시');
    expect(getPrimitiveTypeLabel('formula_line')).toBe('수식 줄');
  });

  it('does not expose raw primitive IDs as review labels', () => {
    for (const [primitiveId, label] of Object.entries(primitiveTypeLabels)) {
      expect(label).not.toBe(primitiveId);
      expect(label).not.toContain('_');
    }
  });

  it('uses a Korean fallback when a review reason is missing', () => {
    expect(
      getReviewReasonText({
        element_id: 'human-missing',
        type: 'dimension_line',
        requires_human_review: true
      })
    ).toContain('검토 사유가 아직 없습니다');
  });
});
