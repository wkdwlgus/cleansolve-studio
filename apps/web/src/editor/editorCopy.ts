interface Point {
  x: number;
  y: number;
}

interface AnchorPatchSummary {
  start: Point;
  end: Point;
}

const stylePresetLabels: Record<string, string> = {
  default_pretty_handwriting: '기본 손글씨 스타일'
};

function formatPoint(point: Point): string {
  return `${Math.round(point.x)}, ${Math.round(point.y)}`;
}

export function getStylePresetLabel(presetId: string): string {
  return stylePresetLabels[presetId] ?? '사용자 지정 손글씨 스타일';
}

export function formatAnchorPatchSummary({ start, end }: AnchorPatchSummary): string {
  return `끝점 조정: 시작점 (${formatPoint(start)}), 끝점 (${formatPoint(end)})`;
}
