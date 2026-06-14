import type { PrimitiveType, ReviewItem } from '../types/spec';

export const REVIEW_ITEM_LIMIT = 3;

export const primitiveTypeLabels: Record<PrimitiveType, string> = {
  formula_line: '수식 줄',
  text_note: '텍스트 메모',
  highlight_line: '직선 강조 표시',
  highlight_curve: '곡선 강조 표시',
  dimension_line: '직선 치수 표시',
  dimension_curve: '곡선 치수 표시',
  freehand_dimension_marker: '손그림 치수 표시',
  arrow: '화살표',
  box: '상자',
  circle: '원',
  angle_mark: '각도 표시',
  point_label: '점 라벨',
  segment_label: '선분 라벨',
  graph_point: '그래프 점',
  graph_curve: '그래프 곡선',
  graph_tangent: '그래프 접선',
  shaded_area: '음영 영역',
  choice_mark: '선택 표시',
  freehand_annotation: '손그림 주석',
  unsupported_annotation: '지원되지 않는 주석'
};

export function filterHumanReviewItems(items: ReviewItem[], limit = REVIEW_ITEM_LIMIT): ReviewItem[] {
  return items.filter((item) => item.requires_human_review === true).slice(0, limit);
}

export function getPrimitiveTypeLabel(type: PrimitiveType): string {
  return primitiveTypeLabels[type];
}

export function getReviewReasonText(item: ReviewItem): string {
  const reason = item.review_reason?.trim();

  if (reason) {
    return reason;
  }

  return `${getPrimitiveTypeLabel(item.type)} 검토 사유가 아직 없습니다. 원본 요소를 확인해 주세요.`;
}
