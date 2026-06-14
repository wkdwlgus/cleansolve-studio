import { useMemo, useState } from 'react';
import { Circle, Group, Layer, Line, Rect, Stage, Text } from 'react-konva';
import type { ReviewItem } from '../types/spec';
import { formatAnchorPatchSummary } from './editorCopy';
import { isReviewActionAllowed } from './interactionPolicy';

interface Point {
  x: number;
  y: number;
}

type AnchorKey = 'start' | 'end';

const INITIAL_ANCHORS: Record<AnchorKey, Point> = {
  start: { x: 178, y: 386 },
  end: { x: 542, y: 386 }
};
const NUDGE_AMOUNT = 8;

type DragLikeEvent = {
  target: {
    x: () => number;
    y: () => number;
  };
};

interface EditorCanvasProps {
  markerReviewItem?: ReviewItem;
}

export function EditorCanvas({ markerReviewItem }: EditorCanvasProps) {
  const [anchors, setAnchors] = useState(INITIAL_ANCHORS);
  const canDragStartAnchor = isReviewActionAllowed(markerReviewItem, 'drag_target_anchor_start');
  const canDragEndAnchor = isReviewActionAllowed(markerReviewItem, 'drag_target_anchor_end');

  const patchSummary = useMemo(() => formatAnchorPatchSummary(anchors), [anchors]);

  const canvasSummary = `손그림 치수 표시 시작점은 x ${Math.round(anchors.start.x)}, y ${Math.round(
    anchors.start.y
  )}이고 끝점은 x ${Math.round(anchors.end.x)}, y ${Math.round(anchors.end.y)}입니다.`;

  const updateAnchor = (anchor: AnchorKey, point: Point) => {
    setAnchors((current) => ({
      ...current,
      [anchor]: point
    }));
  };

  const handleAnchorDrag = (anchor: AnchorKey, allowed: boolean) => (event: DragLikeEvent) => {
    if (!allowed) {
      return;
    }

    updateAnchor(anchor, {
      x: event.target.x(),
      y: event.target.y()
    });
  };

  const nudgeAnchor = (anchor: AnchorKey, allowed: boolean, delta: Point) => {
    if (!allowed) {
      return;
    }

    setAnchors((current) => ({
      ...current,
      [anchor]: {
        x: current[anchor].x + delta.x,
        y: current[anchor].y + delta.y
      }
    }));
  };

  return (
    <section className="canvas-shell" aria-label="편집 캔버스">
      <div
        className="canvas-frame"
        role="img"
        aria-label="삼각형 문제 위 손그림 치수 표시를 조정하는 미리보기 캔버스"
        aria-describedby="canvas-state-summary"
      >
        <Stage width={760} height={540}>
          <Layer>
            <Rect x={0} y={0} width={760} height={540} fill="#ffffff" />
            <Rect x={42} y={44} width={676} height={444} fill="#fbfcfd" stroke="#d9e2ec" strokeWidth={1} />
            <Text x={66} y={66} text="원본 문제 이미지 레이어" fontSize={18} fill="#25324a" />
            <Text x={88} y={132} text="삼각형에서 표시된 길이를 확인하세요." fontSize={24} fill="#1f2937" />
            <Line points={[178, 386, 318, 184, 542, 386, 178, 386]} stroke="#334155" strokeWidth={3} closed />
            <Text x={308} y={208} text="?" fontSize={32} fill="#334155" />
          </Layer>
          <Layer>
            <Group>
              <Line
                points={[anchors.start.x, anchors.start.y, 208, 326, 252, 278, 300, 244]}
                stroke="#dc2626"
                strokeWidth={4}
                tension={0.42}
                lineCap="round"
                lineJoin="round"
              />
              <Line
                points={[326, 226, 392, 198, 470, 190, anchors.end.x, anchors.end.y]}
                stroke="#dc2626"
                strokeWidth={4}
                tension={0.42}
                lineCap="round"
                lineJoin="round"
              />
              <Text x={326} y={214} text="1" fontSize={28} fill="#dc2626" fontStyle="bold" />
              <Circle
                x={anchors.start.x}
                y={anchors.start.y}
                radius={7}
                fill="#0f766e"
                stroke="#ffffff"
                strokeWidth={2}
                draggable={canDragStartAnchor}
                onDragMove={handleAnchorDrag('start', canDragStartAnchor)}
                onDragEnd={handleAnchorDrag('start', canDragStartAnchor)}
              />
              <Circle
                x={anchors.end.x}
                y={anchors.end.y}
                radius={7}
                fill="#0f766e"
                stroke="#ffffff"
                strokeWidth={2}
                draggable={canDragEndAnchor}
                onDragMove={handleAnchorDrag('end', canDragEndAnchor)}
                onDragEnd={handleAnchorDrag('end', canDragEndAnchor)}
              />
              <Circle x={326} y={226} radius={5} fill="#f59e0b" stroke="#ffffff" strokeWidth={2} />
            </Group>
          </Layer>
        </Stage>
      </div>
      <p id="canvas-state-summary" className="canvas-summary">
        {canvasSummary}
        {!markerReviewItem ? ' 현재 사람 확인이 필요한 치수 표시가 없어 조정 도구는 비활성화되어 있습니다.' : ''}
      </p>
      <div className="anchor-controls" aria-label="키보드용 치수 표시 조정">
        <div>
          <h2>시작점 조정</h2>
          <button type="button" disabled={!canDragStartAnchor} onClick={() => nudgeAnchor('start', canDragStartAnchor, { x: 0, y: -NUDGE_AMOUNT })}>
            위로
          </button>
          <button type="button" disabled={!canDragStartAnchor} onClick={() => nudgeAnchor('start', canDragStartAnchor, { x: 0, y: NUDGE_AMOUNT })}>
            아래로
          </button>
          <button type="button" disabled={!canDragStartAnchor} onClick={() => nudgeAnchor('start', canDragStartAnchor, { x: -NUDGE_AMOUNT, y: 0 })}>
            왼쪽
          </button>
          <button type="button" disabled={!canDragStartAnchor} onClick={() => nudgeAnchor('start', canDragStartAnchor, { x: NUDGE_AMOUNT, y: 0 })}>
            오른쪽
          </button>
        </div>
        <div>
          <h2>끝점 조정</h2>
          <button type="button" disabled={!canDragEndAnchor} onClick={() => nudgeAnchor('end', canDragEndAnchor, { x: 0, y: -NUDGE_AMOUNT })}>
            위로
          </button>
          <button type="button" disabled={!canDragEndAnchor} onClick={() => nudgeAnchor('end', canDragEndAnchor, { x: 0, y: NUDGE_AMOUNT })}>
            아래로
          </button>
          <button type="button" disabled={!canDragEndAnchor} onClick={() => nudgeAnchor('end', canDragEndAnchor, { x: -NUDGE_AMOUNT, y: 0 })}>
            왼쪽
          </button>
          <button type="button" disabled={!canDragEndAnchor} onClick={() => nudgeAnchor('end', canDragEndAnchor, { x: NUDGE_AMOUNT, y: 0 })}>
            오른쪽
          </button>
        </div>
      </div>
      <p className="patch-preview" aria-label="변경 요약">
        {patchSummary}
      </p>
    </section>
  );
}
