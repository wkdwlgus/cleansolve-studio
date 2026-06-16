import type { CandidateSpecElement, CandidateSpecPreview } from '../api/client';

const STAGE_WIDTH = 760;
const STAGE_HEIGHT = 540;
const PREVIEW_WIDTH = 720;
const PREVIEW_HEIGHT = 460;
const OFFSET_X = 20;
const OFFSET_Y = 40;
const DEFAULT_OVERLAY_COLOR = '#dc2626';

type Point = [number, number];
type BBox = [number, number, number, number];

export type PreviewPrimitive =
  | { kind: 'line'; id: string; points: number[]; color: string; strokeWidth: number; closed?: boolean; tension?: number }
  | { kind: 'rect'; id: string; x: number; y: number; width: number; height: number; color: string; strokeWidth: number }
  | { kind: 'circle'; id: string; x: number; y: number; radius: number; color: string; strokeWidth: number; fill?: string }
  | { kind: 'text'; id: string; x: number; y: number; text: string; color: string; fontSize: number };

export interface PreviewModel {
  stage: { width: 760; height: 540 };
  scale: number;
  offset: { x: 20; y: 40 };
  primitives: PreviewPrimitive[];
}

export function buildPreviewModel(spec: CandidateSpecPreview): PreviewModel {
  const scale = computeScale(spec);
  const transformPoint = (point: Point): Point => [OFFSET_X + point[0] * scale, OFFSET_Y + point[1] * scale];
  const elements = isRenderableSpec(spec) ? spec.elements : [];
  const primitives = elements.flatMap((element) => renderElement(element, transformPoint, scale));

  return {
    stage: { width: STAGE_WIDTH, height: STAGE_HEIGHT },
    scale,
    offset: { x: OFFSET_X, y: OFFSET_Y },
    primitives
  };
}

export function getElementText(element: CandidateSpecElement): string | null {
  const geometry = asRecord(element.geometry);
  for (const value of [element.display_text, element.text, geometry?.text, geometry?.label, element.label]) {
    if (value == null) {
      continue;
    }

    const text = String(value);
    return text || null;
  }

  return null;
}

function computeScale(spec: CandidateSpecPreview): number {
  if (!isPositiveNumber(spec.page?.width) || !isPositiveNumber(spec.page?.height)) {
    return 1;
  }

  return Math.min(PREVIEW_WIDTH / spec.page.width, PREVIEW_HEIGHT / spec.page.height);
}

function isRenderableSpec(spec: CandidateSpecPreview): boolean {
  return isPositiveNumber(spec.page?.width) && isPositiveNumber(spec.page?.height) && Array.isArray(spec.elements);
}

function renderElement(
  element: CandidateSpecElement,
  transformPoint: (point: Point) => Point,
  scale: number
): PreviewPrimitive[] {
  switch (element.type) {
    case 'formula_line':
      return renderTextElement(element, transformPoint, 18);
    case 'text_note':
      return renderTextElement(element, transformPoint, 16);
    case 'highlight_line':
      return renderStraightLine(element, transformPoint, 8);
    case 'highlight_curve':
      return renderCurve(element, transformPoint, 8);
    case 'arrow':
      return renderArrow(element, transformPoint);
    case 'box':
      return renderBox(element, transformPoint, scale);
    case 'circle':
      return renderCircle(element, transformPoint, scale);
    case 'point_label':
      return renderPointLabel(element, transformPoint);
    case 'segment_label':
      return renderSegmentLabel(element, transformPoint);
    case 'dimension_line':
      return renderDimensionLine(element, transformPoint);
    case 'dimension_curve':
      return renderDimensionCurve(element, transformPoint);
    case 'freehand_dimension_marker':
      return renderFreehandDimensionMarker(element, transformPoint);
    default:
      return [];
  }
}

function renderTextElement(
  element: CandidateSpecElement,
  transformPoint: (point: Point) => Point,
  fontSize: number
): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const anchor = asPoint(geometry?.anchor);
  const text = getElementText(element);
  if (!anchor || !text) {
    return [];
  }

  const [x, y] = transformPoint(anchor);
  return [{ kind: 'text', id: element.id, x, y, text, color: colorFor(element), fontSize }];
}

