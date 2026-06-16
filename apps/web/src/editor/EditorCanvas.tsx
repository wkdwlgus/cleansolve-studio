import { useEffect, useMemo, useRef, useState } from 'react';
import { Circle, Group, Layer, Line, Rect, Stage, Text } from 'react-konva';
import type { CandidateSpecPreview } from '../api/client';
import type { ReviewItem } from '../types/spec';
import { buildPreviewModel, type PreviewPrimitive } from './candidatePreview';

interface EditorCanvasProps {
  candidateSpec: CandidateSpecPreview | null;
  markerReviewItem?: ReviewItem;
}

export function EditorCanvas({ candidateSpec, markerReviewItem }: EditorCanvasProps) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [stageSize, setStageSize] = useState({ width: 760, height: 540 });
  const previewModel = useMemo(() => (candidateSpec ? buildPreviewModel(candidateSpec) : null), [candidateSpec]);
  const stageScale = stageSize.width / 760;

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame || typeof ResizeObserver === 'undefined') {
      return;
    }

    const observer = new ResizeObserver(([entry]) => {
      const width = Math.min(760, Math.max(1, entry.contentRect.width));
      setStageSize({ width, height: Math.round((width * 540) / 760) });
    });
    observer.observe(frame);
    return () => observer.disconnect();
  }, []);

  const canvasSummary = candidateSpec
    ? `candidate spec version ${candidateSpec.version} 기준 미리보기입니다. 표시된 overlay 요소는 ${previewModel?.primitives.length ?? 0}개입니다.`
    : '업로드 후 분석을 실행하면 미리보기가 여기에 표시됩니다.';

  return (
    <section className="canvas-shell" aria-label="편집 캔버스">
      <div
        ref={frameRef}
        className="canvas-frame"
        role="img"
        aria-label="candidate spec 기반 미리보기 캔버스"
        aria-describedby="canvas-state-summary"
        style={{ height: stageSize.height }}
      >
        <Stage width={stageSize.width} height={stageSize.height}>
          {previewModel ? (
            <Layer>
              <Group scaleX={stageScale} scaleY={stageScale}>
                <Rect x={0} y={0} width={760} height={540} fill="#ffffff" />
                <Rect x={20} y={40} width={720} height={460} fill="#fbfcfd" stroke="#d9e2ec" strokeWidth={1} />
                {previewModel.primitives.map(renderPreviewPrimitive)}
              </Group>
            </Layer>
          ) : (
            <Layer>
              <Group scaleX={stageScale} scaleY={stageScale}>
                <Rect x={0} y={0} width={760} height={540} fill="#ffffff" />
                <Rect x={42} y={44} width={676} height={444} fill="#fbfcfd" stroke="#d9e2ec" strokeWidth={1} />
                <Text x={66} y={66} text="미리보기 대기 중" fontSize={18} fill="#25324a" />
                <Text x={88} y={132} text="업로드 후 분석을 실행하면 미리보기가 여기에 표시됩니다." fontSize={22} fill="#1f2937" />
                <Line points={[178, 386, 318, 184, 542, 386, 178, 386]} stroke="#334155" strokeWidth={3} closed />
                <Text x={308} y={208} text="?" fontSize={32} fill="#334155" />
                <Line
                  points={[178, 386, 208, 326, 252, 278, 300, 244]}
                  stroke="#dc2626"
                  strokeWidth={4}
                  tension={0.42}
                  lineCap="round"
                  lineJoin="round"
                />
                <Line
                  points={[326, 226, 392, 198, 470, 190, 542, 386]}
                  stroke="#dc2626"
                  strokeWidth={4}
                  tension={0.42}
                  lineCap="round"
                  lineJoin="round"
                />
                <Text x={326} y={214} text="1" fontSize={28} fill="#dc2626" fontStyle="bold" />
              </Group>
            </Layer>
          )}
        </Stage>
      </div>
      <p id="canvas-state-summary" className="canvas-summary">
        {canvasSummary}
        {markerReviewItem ? ' 사람 확인이 필요한 항목은 오른쪽 검토 패널에서 확인합니다.' : ''}
      </p>
    </section>
  );
}

function renderPreviewPrimitive(primitive: PreviewPrimitive) {
  switch (primitive.kind) {
    case 'line':
      return (
        <Line
          key={primitive.id}
          points={primitive.points}
          stroke={primitive.color}
          strokeWidth={primitive.strokeWidth}
          tension={primitive.tension}
          closed={primitive.closed}
          lineCap="round"
          lineJoin="round"
        />
      );
    case 'rect':
      return (
        <Rect
          key={primitive.id}
          x={primitive.x}
          y={primitive.y}
          width={primitive.width}
          height={primitive.height}
          fill="transparent"
          stroke={primitive.color}
          strokeWidth={primitive.strokeWidth}
        />
      );
    case 'circle':
      return (
        <Circle
          key={primitive.id}
          x={primitive.x}
          y={primitive.y}
          radius={primitive.radius}
          fill={primitive.fill ?? 'transparent'}
          stroke={primitive.color}
          strokeWidth={primitive.strokeWidth}
        />
      );
    case 'text':
      return (
        <Text
          key={primitive.id}
          x={primitive.x}
          y={primitive.y}
          text={primitive.text}
          fontSize={primitive.fontSize}
          fill={primitive.color}
        />
      );
  }
}
