import { Circle, Group, Layer, Line, Rect, Stage, Text } from 'react-konva';

export function EditorCanvas() {
  return (
    <div className="canvas-frame" aria-label="CleanSolve 미리보기 캔버스">
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
            <Circle x={178} y={386} radius={7} fill="#0f766e" stroke="#ffffff" strokeWidth={2} draggable />
            <Circle x={542} y={386} radius={7} fill="#0f766e" stroke="#ffffff" strokeWidth={2} draggable />
            <Circle x={326} y={226} radius={5} fill="#f59e0b" stroke="#ffffff" strokeWidth={2} draggable />
          </Group>
        </Layer>
      </Stage>
    </div>
  );
}