function renderStraightLine(
  element: CandidateSpecElement,
  transformPoint: (point: Point) => Point,
  strokeWidth: number
): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const start = asPoint(geometry?.start);
  const end = asPoint(geometry?.end);
  if (!start || !end) {
    return [];
  }

  return [linePrimitive(element.id, [start, end], transformPoint, colorFor(element), strokeWidth)];
}

function renderCurve(
  element: CandidateSpecElement,
  transformPoint: (point: Point) => Point,
  strokeWidth: number
): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const start = asPoint(geometry?.start);
  const end = asPoint(geometry?.end);
  const controlPoints = asPointList(geometry?.control_points);
  if (!start || !end || controlPoints.length === 0) {
    return [];
  }

  return [
    linePrimitive(element.id, [start, ...controlPoints.slice(0, 2), end], transformPoint, colorFor(element), strokeWidth, 0.42)
  ];
}

function renderArrow(element: CandidateSpecElement, transformPoint: (point: Point) => Point): PreviewPrimitive[] {
  const base = renderStraightLine(element, transformPoint, 2);
  if (base.length === 0 || base[0].kind !== 'line') {
    return [];
  }

  const points = base[0].points;
  return [
    base[0],
    {
      kind: 'text',
      id: `${element.id}:arrowhead`,
      x: points[points.length - 2] - 5,
      y: points[points.length - 1] + 5,
      text: '→',
      color: colorFor(element),
      fontSize: 18
    }
  ];
}

function renderBox(
  element: CandidateSpecElement,
  transformPoint: (point: Point) => Point,
  scale: number
): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const bbox = asBBox(geometry?.bbox) ?? asBBox(element.bbox);
  if (!bbox) {
    return [];
  }

  const [x, y] = transformPoint([bbox[0], bbox[1]]);
  return [
    {
      kind: 'rect',
      id: element.id,
      x,
      y,
      width: bbox[2] * scale,
      height: bbox[3] * scale,
      color: colorFor(element),
      strokeWidth: 2
    }
  ];
}

function renderCircle(
  element: CandidateSpecElement,
  transformPoint: (point: Point) => Point,
  scale: number
): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const center = asPoint(geometry?.center);
  const radius = geometry?.radius;
  if (center && isPositiveNumber(radius)) {
    const [x, y] = transformPoint(center);
    return [{ kind: 'circle', id: element.id, x, y, radius: radius * scale, color: colorFor(element), strokeWidth: 2 }];
  }

  const bbox = asBBox(geometry?.bbox) ?? asBBox(element.bbox);
  if (!bbox) {
    return [];
  }

  const [x, y] = transformPoint([bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2]);
  return [{ kind: 'circle', id: element.id, x, y, radius: (Math.min(bbox[2], bbox[3]) / 2) * scale, color: colorFor(element), strokeWidth: 2 }];
}

function renderPointLabel(element: CandidateSpecElement, transformPoint: (point: Point) => Point): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const point = asPoint(geometry?.point);
  const text = getElementText(element);
  if (!point || !text) {
    return [];
  }

  const labelAnchor = asPoint(geometry?.label_anchor) ?? [point[0] + 8, point[1] - 8];
  const [pointX, pointY] = transformPoint(point);
  const [labelX, labelY] = transformPoint(labelAnchor);
  const color = colorFor(element);
  return [
    { kind: 'circle', id: `${element.id}:point`, x: pointX, y: pointY, radius: 3, color, strokeWidth: 0, fill: color },
    { kind: 'text', id: `${element.id}:label`, x: labelX, y: labelY, text, color, fontSize: 14 }
  ];
}

function renderSegmentLabel(element: CandidateSpecElement, transformPoint: (point: Point) => Point): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const start = asPoint(geometry?.start);
  const end = asPoint(geometry?.end);
  const text = getElementText(element);
  if (!start || !end || !text) {
    return [];
  }

  const labelAnchor = asPoint(geometry?.label_anchor) ?? [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2];
  const [x, y] = transformPoint(labelAnchor);
  return [{ kind: 'text', id: element.id, x, y, text, color: colorFor(element), fontSize: 14 }];
}

function renderDimensionLine(element: CandidateSpecElement, transformPoint: (point: Point) => Point): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const start = asPoint(geometry?.visible_start) ?? asPoint(geometry?.target_anchor_start);
  const end = asPoint(geometry?.visible_end) ?? asPoint(geometry?.target_anchor_end);
  if (!start || !end) {
    return [];
  }

  const primitives: PreviewPrimitive[] = [linePrimitive(element.id, [start, end], transformPoint, colorFor(element), 2)];
  primitives.push(...renderGeometryLabel(element, transformPoint));
  return primitives;
}

function renderDimensionCurve(element: CandidateSpecElement, transformPoint: (point: Point) => Point): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const start = asPoint(geometry?.visible_start) ?? asPoint(geometry?.target_anchor_start);
  const end = asPoint(geometry?.visible_end) ?? asPoint(geometry?.target_anchor_end);
  const controls = asPointList(geometry?.control_points ?? geometry?.curve_control_points);
  if (!start || !end || controls.length === 0) {
    return [];
  }

  const primitives: PreviewPrimitive[] = [
    linePrimitive(element.id, [start, ...controls.slice(0, 2), end], transformPoint, colorFor(element), 2, 0.42)
  ];
  primitives.push(...renderGeometryLabel(element, transformPoint));
  return primitives;
}

function renderFreehandDimensionMarker(
  element: CandidateSpecElement,
  transformPoint: (point: Point) => Point
): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const strokes = Array.isArray(geometry?.visible_strokes) ? geometry.visible_strokes : [];
  const color = colorFor(element);
  const primitives = strokes.flatMap((stroke) => {
    const strokeRecord = asRecord(stroke);
    const strokeId = strokeRecord?.stroke_id == null ? null : String(strokeRecord.stroke_id);
    const points = asPointList(strokeRecord?.points);
    if (!strokeId || points.length < 2) {
      return [];
    }

    return [linePrimitive(`${element.id}:${strokeId}`, points, transformPoint, color, 4, 0.42)];
  });

  primitives.push(...renderGeometryLabel(element, transformPoint));
  return primitives;
}

function renderGeometryLabel(element: CandidateSpecElement, transformPoint: (point: Point) => Point): PreviewPrimitive[] {
  const geometry = asRecord(element.geometry);
  const text = getElementText(element);
  const anchor = asPoint(geometry?.label_anchor);
  if (!text || !anchor) {
    return [];
  }

  const [x, y] = transformPoint(anchor);
  return [{ kind: 'text', id: `${element.id}:label`, x, y, text, color: colorFor(element), fontSize: 16 }];
}

function linePrimitive(
  id: string,
  points: Point[],
  transformPoint: (point: Point) => Point,
  color: string,
  strokeWidth: number,
  tension?: number
): PreviewPrimitive {
  return {
    kind: 'line',
    id,
    points: points.flatMap((point) => transformPoint(point)),
    color,
    strokeWidth,
    tension
  };
}

function colorFor(element: CandidateSpecElement): string {
  return element.color || DEFAULT_OVERLAY_COLOR;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }

  return null;
}

function asPoint(value: unknown): Point | null {
  if (!Array.isArray(value) || value.length !== 2 || !isNumber(value[0]) || !isNumber(value[1])) {
    return null;
  }

  return [value[0], value[1]];
}

function asPointList(value: unknown): Point[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map(asPoint).filter((point): point is Point => point !== null);
}

function asBBox(value: unknown): BBox | null {
  if (
    !Array.isArray(value) ||
    value.length !== 4 ||
    !isNumber(value[0]) ||
    !isNumber(value[1]) ||
    !isPositiveNumber(value[2]) ||
    !isPositiveNumber(value[3])
  ) {
    return null;
  }

  return [value[0], value[1], value[2], value[3]];
}

function isPositiveNumber(value: unknown): value is number {
  return isNumber(value) && value > 0;
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
